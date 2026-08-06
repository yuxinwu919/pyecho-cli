"""Numerical / physics consistency tests for the pyecho numerical stack.

These tests validate four self-consistency properties that any trustworthy
wake solver post-processor must satisfy.  They are pure-numeric (no ECHO2D
executable required) and are built on :mod:`pyecho.mathlib` plus the
synthetic-data wake pipeline in :mod:`pyecho.postprocess.wakes.recta`
(which itself is implemented on top of :mod:`pyecho.mathlib`).

Groups
------
1. **wake <-> impedance roundtrip preserves the loss factor** — the FFT
   pair :func:`wake2impedance` / :func:`impedance2wake` is exactly
   energy-consistent: the reconstructed wake carries the same loss factor,
   RMS spread and peak, the impedance of a real wake is Hermitian, and
   the time- and frequency-domain energies agree via Parseval.

2. **Mesh refinement convergence** — the longitudinal loss factor is a
   well-converged numerical observable: on successively finer ``s``-grids
   it approaches the analytic limit with second-order (trapezoidal) rate,
   and the closed-form Gaussian x Gaussian result is recovered exactly.

3. **Mode-count convergence** — the recta geometry longitudinal wake is a
   sum over azimuthal modes with decaying amplitudes; truncating the sum
   at ``n`` modes converges to the full solution as ``n`` grows, and the
   per-mode contribution to the loss factor decreases monotonically.

4. **Symmetry magn + elec = full solution** — any driving charge splits
   into a symmetric (``magn`` / cos-cos) and antisymmetric (``elec`` /
   sin-sin) part per ECHO_manual Eq. (4.19)–(4.22); the full off-axis wake
   is the *linear sum* of the two half-domain solutions, the antisymmetric
   part vanishes on axis, and it does not contribute to the loss factor of
   a symmetric bunch.
"""

from __future__ import annotations

import numpy as np
import pytest

from pyecho.mathlib import c, gauss, impedance2wake, integr_tr, loss_shape, wake2impedance
from pyecho.postprocess.wakes.recta import compute_wake_long_quad, compute_wake_zy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _loss(s: np.ndarray, bunch: np.ndarray, wake: np.ndarray) -> float:
    """Longitudinal loss factor κ = −∫λ·W·ds via :func:`loss_shape`."""
    k, _spread, _peak = loss_shape(
        np.column_stack([s, bunch]),
        np.column_stack([s, wake]),
    )
    return k


def _uniform_cos(N: int, L: float, A: float, omega: float) -> float:
    """Loss factor of a uniform bunch against a cosinusoidal wake.

    Analytic value: κ = A·sin(ω·L)/(ω·L).
    """
    s = np.linspace(-L, L, N)
    bunch = np.full_like(s, 1.0 / (2.0 * L))
    return _loss(s, bunch, -A * np.cos(omega * s))


def _coupling_matrix(
    D: float,
    s: np.ndarray,
    amps: list[float],
    sigma_w: float,
) -> np.ndarray:
    """Build a Wcc/Wss coupling matrix directly (no files needed).

    Row 0: ``[D, s_0, …, s_{ns-1}]``; row *i* (i≥1): ``[k_i, A_i·W(s)]``
    with :math:`k_i = \\pi(2i-1)/D`.
    """
    ns = len(s)
    n_modes = len(amps)
    matrix: np.ndarray = np.zeros((n_modes + 1, ns + 1), dtype=np.float64)
    matrix[0, 0] = D
    matrix[0, 1:] = s
    for i, A in enumerate(amps, start=1):
        k = np.pi * (2 * i - 1) / D
        matrix[i, 0] = k
        matrix[i, 1:] = A * np.exp(-(s ** 2) / (2.0 * sigma_w * sigma_w))
    return matrix


# ===========================================================================
# 1. Wake ↔ impedance roundtrip preserves the loss factor
# ===========================================================================


class TestWakeImpedanceRoundtrip:
    """The FFT pair is exactly energy-consistent under a full roundtrip."""

    def test_roundtrip_preserves_loss_factor(self) -> None:
        """wake→impedance→wake recovers the same κ for a Gaussian wake."""
        s = np.linspace(-3e-3, 3e-3, 256)
        bunch = gauss(s, 5e-4)
        wake = -1.5 * np.exp(-(s ** 2) / (2.0 * (8e-4) ** 2))
        f, Z = wake2impedance(s, wake)
        _, wake_rt = impedance2wake(f, Z)
        loss0 = _loss(s, bunch, wake)
        loss1 = _loss(s, bunch, wake_rt)
        assert loss1 == pytest.approx(loss0, rel=1e-10, abs=1e-12)
        assert np.allclose(wake_rt, wake, atol=1e-12)

    def test_roundtrip_preserves_oscillatory_wake_observables(self) -> None:
        """Loss, RMS spread and peak survive for a damped oscillatory wake."""
        s = np.linspace(-3e-3, 3e-3, 256)
        bunch = gauss(s, 5e-4)
        wake = (
            -np.sin(2.0 * np.pi * 2e3 * (s - 0.5e-3))
            * np.exp(-(s ** 2) / (2.0 * (8e-4) ** 2))
        )
        f, Z = wake2impedance(s, wake)
        _, wake_rt = impedance2wake(f, Z)
        h = s[1] - s[0]

        loss0 = _loss(s, bunch, wake)
        loss1 = _loss(s, bunch, wake_rt)
        # κ may be ~0 for this almost-orthogonal wake → absolute tolerance.
        assert abs(loss1 - loss0) < 1e-12

        spread0 = np.sqrt(np.sum(bunch * (wake + loss0) ** 2) * h)
        spread1 = np.sqrt(np.sum(bunch * (wake_rt + loss1) ** 2) * h)
        assert spread1 == pytest.approx(spread0, rel=1e-10)

        assert np.max(np.abs(wake_rt)) == pytest.approx(
            np.max(np.abs(wake)), rel=1e-10
        )

    def test_parseval_energy_consistency(self) -> None:
        """Time-domain wake energy = c · frequency-domain impedance energy."""
        s = np.linspace(-3e-3, 3e-3, 256)
        wake = 1.5 * np.exp(-(s ** 2) / (2.0 * (8e-4) ** 2))
        f, Z = wake2impedance(s, wake)
        h = s[1] - s[0]
        df = f[1] - f[0]
        energy_t = np.sum(wake ** 2) * h
        energy_f = np.sum(np.abs(Z) ** 2) * df
        assert energy_t == pytest.approx(c * energy_f, rel=1e-9)

    def test_impedance_hermitian_symmetry(self) -> None:
        """A real wake maps to a Hermitian impedance: Z[k] = conj(Z[N−k])."""
        s = np.linspace(-3e-3, 3e-3, 256)
        wake = -1.5 * np.exp(-(s ** 2) / (2.0 * (8e-4) ** 2))
        _, Z = wake2impedance(s, wake)
        n = len(Z)
        idx = np.arange(n)
        assert np.allclose(Z, np.conj(Z[(n - idx) % n]), atol=1e-14)
        # Re even / Im odd about the DC bin.
        mid = n // 2
        assert np.allclose(Z[1:mid].real, Z[n - 1:mid:-1].real, atol=1e-12)
        assert np.allclose(Z[1:mid].imag, -Z[n - 1:mid:-1].imag, atol=1e-12)

    def test_roundtrip_loss_factor_converges_to_analytic(self) -> None:
        """Roundtrip κ equals original κ and both → A·sin(ωL)/(ωL)."""
        L = 2e-3
        A = 1.5
        omega = 3.0 * np.pi / (2.0 * L)
        analytic = A * np.sin(omega * L) / (omega * L)
        errors: list[float] = []
        for N in (128, 512, 2048):
            s = np.linspace(-L, L, N)
            bunch = np.full_like(s, 1.0 / (2.0 * L))
            wake = -A * np.cos(omega * s)
            f, Z = wake2impedance(s, wake)
            _, wake_rt = impedance2wake(f, Z)
            k0 = _loss(s, bunch, wake)
            k1 = _loss(s, bunch, wake_rt)
            assert k1 == pytest.approx(k0, rel=1e-10, abs=1e-12)
            errors.append(abs(k0 - analytic))
        assert errors[0] > errors[1] > errors[2]  # converging
        assert errors[-1] < 5e-5  # converged at the finest grid


# ===========================================================================
# 2. Mesh refinement convergence
# ===========================================================================


class TestMeshConvergence:
    """The loss factor converges (with second-order rate) as the mesh refines."""

    def test_loss_factor_converges_with_mesh(self) -> None:
        """Coarse-grid κ is farther from the analytic limit than the fine grid."""
        L = 2e-3
        A = 1.5
        omega = 3.0 * np.pi / (2.0 * L)
        analytic = A * np.sin(omega * L) / (omega * L)
        k_coarse = _uniform_cos(64, L, A, omega)
        k_fine = _uniform_cos(2048, L, A, omega)
        assert abs(k_coarse - analytic) > abs(k_fine - analytic)
        assert abs(k_fine - analytic) < 1e-5

    def test_loss_factor_second_order_rate(self) -> None:
        """Doubling N quarters the error (trapezoidal O(h²) behaviour)."""
        L = 2e-3
        A = 1.5
        omega = 3.0 * np.pi / (2.0 * L)
        analytic = A * np.sin(omega * L) / (omega * L)
        errors = [
            abs(_uniform_cos(N, L, A, omega) - analytic)
            for N in (128, 256, 512, 1024)
        ]
        for coarse, fine in zip(errors, errors[1:]):
            assert coarse > fine
            assert 2.0 < coarse / fine < 8.0

    def test_integr_tr_endpoint_converges(self) -> None:
        """Cumulative trapezoidal endpoint for x² over [0, 1] → 1/3 at O(h²)."""
        ref = 1.0 / 3.0
        errors: list[float] = []
        for N in (8, 16, 32, 64, 128):
            x = np.linspace(0.0, 1.0, N)
            endpoint = integr_tr(x[1] - x[0], x ** 2)[-1]
            errors.append(abs(endpoint - ref))
        assert all(errors[i] > errors[i + 1] for i in range(len(errors) - 1))
        for coarse, fine in zip(errors, errors[1:]):
            assert 2.0 < coarse / fine < 8.0
        assert errors[-1] < 5e-5

    def test_loss_factor_gauss_gauss_analytic(self) -> None:
        """Gaussian bunch × Gaussian wake matches the closed form A·σm/σb."""
        sig_b, sig_w, A = 5e-4, 8e-4, 1.5
        sigma_m = sig_b * sig_w / np.sqrt(sig_b ** 2 + sig_w ** 2)
        analytic = A * sigma_m / sig_b
        s = np.linspace(-3e-3, 3e-3, 1024)
        bunch = gauss(s, sig_b)
        wake = -A * np.exp(-(s ** 2) / (2.0 * sig_w ** 2))
        assert _loss(s, bunch, wake) == pytest.approx(analytic, rel=1e-8)


# ===========================================================================
# 3. Mode count convergence
# ===========================================================================


class TestModeConvergence:
    """Truncating the modal sum at n modes converges to the full solution."""

    def test_modal_partial_sum_converges(self) -> None:
        """κ(n) → κ₁·Σᵢ 1/i² = κ₁·π²/6 as the modal sum grows."""
        s = np.linspace(-3e-3, 3e-3, 501)
        shape = np.exp(-(s ** 2) / (2.0 * (8e-4) ** 2))
        bunch = gauss(s, 5e-4)
        kappa_1 = _loss(s, bunch, -shape)
        limit = kappa_1 * np.pi ** 2 / 6.0

        errors: list[float] = []
        for n in (16, 256, 4096):
            amps = 1.0 / np.arange(1, n + 1) ** 2
            wake = -np.sum(amps[:, None] * shape[None, :], axis=0)
            errors.append(abs(_loss(s, bunch, wake) - limit))
        assert errors[0] > errors[1] > errors[2]
        # Tail ~1/n → each 16× more modes shrinks the error ~16×.
        assert 8.0 < errors[0] / errors[1] < 32.0
        assert 8.0 < errors[1] / errors[2] < 32.0

    def test_modal_contributions_decay(self) -> None:
        """Per-mode loss contribution is κ₁/i² — strictly decreasing."""
        s = np.linspace(-3e-3, 3e-3, 501)
        shape = np.exp(-(s ** 2) / (2.0 * (8e-4) ** 2))
        bunch = gauss(s, 5e-4)
        kappa_1 = _loss(s, bunch, -shape)

        n_modes = 8
        marginal: list[float] = []
        wake = np.zeros_like(s)
        for i in range(1, n_modes + 1):
            wake_prev = wake.copy()
            wake = wake - (1.0 / i ** 2) * shape
            marginal.append(abs(_loss(s, bunch, wake) - _loss(s, bunch, wake_prev)))
        predicted = kappa_1 / np.arange(1, n_modes + 1) ** 2
        assert np.allclose(marginal, predicted, rtol=1e-9)
        assert all(marginal[i] > marginal[i + 1] for i in range(len(marginal) - 1))

    def test_recta_wlong_mode_convergence(self) -> None:
        """The production modal sum Wlong(n) approaches Wlong(all modes)."""
        s = np.linspace(-3e-3, 3e-3, 501)
        D = 0.02
        n_modes = 20
        amps = [1.0 / i ** 2 for i in range(1, n_modes + 1)]
        wcc = _coupling_matrix(D, s, amps, sigma_w=8e-4)
        full = compute_wake_long_quad(wcc, n_modes=n_modes)["Wlong"]

        diffs: list[float] = []
        for n in (2, 4, 8, 12, 16, 20):
            wlong = compute_wake_long_quad(wcc, n_modes=n)["Wlong"]
            diffs.append(float(np.max(np.abs(wlong - full))))
        assert all(diffs[i] > diffs[i + 1] for i in range(len(diffs) - 1))
        assert diffs[0] > 1e-3  # few modes is far from converged
        assert diffs[-1] < 1e-12  # n_modes == available rows is exact


# ===========================================================================
# 4. Symmetry: magn + elec = full solution
# ===========================================================================


class TestSymmetry:
    """Half-domain magn/elec solutions combine linearly into the full wake."""

    def test_charge_even_odd_decomposition(self) -> None:
        """Eq. (4.19): ρ = ρ^H (symmetric, magn) + ρ^E (antisymmetric, elec)."""
        y = np.linspace(-0.01, 0.01, 201)
        rho = np.exp(-(y - 0.002) ** 2 / (2.0 * (0.003) ** 2))
        rho_H = 0.5 * (rho + rho[::-1])
        rho_E = 0.5 * (rho - rho[::-1])
        assert np.allclose(rho_H + rho_E, rho)  # exact reconstruction
        assert np.allclose(rho_H, rho_H[::-1])  # even → magn / cos-cos
        assert np.allclose(rho_E, -rho_E[::-1])  # odd → elec / sin-sin

    def test_odd_wake_vanishes_for_symmetric_bunch(self) -> None:
        """The antisymmetric (elec) wake adds nothing to a symmetric bunch's loss."""
        s = np.linspace(-2e-3, 2e-3, 401)
        bunch = gauss(s, 5e-4)  # symmetric in s
        wake_even = -1.2 * np.exp(-(s ** 2) / (2.0 * (8e-4) ** 2))
        wake_odd = 0.7 * s / s[-1]  # odd in s

        k_odd = _loss(s, bunch, wake_odd)
        assert abs(k_odd) < 1e-12  # ∫λ·W_odd = 0 exactly on a symmetric grid

        k_full = _loss(s, bunch, wake_even + wake_odd)
        k_even = _loss(s, bunch, wake_even)
        assert k_full == pytest.approx(k_even, rel=1e-10, abs=1e-12)

    def test_magn_plus_elec_equals_full(self) -> None:
        """Full off-axis wake = magn-part + elec-part; on axis elec vanishes."""
        s = np.linspace(-3e-3, 3e-3, 501)
        D = 0.02
        amps = [1.0 / i ** 2 for i in range(1, 21)]
        wcc = _coupling_matrix(D, s, amps, sigma_w=8e-4)
        wss = wcc.copy()

        # Zero only the mode rows (keep k-values in column 0): isolate the
        # cos-cos (magn) and sin-sin (elec) contributions respectively.
        wcc_only = wcc.copy()
        wss_only = wss.copy()
        wcc_only[1:, 1:] = 0.0
        wss_only[1:, 1:] = 0.0

        y, y0 = 0.0015, 0.001
        res_full = compute_wake_zy(wcc, wss, np.array([y]), y0=y0)
        res_magn = compute_wake_zy(wcc, wss_only, np.array([y]), y0=y0)
        res_elec = compute_wake_zy(wcc_only, wss, np.array([y]), y0=y0)
        # Linearity of Maxwell's equations → magn + elec = full.
        assert np.allclose(res_full["Wz"][0], res_magn["Wz"][0] + res_elec["Wz"][0])
        assert np.allclose(res_full["Wy"][0], res_magn["Wy"][0] + res_elec["Wy"][0])

        # On axis sinh(0)=0 → the elec (sin-sin) part vanishes; magn alone
        # reproduces the full on-axis longitudinal wake.
        res_axis_elec = compute_wake_zy(wcc_only, wss, np.array([0.0]), y0=0.0)
        assert np.allclose(res_axis_elec["Wz"][0], 0.0)
        assert np.allclose(res_axis_elec["Wy"][0], 0.0)
        res_axis_full = compute_wake_zy(wcc, wss, np.array([0.0]), y0=0.0)
        res_axis_magn = compute_wake_zy(wcc, wss_only, np.array([0.0]), y0=0.0)
        assert np.allclose(res_axis_full["Wz"][0], res_axis_magn["Wz"][0])
