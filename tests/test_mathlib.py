"""Tests for the :mod:`pyecho.mathlib` numerical utilities.

Covers the five submodules:

* :mod:`pyecho.mathlib.gauss`        — Gaussian / normal distribution
* :mod:`pyecho.mathlib.fft`          — wake <-> impedance Fourier transforms
* :mod:`pyecho.mathlib.integration`  — IntegrTr / DiffL / Int0 operators
* :mod:`pyecho.mathlib.convolution`  — interp1 + ZaZb impedance convolution
* :mod:`pyecho.mathlib.loss`         — LossShape / LongLoss2 loss factors

All reference values are derived analytically or from ``numpy``; the tests
validate the exact MATLAB-compatible numerical behaviour of each operator.
"""

from __future__ import annotations

import numpy as np
import pytest

from pyecho.mathlib.convolution import _interp1_linear, za_zb
from pyecho.mathlib.fft import _C_LIGHT, impedance2wake, wake2impedance
from pyecho.mathlib.gauss import gauss
from pyecho.mathlib.integration import diff_l, int0, integr_tr
from pyecho.mathlib.loss import long_loss2, long_loss2_cm, loss_shape


# ---------------------------------------------------------------------------
# gauss
# ---------------------------------------------------------------------------


class TestGauss:
    def test_gauss_normalization(self) -> None:
        """A normalised Gaussian integrates to 1 over the real line."""
        x = np.linspace(-5.0, 5.0, 100_001)
        area = np.trapezoid(gauss(x, 1.0), x)
        assert area == pytest.approx(1.0, abs=1e-3)

    def test_gauss_peak(self) -> None:
        """Peak value at the origin equals 1 / (sigma * sqrt(2*pi))."""
        sigma = 0.7
        expected = 1.0 / (sigma * np.sqrt(2.0 * np.pi))
        assert gauss(np.array([0.0]), sigma)[0] == pytest.approx(expected)

    def test_gauss_symmetry(self) -> None:
        """Gaussian is even: g(x) == g(-x)."""
        x = np.linspace(-3.0, 3.0, 101)
        assert np.allclose(gauss(x, 0.5), gauss(-x, 0.5))

    def test_gauss_sigma_scaling(self) -> None:
        """Doubling sigma halves amplitude and doubles the width."""
        x = np.linspace(-4.0, 4.0, 101)
        assert np.allclose(gauss(x, 2.0), 0.5 * gauss(x / 2.0, 1.0))

    def test_gauss_zero_sigma(self) -> None:
        """sigma == 0 produces NaN / inf without raising."""
        with np.errstate(divide="ignore", invalid="ignore"):
            y = gauss(np.array([-1.0, 0.0, 1.0]), 0.0)
        assert np.all(np.isnan(y) | np.isinf(y))

    def test_gauss_output_shape(self) -> None:
        """Output shape matches the input x array shape."""
        x = np.linspace(-1.0, 1.0, 37)
        assert gauss(x, 0.3).shape == x.shape
        x2d = np.zeros((4, 5))
        assert gauss(x2d, 1.0).shape == (4, 5)


# ---------------------------------------------------------------------------
# fft
# ---------------------------------------------------------------------------


class TestFft:
    def test_wake2impedance_shapes(self) -> None:
        """wake2impedance returns frequency and impedance of length n."""
        n = 128
        s = np.linspace(0.0, 1e-3, n)
        w = gauss(s - 0.5e-3, 1e-4)
        f, y = wake2impedance(s, w)
        assert f.shape == (n,)
        assert y.shape == (n,)
        assert np.iscomplexobj(y)

    def test_impedance2wake_shapes(self) -> None:
        """impedance2wake returns coordinate and wake of length n."""
        n = 128
        s = np.linspace(0.0, 1e-3, n)
        f, y = wake2impedance(s, gauss(s - 0.5e-3, 1e-4))
        s2, w2 = impedance2wake(f, y)
        assert s2.shape == (n,)
        assert w2.shape == (n,)

    def test_roundtrip_gaussian(self) -> None:
        """wake -> impedance -> wake recovers a Gaussian wake exactly."""
        s = np.linspace(-0.5e-3, 0.5e-3, 256)
        w = gauss(s, 1e-4)
        f, y = wake2impedance(s, w)
        _, w2 = impedance2wake(f, y)
        assert np.allclose(w2, w, atol=1e-12)

    def test_roundtrip_sine(self) -> None:
        """wake -> impedance -> wake recovers an oscillatory wake."""
        s = np.linspace(0.0, 1e-3, 256)
        w = np.sin(2.0 * np.pi * 5e3 * s) * np.exp(-((s - 0.5e-3) ** 2) / 2e-8)
        f, y = wake2impedance(s, w)
        _, w2 = impedance2wake(f, y)
        assert np.allclose(w2, w, atol=1e-12)

    def test_wake2impedance_complex(self) -> None:
        """A real, non-symmetric wake yields a complex impedance."""
        s = np.linspace(0.0, 1e-3, 128)
        w = gauss(s - 0.3e-3, 1e-4)  # off-centre -> non-even spectrum
        _, y = wake2impedance(s, w)
        assert np.max(np.abs(y.imag)) > 1e-10

    def test_impedance2wake_real(self) -> None:
        """impedance2wake always returns a real-valued wake."""
        s = np.linspace(0.0, 1e-3, 128)
        f, y = wake2impedance(s, gauss(s - 0.5e-3, 1e-4))
        _, w2 = impedance2wake(f, y)
        assert np.isrealobj(w2)

    def test_frequency_grid_consistency(self) -> None:
        """Frequency grid follows f_k = k / (N * dt)."""
        n = 101
        s = np.linspace(0.0, 1e-3, n)
        w = gauss(s - 0.5e-3, 1e-4)
        dt = (s[1] - s[0]) / _C_LIGHT
        f, _ = wake2impedance(s, w)
        expected = np.arange(n) / (dt * n)
        assert f[0] == 0.0
        assert np.allclose(f, expected)
        assert np.allclose(f[1] - f[0], 1.0 / (dt * n))


# ---------------------------------------------------------------------------
# integration
# ---------------------------------------------------------------------------


class TestIntegration:
    def test_integr_tr_constant(self) -> None:
        """Integrating a constant c yields c * h * [0, 1, 2, ...]."""
        h = 0.1
        x = 3.0 * np.ones(5)
        y = integr_tr(h, x)
        assert np.allclose(y, h * 3.0 * np.arange(5))

    def test_integr_tr_zero(self) -> None:
        """Integrating zero yields all zeros."""
        y = integr_tr(0.1, np.zeros(7))
        assert np.allclose(y, 0.0)

    def test_integr_tr_shape(self) -> None:
        """Output has same length, starts at 0, is non-decreasing."""
        x = np.array([1.0, 2.0, 4.0, 8.0, 16.0])
        y = integr_tr(0.5, x)
        assert y.shape == x.shape
        assert y[0] == 0.0
        assert np.all(np.diff(y) >= 0.0)

    def test_diff_l_constant(self) -> None:
        """Differentiating a constant yields all zeros."""
        y = diff_l(1.0, 3.0 * np.ones(6))
        assert np.allclose(y, 0.0)

    def test_diff_l_linear(self) -> None:
        """Alternating-sign difference of a linear ramp: [0, 2a/h, 0, ...]."""
        x = 5.0 * np.arange(6, dtype=np.float64)
        y = diff_l(1.0, x)
        assert np.allclose(y, np.array([0.0, 10.0, 0.0, 10.0, 0.0, 10.0]))

    def test_diff_l_output(self) -> None:
        """Output has same length and zero first element."""
        x = np.array([1.0, 3.0, 6.0, 10.0])
        y = diff_l(2.0, x)
        assert y.shape == x.shape
        assert y[0] == 0.0

    def test_int0_constant(self) -> None:
        """Integrating a constant c over [a, b] gives c * (b - a)."""
        x = np.linspace(0.0, 2.0, 5)
        y = 4.0 * np.ones_like(x)
        assert int0(x, y) == pytest.approx(8.0)

    def test_int0_linear(self) -> None:
        """Integrating y == x over [0, L] gives L**2 / 2."""
        x = np.linspace(0.0, 2.0, 5)
        assert int0(x, x) == pytest.approx(2.0)

    def test_int0_matches_numpy(self) -> None:
        """int0 equals numpy.trapezoid on a non-uniform grid."""
        x = np.array([0.0, 0.1, 0.4, 0.9, 1.7, 2.0])
        y = np.exp(x)
        assert int0(x, y) == pytest.approx(np.trapezoid(y, x))

    def test_int0_minimal(self) -> None:
        """Two-point input reduces to the trapezoid on a single interval."""
        x = np.array([0.0, 1.0])
        y = np.array([2.0, 4.0])
        assert int0(x, y) == pytest.approx(3.0)


# ---------------------------------------------------------------------------
# convolution
# ---------------------------------------------------------------------------


class TestConvolution:
    def test_interp1_linear_exact(self) -> None:
        """Interpolating at source points reproduces the source values."""
        x = np.array([0.0, 1.0, 2.0, 3.0])
        y = np.array([10.0, 20.0, 30.0, 40.0])
        assert np.allclose(_interp1_linear(x, y, x), y)

    def test_interp1_linear_midpoint(self) -> None:
        """Midpoint queries return the average of the bracketing values."""
        x = np.array([0.0, 1.0, 2.0, 3.0])
        y = np.array([10.0, 20.0, 30.0, 40.0])
        xi = np.array([0.5, 1.5, 2.5])
        assert np.allclose(_interp1_linear(x, y, xi), [15.0, 25.0, 35.0])

    def test_interp1_linear_out_of_bounds(self) -> None:
        """Queries outside the source range return the fill value."""
        x = np.array([0.0, 1.0, 2.0, 3.0])
        y = np.array([10.0, 20.0, 30.0, 40.0])
        xi = np.array([-1.0, 4.0])
        assert np.allclose(_interp1_linear(x, y, xi), [0.0, 0.0])
        assert np.allclose(
            _interp1_linear(x, y, xi, fill_value=7.0), [7.0, 7.0]
        )

    def test_interp1_linear_shape(self) -> None:
        """Output shape matches the query array shape."""
        x = np.array([0.0, 1.0, 2.0, 3.0])
        y = np.array([10.0, 20.0, 30.0, 40.0])
        xi = np.array([[0.5, 1.5], [2.5, 3.0]])
        out = _interp1_linear(x, y, xi)
        assert out.shape == xi.shape
        assert np.allclose(out, [[15.0, 25.0], [35.0, 40.0]])

    def test_za_zb_shape(self) -> None:
        """za_zb returns an (N_b, 1) wake array of finite values."""
        nb = 64
        xb = np.linspace(-1e-3, 1e-3, nb)
        bunch = gauss(xb, 1e-4)
        fz = np.linspace(0.0, 1e13, 64)
        Za0 = np.column_stack(
            [fz, 0.5 * np.ones_like(fz), np.zeros_like(fz)]
        )
        res = za_zb(xb, bunch, Za0)
        assert res.shape == (nb, 1)
        assert np.all(np.isfinite(res))

    def test_za_zb_zero_impedance(self) -> None:
        """Zero impedance yields an identically zero wake."""
        nb = 32
        xb = np.linspace(-1e-3, 1e-3, nb)
        bunch = gauss(xb, 1e-4)
        fz = np.linspace(0.0, 1e12, 32)
        Za0 = np.column_stack([fz, np.zeros_like(fz), np.zeros_like(fz)])
        res = za_zb(xb, bunch, Za0)
        assert np.allclose(res, 0.0)


# ---------------------------------------------------------------------------
# loss
# ---------------------------------------------------------------------------


class TestLoss:
    def test_loss_shape_positive(self) -> None:
        """A purely negative wake gives a positive loss factor."""
        s = np.linspace(0.0, 1e-3, 100)
        bunch = np.column_stack([s, np.ones_like(s)])
        wake = np.column_stack([s, -2.0 * np.ones_like(s)])
        loss, _, _ = loss_shape(bunch, wake)
        assert loss > 0.0

    def test_loss_shape_peak(self) -> None:
        """peak equals the maximum absolute wake value."""
        s = np.array([0.0, 1.0, 2.0])
        bunch = np.column_stack([s, np.ones(3)])
        wake = np.column_stack([s, np.array([-5.0, 1.0, 3.0])])
        _, _, peak = loss_shape(bunch, wake)
        assert peak == 5.0

    def test_loss_shape_loss_factor(self) -> None:
        """Exact loss / spread / peak for a small hand-computed case."""
        s = np.array([0.0, 1.0, 2.0])
        bunch = np.column_stack([s, np.ones(3)])
        wake = np.column_stack([s, np.array([-1.0, -2.0, -3.0])])
        loss, spread, peak = loss_shape(bunch, wake)
        assert loss == pytest.approx(6.0)  # -sum(lambda * W) * h
        assert spread == pytest.approx(np.sqrt(50.0))  # sum((W + loss)^2)
        assert peak == 3.0

    def test_long_loss2_sign(self) -> None:
        """A negative wake gives a positive loss factor."""
        s = np.linspace(-2e-3, 2e-3, 200)
        w = -5.0 * np.ones_like(s)
        loss, _, _ = long_loss2(s, w, 3e-4)
        assert loss > 0.0

    def test_long_loss2_spread(self) -> None:
        """For a linear wake, spread equals sigma of the Gaussian bunch."""
        sigma = 3e-4
        s = np.linspace(-2e-3, 2e-3, 401)
        w = -s  # antisymmetric -> loss ~ 0, spread ~ sigma
        loss, spread, _ = long_loss2(s, w, sigma)
        assert loss == pytest.approx(0.0, abs=1e-12)
        assert spread == pytest.approx(sigma, rel=2e-2)

    def test_long_loss2_bunch(self) -> None:
        """Returned bunch profile is the Gaussian evaluated on s."""
        s = np.linspace(-2e-3, 2e-3, 101)
        sigma = 3e-4
        w = -3.0 * np.ones_like(s)
        _, _, bunch = long_loss2(s, w, sigma)
        assert np.allclose(bunch, gauss(s, sigma))

    def test_long_loss2_cm_conversion(self) -> None:
        """cm interface matches the metre interface after unit conversion."""
        s_cm = np.linspace(-0.2, 0.2, 101)
        w = -3.0 * np.ones_like(s_cm)
        sigma_cm = 0.03
        loss_cm, spread_cm, bunch_cm = long_loss2_cm(s_cm, w, sigma_cm)
        loss_m, spread_m, bunch_m = long_loss2(
            s_cm * 1e-2, w, sigma_cm * 1e-2
        )
        assert loss_cm == pytest.approx(loss_m)
        assert spread_cm == pytest.approx(spread_m)
        assert np.allclose(bunch_cm, bunch_m)
