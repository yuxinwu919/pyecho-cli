"""Physics-validation tests for the ECHO2D wake post-processing.

These tests check *physical* identities that the wake-processing code
must satisfy, independently of any particular solver output.  They are
pure-numpy / analytic tests and do not run the ECHO2D binary.

Covered topics
--------------
1. **Panofsky-Wenzel theorem**  — ``∂W_y/∂s = −∂W_z/∂y``
   (the transverse wake is the negative *s*-integral of the transverse
   gradient of the longitudinal wake).  The sign convention matches the
   one used in ``pyecho.postprocess.wakes.recta``::

       Wz(y,s) = scale · Σ_k [ Wcc·cosh(k y)·cosh(k y₀)
                             + Wss·sinh(k y)·sinh(k y₀) ]
       Wy(y,s) = −scale · IntegrTr(h_s, Σ_k k·[ Wcc·sinh(k y)·cosh(k y₀)
                                             + Wss·cosh(k y)·sinh(k y₀) ])

   so that ``∂Wy/∂s = −∂Wz/∂y``.

2. **Loss factor analytic (Gaussian × Gaussian)**  — for a Gaussian
   bunch with RMS ``σ_b`` and a Gaussian wake
   ``W(s) = −W₀·exp(−s²/(2σ_w²))`` the loss factor has the closed form::

       κ = W₀ · σ_w / √(σ_b² + σ_w²)

   and, when the bunch is displaced by ``s₀``::

       κ = W₀ · σ_w / √(σ_b² + σ_w²) · exp(−s₀² / (2(σ_b² + σ_w²)))

3. **Wake reciprocity** — the wake coupling is symmetric under
   source/witness exchange, and the transverse-kick gradient satisfies
   the corresponding mixed-derivative identity.

4. **Mode orthogonality** — the ``cos``/``sin`` transverse eigenmodes
   ``cos(π m y / D)``, ``sin(π m y / D)`` (odd ``m``) form an orthogonal
   basis over ``[−D/2, D/2]`` with norm ``√(D/2)``.

5. **cosh/sinh scaling** — the transverse dependence ``cosh(k y)`` /
   ``sinh(k y)`` of the modal expansion obeys the hyperbolic scaling laws
   (source-at-witness case scales as ``cosh²(k y)`` for a monopole-like
   mode and ``sinh²(k y)`` for a dipole-like mode).

6. **Kick factor sign convention** — the transverse kick factor is
   ``k_⊥ = +∫ λ(s) W_⊥(s) ds``, so a defocusing (positive) transverse
   wake gives a positive kick.  The ``round``-geometry convention
   (kick computed on the *pre-negation* cumulative integral,
   ``W_trans = −IntegrTr(…)``) reproduces this physical sign.
"""

from __future__ import annotations

import numpy as np
import pytest

from pyecho.mathlib.gauss import gauss
from pyecho.mathlib.integration import integr_tr
from pyecho.mathlib.loss import long_loss2, loss_shape
from pyecho.postprocess.wakes.recta import compute_wake_off_axis, compute_wake_zy

# ---------------------------------------------------------------------------
# Shared model parameters
# ---------------------------------------------------------------------------

_D = 0.01  # structure width [m]  (Width in input_in.txt)
_S = np.linspace(-2e-3, 2e-3, 401)  # longitudinal grid [m]
_HS = float(_S[1] - _S[0])
_SIGMA_S = 1e-3  # smoothness scale of the synthetic modal profiles [m]
_K1 = np.pi / _D  # lowest odd-mode wavenumber [rad/m]


def _profile(s: np.ndarray) -> np.ndarray:
    """A smooth, bell-shaped longitudinal profile used for synthetic modes."""
    return np.exp(-(s**2) / (2.0 * _SIGMA_S**2))


def _synthetic_coupling(
    wcc_profiles: list[np.ndarray],
    wss_profiles: list[np.ndarray],
    *,
    D: float = _D,
    s: np.ndarray = _S,
) -> tuple[np.ndarray, np.ndarray]:
    """Build Wcc / Wss matrices in the ``recta.py`` on-disk format.

    Returns two arrays of shape ``(n_modes+1, ns+1)``:

    * row 0    = ``[D, s_0, …, s_{ns-1}]``
    * row i≥1  = ``[k_i, Wcc_i(s_0), …, Wcc_i(s_{ns-1})]``

    with wavenumbers ``k_i = π·(2i−1)/D`` (odd modes, matching ECHO2D).
    """
    n_modes = len(wcc_profiles)
    if len(wss_profiles) != n_modes:
        raise ValueError("wcc and wss must have the same number of modes.")
    ns = len(s)
    wcc = np.zeros((n_modes + 1, ns + 1), dtype=np.float64)
    wss = np.zeros((n_modes + 1, ns + 1), dtype=np.float64)
    for mat, profiles in ((wcc, wcc_profiles), (wss, wss_profiles)):
        mat[0, 0] = D
        mat[0, 1:] = s
        for i, prof in enumerate(profiles):
            mat[i + 1, 0] = np.pi / D * (2 * i + 1)
            mat[i + 1, 1:] = prof
    return wcc, wss


def _assert_panofsky_wenzel(
    Wz: np.ndarray,
    Wy: np.ndarray,
    y: np.ndarray,
    s: np.ndarray,
    *,
    atol: float,
    rtol: float = 0.0,
) -> None:
    """Assert ``∂Wy/∂s = −∂Wz/∂y`` by central differences on interior points.

    ``Wz``, ``Wy`` are (ny, ns) maps indexed by ``y`` then ``s``.
    """
    ny, ns = Wz.shape
    dy = y[1] - y[0]
    hs = s[1] - s[0]
    i0, i1 = 2, ny - 2  # y-index range for the interior rectangle
    j0, j1 = 2, ns - 2  # s-index range for the interior rectangle

    # ∂Wy/∂s at (i, j) : (Wy[i, j+1] − Wy[i, j−1]) / (2 h_s)
    dWy_ds = (Wy[i0:i1, j0 + 1:j1 + 1] - Wy[i0:i1, j0 - 1:j1 - 1]) / (2.0 * hs)
    # ∂Wz/∂y at (i, j) : (Wz[i+1, j] − Wz[i−1, j]) / (2 d_y)
    dWz_dy = (Wz[i0 + 1:i1 + 1, j0:j1] - Wz[i0 - 1:i1 - 1, j0:j1]) / (2.0 * dy)

    assert dWy_ds.shape == dWz_dy.shape, (dWy_ds.shape, dWz_dy.shape)
    np.testing.assert_allclose(dWy_ds, -dWz_dy, rtol=rtol, atol=atol)


# ---------------------------------------------------------------------------
# 1. Panofsky-Wenzel theorem
# ---------------------------------------------------------------------------


class TestPanofskyWenzel:
    def test_panofsky_wenzel_analytic_modal(self) -> None:
        """A modal wake built as Wz=cosh(k y)·A(s), Wy=−∫k·sinh(k y)·A satisfies ∂Wy/∂s=−∂Wz/∂y."""
        y = np.linspace(-1e-3, 1e-3, 81)
        k = _K1
        A = _profile(_S)
        # Wz(y, s) = cosh(k y) · A(s);  ∂Wz/∂y = k·sinh(k y)·A(s)
        Wz = np.outer(np.cosh(k * y), A)
        # Wy(y, s) = −IntegrTr(∂Wz/∂y) = −k·sinh(k y)·IntegrTr(A)
        Wy = -np.outer(k * np.sinh(k * y), integr_tr(_HS, A))
        _assert_panofsky_wenzel(Wz, Wy, y, _S, atol=1e-3, rtol=1e-3)

    def test_panofsky_wenzel_wy_from_dwzdy_integr_tr(self) -> None:
        """The code's off-axis Wy equals −IntegrTr(∂Wz/∂y) (finite-difference P-W reconstruction)."""
        y0, y = 3e-4, 5e-4
        delta = 5e-5
        wcc, wss = _synthetic_coupling(
            [_profile(_S)], [0.5 * _profile(_S)]
        )
        wz_plus = compute_wake_off_axis(wcc, wss, y0=y0, y=y + delta)["Wz"]
        wz_minus = compute_wake_off_axis(wcc, wss, y0=y0, y=y - delta)["Wz"]
        dWz_dy = (wz_plus - wz_minus) / (2.0 * delta)

        wy_expected = -integr_tr(_HS, dWz_dy)
        wy_code = compute_wake_off_axis(wcc, wss, y0=y0, y=y)["Wy"]
        np.testing.assert_allclose(wy_code, wy_expected, rtol=1e-3, atol=1e-3)

    def test_panofsky_wenzel_wake_zy_map(self) -> None:
        """The 2-D Wz/Wy map returned by compute_wake_zy obeys ∂Wy/∂s = −∂Wz/∂y."""
        prof2 = 0.25 * _profile(_S)
        wcc, wss = _synthetic_coupling(
            [_profile(_S), prof2],
            [0.5 * _profile(_S), 0.25 * prof2],
        )
        y = np.linspace(-1e-3, 1e-3, 81)
        result = compute_wake_zy(wcc, wss, y_offsets=y, y0=0.0)
        _assert_panofsky_wenzel(
            result["Wz"], result["Wy"], y, result["s"], atol=1e-2, rtol=1e-2
        )


# ---------------------------------------------------------------------------
# 2. Loss factor — Gaussian bunch × Gaussian wake closed form
# ---------------------------------------------------------------------------


class TestLossFactorAnalytic:
    def test_loss_factor_gaussian_gaussian_centered(self) -> None:
        """κ = W₀·σ_w/√(σ_b²+σ_w²) for centered bunch and Gaussian wake."""
        s = np.linspace(-3e-3, 3e-3, 4001)
        sigma_b, sigma_w, W0 = 3e-4, 4e-4, 2.0
        lam = gauss(s, sigma_b)
        wake = -W0 * np.exp(-(s**2) / (2.0 * sigma_w**2))
        loss, _, _ = loss_shape(
            np.column_stack([s, lam]), np.column_stack([s, wake])
        )
        expected = W0 * sigma_w / np.sqrt(sigma_b**2 + sigma_w**2)
        assert loss == pytest.approx(expected, rel=1e-3)

    def test_loss_factor_gaussian_gaussian_shifted(self) -> None:
        """Displaced bunch picks up the factor exp(−s₀²/(2(σ_b²+σ_w²)))."""
        s = np.linspace(-3e-3, 3e-3, 4001)
        sigma_b, sigma_w, W0, s0 = 3e-4, 4e-4, 2.0, 2e-4
        lam = gauss(s - s0, sigma_b)
        wake = -W0 * np.exp(-(s**2) / (2.0 * sigma_w**2))
        loss, _, _ = loss_shape(
            np.column_stack([s, lam]), np.column_stack([s, wake])
        )
        expected = (
            W0
            * sigma_w
            / np.sqrt(sigma_b**2 + sigma_w**2)
            * np.exp(-(s0**2) / (2.0 * (sigma_b**2 + sigma_w**2)))
        )
        assert loss == pytest.approx(expected, rel=1e-3)

    def test_loss_factor_long_loss2_closed_form(self) -> None:
        """long_loss2 (internal Gaussian bunch) matches the closed form."""
        sigma_b, sigma_w, W0 = 3e-4, 4e-4, 2.0
        wake = -W0 * np.exp(-(_S**2) / (2.0 * sigma_w**2))
        loss, _, _ = long_loss2(_S, wake, sigma_b)
        expected = W0 * sigma_w / np.sqrt(sigma_b**2 + sigma_w**2)
        assert loss == pytest.approx(expected, rel=1e-3)

    def test_loss_factor_delta_wake_limit(self) -> None:
        """As σ_w → 0 the loss factor obeys κ ≈ W₀·σ_w/σ_b (δ-wake limit)."""
        sigma_b, W0 = 3e-4, 2.0
        sigma_w_vals = (3e-4, 7.5e-5, 1.875e-5, 4.6875e-6)
        last_loss = None
        for sigma_w in sigma_w_vals:
            h = min(sigma_b, sigma_w) / 100.0
            s = np.arange(-3e-3, 3e-3, h)
            lam = gauss(s, sigma_b)
            wake = -W0 * np.exp(-(s**2) / (2.0 * sigma_w**2))
            last_loss, _, _ = loss_shape(
                np.column_stack([s, lam]), np.column_stack([s, wake])
            )
            expected = W0 * sigma_w / np.sqrt(sigma_b**2 + sigma_w**2)
            assert last_loss == pytest.approx(expected, rel=1e-3)
        # δ-wake asymptotic: κ → W₀·σ_w/σ_b
        assert last_loss == pytest.approx(
            W0 * sigma_w_vals[-1] / sigma_b, rel=5e-3
        )


# ---------------------------------------------------------------------------
# 3. Wake reciprocity
# ---------------------------------------------------------------------------


class TestWakeReciprocity:
    def test_wake_reciprocity_wz_source_witness_swap(self) -> None:
        """Longitudinal wake is symmetric under source/witness exchange."""
        wcc, wss = _synthetic_coupling(
            [_profile(_S)], [0.5 * _profile(_S)]
        )
        y0, y = 3e-4, 5e-4
        wz_ab = compute_wake_off_axis(wcc, wss, y0=y0, y=y)["Wz"]
        wz_ba = compute_wake_off_axis(wcc, wss, y0=y, y=y0)["Wz"]
        np.testing.assert_allclose(wz_ab, wz_ba, rtol=1e-9, atol=1e-12)

    def test_wake_reciprocity_transverse_gradient(self) -> None:
        """∂Wy(y, y₀)/∂y₀ = ∂Wy(y₀, y)/∂y — mixed-derivative reciprocity of the kick."""
        wcc, wss = _synthetic_coupling(
            [_profile(_S)], [0.5 * _profile(_S)]
        )
        a, b = 3e-4, 5e-4
        delta = 5e-6

        def _wy(y: float, y0: float) -> np.ndarray:
            return compute_wake_off_axis(wcc, wss, y0=y0, y=y)["Wy"]

        # vary the source offset y₀ around a, witness fixed at b
        d_source = (_wy(b, a + delta) - _wy(b, a - delta)) / (2.0 * delta)
        # vary the witness offset y around b, source fixed at a
        d_witness = (_wy(a, b + delta) - _wy(a, b - delta)) / (2.0 * delta)
        np.testing.assert_allclose(d_source, d_witness, rtol=1e-2, atol=1e-2)

    def test_wake_reciprocity_parity_source_sign(self) -> None:
        """Off-axis wakes: Wz even and Wy odd in the source offset y₀."""
        wcc, wss = _synthetic_coupling(
            [_profile(_S)], [0.5 * _profile(_S)]
        )
        a = 4e-4
        r_plus = compute_wake_off_axis(wcc, wss, y0=+a, y=0.0)
        r_minus = compute_wake_off_axis(wcc, wss, y0=-a, y=0.0)
        np.testing.assert_allclose(r_plus["Wz"], r_minus["Wz"], rtol=1e-9, atol=1e-12)
        np.testing.assert_allclose(r_plus["Wy"], -r_minus["Wy"], rtol=1e-9, atol=1e-12)


# ---------------------------------------------------------------------------
# 4. Mode orthogonality
# ---------------------------------------------------------------------------


class TestModeOrthogonality:
    @pytest.mark.parametrize("m,n", [(1, 3), (1, 5), (3, 5)])
    def test_mode_orthogonality_cos_cos(self, m: int, n: int) -> None:
        """cos(π m y/D) and cos(π n y/D) are orthogonal with self-norm √(D/2)."""
        y = np.linspace(-_D / 2.0, _D / 2.0, 100_001)
        f = np.cos(np.pi * m * y / _D)
        g = np.cos(np.pi * n * y / _D)
        assert np.trapezoid(f * g, y) == pytest.approx(0.0, abs=1e-6)
        # self-normalization of the cos mode over [−D/2, D/2] is D/2
        assert np.trapezoid(f * f, y) == pytest.approx(_D / 2.0, rel=1e-6)

    @pytest.mark.parametrize("m,n", [(1, 3), (1, 5), (3, 5)])
    def test_mode_orthogonality_sin_sin(self, m: int, n: int) -> None:
        """sin(π m y/D) and sin(π n y/D) are orthogonal with self-norm √(D/2)."""
        y = np.linspace(-_D / 2.0, _D / 2.0, 100_001)
        f = np.sin(np.pi * m * y / _D)
        g = np.sin(np.pi * n * y / _D)
        assert np.trapezoid(f * g, y) == pytest.approx(0.0, abs=1e-6)
        # self-normalization of the sin mode over [−D/2, D/2] is D/2
        assert np.trapezoid(f * f, y) == pytest.approx(_D / 2.0, rel=1e-6)

    @pytest.mark.parametrize("m,n", [(1, 1), (1, 3), (3, 5)])
    def test_mode_orthogonality_cos_sin_cross(self, m: int, n: int) -> None:
        """cos and sin modes are mutually orthogonal (different parity)."""
        y = np.linspace(-_D / 2.0, _D / 2.0, 100_001)
        f = np.cos(np.pi * m * y / _D)
        g = np.sin(np.pi * n * y / _D)
        assert np.trapezoid(f * g, y) == pytest.approx(0.0, abs=1e-6)


# ---------------------------------------------------------------------------
# 5. cosh / sinh transverse scaling
# ---------------------------------------------------------------------------


class TestCoshSinhScaling:
    def test_cosh_sinh_scaling_wz_cosh2(self) -> None:
        """Pure-Wcc: Wz(y, y) = Wz(0, 0)·cosh²(k y) (source at the witness)."""
        k = _K1
        prof = _profile(_S)
        wcc, wss = _synthetic_coupling([prof], [np.zeros_like(_S)])
        wz_00 = compute_wake_off_axis(wcc, wss, y0=0.0, y=0.0)["Wz"]
        for y in (2e-4, 4e-4, 6e-4, 8e-4):
            wz_yy = compute_wake_off_axis(wcc, wss, y0=y, y=y)["Wz"]
            np.testing.assert_allclose(
                wz_yy, wz_00 * np.cosh(k * y) ** 2, rtol=1e-9, atol=1e-12
            )

    def test_cosh_sinh_scaling_wz_sinh2(self) -> None:
        """Pure-Wss: Wz(y, y)/sinh²(k y) is constant and Wz(0, 0) = 0."""
        k = _K1
        prof = _profile(_S)
        wcc, wss = _synthetic_coupling([np.zeros_like(_S)], [prof])
        ratios = []
        for y in (2e-4, 4e-4, 6e-4, 8e-4):
            wz_yy = compute_wake_off_axis(wcc, wss, y0=y, y=y)["Wz"]
            ratios.append(wz_yy / np.sinh(k * y) ** 2)
        for r in ratios[1:]:
            np.testing.assert_allclose(r, ratios[0], rtol=1e-9, atol=1e-12)
        wz_00 = compute_wake_off_axis(wcc, wss, y0=0.0, y=0.0)["Wz"]
        assert np.max(np.abs(wz_00)) == pytest.approx(0.0, abs=1e-12)


# ---------------------------------------------------------------------------
# 6. Kick factor sign convention
# ---------------------------------------------------------------------------


class TestKickFactorSign:
    def test_kick_factor_sign_convention_defocusing_positive(self) -> None:
        """k_⊥ = +∫λ·W_⊥ ds > 0 for a defocusing (positive) transverse wake."""
        s = np.linspace(-2e-3, 2e-3, 401)
        sigma_b, W0 = 3e-4, 2.5
        lam = gauss(s, sigma_b)  # normalized PDF (∫λ ds = 1)
        w_perp = +W0 * np.ones_like(s)  # defocusing transverse wake
        w_raw = -w_perp  # round-geometry raw integral is the negation of W_⊥

        kick_phys = np.trapezoid(lam * w_perp, s)
        assert kick_phys == pytest.approx(W0, rel=1e-3)  # ∫λ ds = 1
        assert kick_phys > 0.0

        # code convention: kick = loss_shape(bunch, w_raw) = −∫λ·w_raw ds
        kick_code = loss_shape(
            np.column_stack([s, lam]), np.column_stack([s, w_raw])
        )[0]
        assert kick_code == pytest.approx(kick_phys, rel=1e-3)
        assert kick_code == pytest.approx(-np.trapezoid(lam * w_raw, s), rel=1e-3)
        assert kick_code > 0.0

    def test_kick_factor_sign_convention_focusing_negative_and_round_pipeline(self) -> None:
        """Focusing wakes give negative kicks; the round-dipole pipeline recovers k=+∫λ·W_⊥ds."""
        s = np.linspace(-2e-3, 2e-3, 401)
        hs = s[1] - s[0]
        sigma_b, W0 = 3e-4, 1.5
        lam = gauss(s, sigma_b)

        # --- focusing case ---
        w_perp = -W0 * np.ones_like(s)  # focusing transverse wake
        kick_code = loss_shape(
            np.column_stack([s, lam]), np.column_stack([s, -w_perp])
        )[0]
        assert kick_code == pytest.approx(-W0, rel=1e-3)
        assert kick_code < 0.0

        # --- round-geometry dipole pipeline (process_wake_dipole convention) ---
        # W_trans_raw = IntegrTr(W_long dipole mode);  W_trans = −W_trans_raw
        w_long = 6e3 * _profile(s)  # synthetic dipole longitudinal mode [V/pC/m²]
        w_trans_raw = integr_tr(hs, w_long)
        w_trans = -w_trans_raw
        kick = loss_shape(
            np.column_stack([s, lam]), np.column_stack([s, w_trans_raw])
        )[0]
        np.testing.assert_allclose(
            kick, np.trapezoid(lam * w_trans, s), rtol=1e-9
        )
        assert kick == pytest.approx(-np.trapezoid(lam * w_trans_raw, s), rel=1e-9)
