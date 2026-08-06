"""Tests for the ECHO2D wake post-processing pipeline.

Covers :mod:`pyecho.postprocess.wakes.round` (monopole / dipole wakes,
unit conversions, offset->dy convention, loss / kick factors) and
:mod:`pyecho.postprocess.wakes.recta` (Wcc/Wss assembly, Wlong/Wquad/
Wdipole computation, off-axis ZY wakes, Tm/Tq/Td wakes), plus the
:class:`pyecho.postprocess.core.PostProcessor` geometry dispatcher.

Synthetic data is generated with numpy: Gaussian bunch profiles and
Gaussian wake potentials on uniform ``s`` grids, written to ``tmp_path``
file trees (``round/``, ``magn/``, ``elec/``) in the exact format
produced by ECHO2D (``wakeL_XX.txt`` + ``Iz0.txt``) so the real
:class:`OutputLoader` / :func:`parse_wake_file` code paths are exercised.
"""

from __future__ import annotations

import numpy as np
import pytest

from pyecho.datamodel import WakeResult
from pyecho.errors import MissingOutputError, ParserError, PostProcessError
from pyecho.mathlib.gauss import gauss
from pyecho.mathlib.integration import integr_tr
from pyecho.parser import OutputLoader
from pyecho.postprocess import PostProcessor
from pyecho.postprocess.wakes.recta import (
    _clamp_mode_count,
    _truncation_error,
    assemble_wcc,
    assemble_wss,
    compute_wake_long_quad,
    compute_wake_long_quad_dipole,
    compute_wake_off_axis,
    compute_wake_tm_tq_td,
    compute_wake_zy,
    process_recta_wake,
)
from pyecho.postprocess.wakes.round import process_wake_dipole, process_wake_monopole

# ---------------------------------------------------------------------------
# Synthetic-data constants
# ---------------------------------------------------------------------------

#: Bunch RMS length [m] (also written into the wakeL header "D sigma" line).
SIGMA = 0.005
#: RMS width of the Gaussian wake potential [m].
SIGMA_W = 0.010
#: Transverse mesh step [m].
HR = 0.001
#: Bunch offset in mesh lines.
OFFSET = 2
#: Total structure width [m] (= Width, recta only).
D = 0.02
#: Number of longitudinal grid points.
N_S = 501
#: Number of radial columns in Iz0.txt (must exceed OFFSET + 1).
N_RADIAL = 5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _s_grid(n: int = N_S, s0: float = -0.05, s1: float = 0.05) -> np.ndarray:
    """Uniform longitudinal grid from *s0* to *s1*."""
    return np.linspace(s0, s1, n)


def _gauss_wake(s: np.ndarray, A: float = 1.0, sigma: float = SIGMA_W) -> np.ndarray:
    """Gaussian wake potential (unnormalised) for analytic reference tests."""
    return A * np.exp(-(s ** 2) / (2.0 * sigma * sigma))


def _write_wake_file(
    path,
    hr: float,
    offset: int,
    D_val: float,
    sigma: float,
    s: np.ndarray,
    w: np.ndarray,
) -> None:
    """Write a ``wakeL_XX.txt`` file in the ECHO2D format."""
    lines = [f"{hr} {offset}", f"{D_val} {sigma}"]
    lines += [f"{si:.16e} {wi:.16e}" for si, wi in zip(s, w)]
    path.write_text("\n".join(lines) + "\n")


def _gaussian_iz(s: np.ndarray, n_radial: int = N_RADIAL) -> np.ndarray:
    """Iz0 profile matrix: every radial column holds gauss(s, SIGMA)/1e9.

    The pipeline multiplies the selected column by 1e9, so the bunch
    recovered on the wake grid is exactly ``gauss(s, SIGMA)``.
    """
    lam = gauss(s, SIGMA) / 1e9
    return np.column_stack([lam] * n_radial)


def _make_round_tree(
    tmp_path,
    *,
    s: np.ndarray | None = None,
    offset: int = OFFSET,
    hr: float = HR,
    sigma: float = SIGMA,
    w0: np.ndarray | None = None,
    w1: np.ndarray | None = None,
    iz_profiles: np.ndarray | None = None,
):
    """Build ``tmp_path/round/`` with wakeL_00/01 and optional Iz0.txt."""
    s = _s_grid() if s is None else s
    rdir = tmp_path / "round"
    rdir.mkdir(parents=True, exist_ok=True)
    if w0 is not None:
        _write_wake_file(rdir / "wakeL_00.txt", hr, offset, D, sigma, s, w0)
    if w1 is not None:
        _write_wake_file(rdir / "wakeL_01.txt", hr, offset, D, sigma, s, w1)
    if iz_profiles is not None:
        np.savetxt(rdir / "Iz0.txt", np.column_stack([s, iz_profiles]), fmt="%.18e")
    return rdir


def _coupling_matrix(
    D_val: float,
    s: np.ndarray,
    amps: list[float],
    sigma_w: float = SIGMA_W,
) -> np.ndarray:
    """Build a Wcc/Wss coupling matrix directly (no files needed).

    Row 0: ``[D, s_0, ..., s_{ns-1}]``; row *i*: ``[k_i, A_i*W(s)]`` with
    :math:`k_i = \\pi(2i-1)/D`.
    """
    ns = len(s)
    n_modes = len(amps)
    matrix: np.ndarray = np.zeros((n_modes + 1, ns + 1), dtype=np.float64)
    matrix[0, 0] = D_val
    matrix[0, 1:] = s
    for i, A in enumerate(amps, start=1):
        k = np.pi * (2 * i - 1) / D_val
        matrix[i, 0] = k
        matrix[i, 1:] = A * np.exp(-(s ** 2) / (2.0 * sigma_w * sigma_w))
    return matrix


def _make_recta_tree(
    tmp_path,
    *,
    s: np.ndarray | None = None,
    offset: int = OFFSET,
    hr: float = HR,
    sigma: float = SIGMA,
    wcc_amps: list[float] | None = None,
    wss_amps: list[float] | None = None,
    n_radial: int = N_RADIAL,
):
    """Build ``tmp_path/magn/`` and ``tmp_path/elec/`` with odd-mode wakeL files.

    Raw wakes are written pre-normalised (``W_raw = W_desired / f(dy*k)^2``)
    so that :func:`assemble_wcc` / :func:`assemble_wss` recover exactly the
    desired Gaussian mode wakes.
    """
    s = _s_grid() if s is None else s
    dy = offset * hr
    for sub, parity, amps in (
        ("magn", "cosh", wcc_amps),
        ("elec", "sinh", wss_amps),
    ):
        if amps is None:
            continue
        d = tmp_path / sub
        d.mkdir(parents=True, exist_ok=True)
        for i, A in enumerate(amps, start=1):
            m = 2 * i - 1
            k = np.pi * m / D
            w = A * np.exp(-(s ** 2) / (2.0 * SIGMA_W * SIGMA_W))
            # assemble_wcc/wss divide by f(dy*k)^2 themselves, so write the
            # raw wake pre-multiplied by that factor to recover `w` exactly.
            denom = np.cosh(dy * k) if parity == "cosh" else np.sinh(dy * k)
            raw = w * (denom ** 2)
            _write_wake_file(d / f"wakeL_{m:02d}.txt", hr, offset, D, sigma, s, raw)
        iz = np.column_stack([s] + [gauss(s, sigma) / 1e9] * n_radial)
        np.savetxt(d / "Iz0.txt", iz, fmt="%.18e")
    return tmp_path


# ===========================================================================
# Round geometry — monopole (m=0)
# ===========================================================================


class TestRoundMonopole:
    """``process_wake_monopole`` — loss factor, units, shift, bunch."""

    def test_loss_factor_matches_analytic(self, tmp_path):
        """Loss factor equals -sum(lambda*W)*h for a Gaussian bunch/wake."""
        s = _s_grid()
        W = _gauss_wake(s, A=3.5)
        _make_round_tree(
            tmp_path, s=s, w0=W / 1e-3, iz_profiles=_gaussian_iz(s),
        )
        res = process_wake_monopole(OutputLoader(tmp_path))
        hs = s[1] - s[0]
        loss_ref = -np.sum(gauss(s, SIGMA) * W) * hs
        assert res.loss_factor == pytest.approx(loss_ref, rel=1e-8)
        assert isinstance(res, WakeResult)

    def test_unit_conversion_mv_nc_to_v_pc(self, tmp_path):
        """W_raw (m·V/nC) x 1e-3 == W (V/pC)."""
        s = _s_grid()
        W = _gauss_wake(s, A=2.0)
        W_raw = W / 1e-3
        _make_round_tree(tmp_path, s=s, w0=W_raw, iz_profiles=_gaussian_iz(s))
        res = process_wake_monopole(OutputLoader(tmp_path))
        assert np.allclose(res.W, W_raw * 1e-3)
        assert res.units == "V/pC"
        assert res.label == "m=0 monopole"

    def test_shift_sigma_centers_bunch(self, tmp_path):
        """s_shifted = s - (5*sigma - 0.5*hs)."""
        s = _s_grid()
        hs = s[1] - s[0]
        _make_round_tree(
            tmp_path, s=s, w0=_gauss_wake(s, A=1.0) / 1e-3,
            iz_profiles=_gaussian_iz(s),
        )
        res = process_wake_monopole(OutputLoader(tmp_path))
        assert np.allclose(res.s, s - (5.0 * SIGMA - 0.5 * hs))

    def test_shift_sigma_disabled(self, tmp_path):
        """shift_sigma=False leaves the s-coordinate untouched."""
        s = _s_grid()
        _make_round_tree(
            tmp_path, s=s, w0=_gauss_wake(s, A=1.0) / 1e-3,
            iz_profiles=_gaussian_iz(s),
        )
        res = process_wake_monopole(OutputLoader(tmp_path), shift_sigma=False)
        assert np.allclose(res.s, s)

    def test_bunch_profile_equals_gaussian(self, tmp_path):
        """The recovered bunch profile matches gauss(s, SIGMA)."""
        s = _s_grid()
        _make_round_tree(
            tmp_path, s=s, w0=_gauss_wake(s, A=1.0) / 1e-3,
            iz_profiles=_gaussian_iz(s),
        )
        res = process_wake_monopole(OutputLoader(tmp_path))
        assert np.allclose(res.bunch, gauss(s, SIGMA))

    def test_offset_selects_iz_column(self, tmp_path):
        """bunch column = Iz_2d[:, offset+1] (MATLAB Iz(:, offset+3))."""
        s = _s_grid()
        # Constant profiles: column j (0-indexed) holds value j+1.
        profiles = np.column_stack(
            [np.full(len(s), j + 1) for j in range(N_RADIAL)]
        )
        offset = 1  # col_idx = offset + 1 = 2 -> column value 3
        _make_round_tree(
            tmp_path, s=s, offset=offset, w0=_gauss_wake(s, A=1.0) / 1e-3,
            iz_profiles=profiles,
        )
        res = process_wake_monopole(OutputLoader(tmp_path))
        assert np.allclose(res.bunch, 3.0e9)

    def test_offset_column_clamped_when_out_of_range(self, tmp_path):
        """offset beyond the Iz0 columns falls back to the last column."""
        s = _s_grid()
        _make_round_tree(
            tmp_path, s=s, offset=5, w0=_gauss_wake(s, A=1.0) / 1e-3,
            iz_profiles=_gaussian_iz(s, n_radial=3),
        )
        res = process_wake_monopole(OutputLoader(tmp_path))
        assert np.allclose(res.bunch, gauss(s, SIGMA))

    def test_no_iz_file_gives_zero_bunch_and_loss(self, tmp_path):
        s = _s_grid()
        _make_round_tree(tmp_path, s=s, w0=_gauss_wake(s, A=1.0) / 1e-3)
        res = process_wake_monopole(OutputLoader(tmp_path))
        assert np.allclose(res.bunch, 0.0)
        assert res.loss_factor == pytest.approx(0.0)

    def test_peak_is_max_abs_wake(self, tmp_path):
        s = _s_grid()
        A = 4.2
        _make_round_tree(
            tmp_path, s=s, w0=_gauss_wake(s, A=A) / 1e-3,
            iz_profiles=_gaussian_iz(s),
        )
        res = process_wake_monopole(OutputLoader(tmp_path))
        assert res.peak == pytest.approx(A, rel=1e-8)

    def test_missing_wake_file_raises(self, tmp_path):
        rdir = tmp_path / "round"
        rdir.mkdir(parents=True)
        _write_wake_file(rdir / "wakeL_01.txt", HR, OFFSET, D, SIGMA,
                         _s_grid(), _gauss_wake(_s_grid(), A=1.0) / 1e-3)
        with pytest.raises(ParserError):
            process_wake_monopole(OutputLoader(tmp_path))


# ===========================================================================
# Round geometry — dipole (m=1)
# ===========================================================================


class TestRoundDipole:
    """``process_wake_dipole`` — dy convention, kick factor, sign rules."""

    def _tree(self, tmp_path, W_long: np.ndarray, **kw):
        dy = (OFFSET + 0.5) * HR
        w1 = W_long * dy ** 2 / 1e-3
        _make_round_tree(tmp_path, s=_s_grid(), w1=w1, iz_profiles=_gaussian_iz(_s_grid()), **kw)
        return dy

    def test_dy_convention_offset_plus_half(self, tmp_path):
        """dy = (offset + 0.5)*hr, NOT offset*hr, for round geometry."""
        W_long = _gauss_wake(_s_grid(), A=2.0)
        self._tree(tmp_path, W_long)
        res = process_wake_dipole(OutputLoader(tmp_path))
        assert res["dy"] == pytest.approx((OFFSET + 0.5) * HR)
        assert res["sigma"] == pytest.approx(SIGMA)
        # A larger offset changes dy accordingly.
        s = _s_grid()
        dy3 = (5 + 0.5) * HR
        _make_round_tree(
            tmp_path, s=s, offset=5,
            w1=_gauss_wake(s, A=2.0) * dy3 ** 2 / 1e-3,
            iz_profiles=_gaussian_iz(s),
        )
        res = process_wake_dipole(OutputLoader(tmp_path))
        assert res["dy"] == pytest.approx((5 + 0.5) * HR)

    def test_longitudinal_unit_conversion(self, tmp_path):
        """W_long = W_raw x 1e-3 / dy^2."""
        s = _s_grid()
        W_long = _gauss_wake(s, A=2.0)
        dy = self._tree(tmp_path, W_long)
        res = process_wake_dipole(OutputLoader(tmp_path))
        assert np.allclose(res["longitudinal"].W, W_long)
        assert res["longitudinal"].units == "V/pC/m²"
        # Re-derive from the raw file value (W_raw x 1e-3 / dy^2):
        assert np.allclose(
            res["longitudinal"].W,
            _gauss_wake(s, A=2.0) * dy ** 2 / 1e-3 * 1e-3 / dy ** 2,
        )

    def test_transverse_is_negated_integr_tr(self, tmp_path):
        """W_trans = -IntegrTr(hs, W_long)."""
        s = _s_grid()
        W_long = _gauss_wake(s, A=2.0)
        self._tree(tmp_path, W_long)
        res = process_wake_dipole(OutputLoader(tmp_path))
        hs = s[1] - s[0]
        assert np.allclose(res["transverse"].W, -integr_tr(hs, W_long))
        assert res["transverse"].units == "V/pC/m"

    def test_kick_factor_matches_analytic(self, tmp_path):
        """Kick = loss_shape(bunch, +IntegrTr) — pre-negation integral."""
        s = _s_grid()
        W_long = _gauss_wake(s, A=2.0)
        self._tree(tmp_path, W_long)
        res = process_wake_dipole(OutputLoader(tmp_path))
        hs = s[1] - s[0]
        lam = gauss(s, SIGMA)
        kick_ref = -np.sum(lam * integr_tr(hs, W_long)) * hs
        assert res["transverse"].loss_factor == pytest.approx(kick_ref, rel=1e-8)

    def test_longitudinal_loss_matches_analytic(self, tmp_path):
        s = _s_grid()
        W_long = _gauss_wake(s, A=2.0)
        self._tree(tmp_path, W_long)
        res = process_wake_dipole(OutputLoader(tmp_path))
        hs = s[1] - s[0]
        loss_ref = -np.sum(gauss(s, SIGMA) * W_long) * hs
        assert res["longitudinal"].loss_factor == pytest.approx(loss_ref, rel=1e-8)

    def test_kick_uses_pre_negation_wake(self, tmp_path):
        """The stored transverse wake is negated, but the kick factor is
        computed on the *un*-negated cumulative integral (MATLAB order)."""
        s = _s_grid()
        W_long = _gauss_wake(s, A=2.0)
        self._tree(tmp_path, W_long)
        res = process_wake_dipole(OutputLoader(tmp_path))
        hs = s[1] - s[0]
        w_trans_raw = integr_tr(hs, W_long)
        assert np.allclose(res["transverse"].W, -w_trans_raw)
        # Kick from +IntegrTr, not from the negated stored wake:
        kick_raw = -np.sum(gauss(s, SIGMA) * w_trans_raw) * hs
        kick_neg = -np.sum(gauss(s, SIGMA) * (-w_trans_raw)) * hs
        assert res["transverse"].loss_factor == pytest.approx(kick_raw, rel=1e-8)
        assert res["transverse"].loss_factor != pytest.approx(kick_neg)

    def test_result_structure(self, tmp_path):
        W_long = _gauss_wake(_s_grid(), A=2.0)
        self._tree(tmp_path, W_long)
        res = process_wake_dipole(OutputLoader(tmp_path))
        assert set(res) == {"longitudinal", "transverse", "dy", "sigma"}
        assert isinstance(res["longitudinal"], WakeResult)
        assert isinstance(res["transverse"], WakeResult)
        assert res["longitudinal"].label == "m=1 dipole"
        assert res["transverse"].label == "dipole-kick"

    def test_shift_sigma(self, tmp_path):
        s = _s_grid()
        hs = s[1] - s[0]
        W_long = _gauss_wake(s, A=2.0)
        self._tree(tmp_path, W_long)
        res = process_wake_dipole(OutputLoader(tmp_path))
        shift = 5.0 * SIGMA - 0.5 * hs
        assert np.allclose(res["longitudinal"].s, s - shift)
        assert np.allclose(res["transverse"].s, s - shift)

    def test_peak_values(self, tmp_path):
        s = _s_grid()
        W_long = _gauss_wake(s, A=2.0)
        self._tree(tmp_path, W_long)
        res = process_wake_dipole(OutputLoader(tmp_path))
        hs = s[1] - s[0]
        assert res["longitudinal"].peak == pytest.approx(2.0, rel=1e-8)
        assert res["transverse"].peak == pytest.approx(
            np.max(np.abs(integr_tr(hs, W_long))), rel=1e-8)

    def test_no_iz_gives_zero_kick(self, tmp_path):
        s = _s_grid()
        W_long = _gauss_wake(s, A=2.0)
        dy = (OFFSET + 0.5) * HR
        _make_round_tree(tmp_path, s=s, w1=W_long * dy ** 2 / 1e-3)
        res = process_wake_dipole(OutputLoader(tmp_path))
        assert np.allclose(res["transverse"].bunch, 0.0)
        assert res["transverse"].loss_factor == pytest.approx(0.0)


# ===========================================================================
# Recta geometry — Wcc / Wss assembly
# ===========================================================================


class TestRectaAssemble:
    """``assemble_wcc`` / ``assemble_wss`` — shapes and normalisation."""

    def test_wcc_shape(self, tmp_path):
        s = _s_grid()
        _make_recta_tree(tmp_path, s=s, wcc_amps=[1.0, 0.5, 0.25])
        wcc = assemble_wcc(tmp_path / "magn", n_modes=3)
        assert wcc.shape == (4, len(s) + 1)

    def test_wcc_header_row(self, tmp_path):
        s = _s_grid()
        _make_recta_tree(tmp_path, s=s, wcc_amps=[1.0])
        wcc = assemble_wcc(tmp_path / "magn", n_modes=1)
        assert wcc[0, 0] == pytest.approx(D)
        assert np.allclose(wcc[0, 1:], s)

    def test_wcc_normalization(self, tmp_path):
        """wcc rows = raw / cosh(dy*k)^2, recovering the desired wakes."""
        s = _s_grid()
        amps = [1.0, 0.5, 0.25]
        dy = OFFSET * HR
        _make_recta_tree(tmp_path, s=s, wcc_amps=amps)
        wcc = assemble_wcc(tmp_path / "magn", n_modes=3)
        for i, A in enumerate(amps, start=1):
            expected = A * np.exp(-(s ** 2) / (2.0 * SIGMA_W ** 2))
            assert np.allclose(wcc[i, 1:], expected)

    def test_wcc_k_values(self, tmp_path):
        """k_i = pi*(2i-1)/D."""
        s = _s_grid()
        _make_recta_tree(tmp_path, s=s, wcc_amps=[1.0, 0.5, 0.25])
        wcc = assemble_wcc(tmp_path / "magn", n_modes=3)
        for i in range(1, 4):
            assert wcc[i, 0] == pytest.approx(np.pi * (2 * i - 1) / D)

    def test_wss_normalization(self, tmp_path):
        """wss rows = raw / sinh(dy*k)^2."""
        s = _s_grid()
        amps = [0.3, 0.2, 0.1]
        dy = OFFSET * HR
        _make_recta_tree(tmp_path, s=s, wss_amps=amps)
        wss = assemble_wss(tmp_path / "elec", n_modes=3)
        for i, A in enumerate(amps, start=1):
            k = np.pi * (2 * i - 1) / D
            expected = A * np.exp(-(s ** 2) / (2.0 * SIGMA_W ** 2))
            assert np.allclose(wss[i, 1:], expected)
            assert wss[i, 0] == pytest.approx(k)

    def test_wss_centered_zero(self, tmp_path):
        """Centered beam (offset=0) -> sinh(0)=0 -> all mode rows zero."""
        s = _s_grid()
        _make_recta_tree(tmp_path, s=s, offset=0, wss_amps=[1.0])
        wss = assemble_wss(tmp_path / "elec", n_modes=1)
        assert np.allclose(wss[1, 1:], 0.0)
        assert wss[1, 0] == pytest.approx(np.pi / D)

    def test_missing_mode_zero_filled(self, tmp_path):
        """A missing odd-mode file yields a zero-filled matrix row."""
        s = _s_grid()
        _make_recta_tree(tmp_path, s=s, wcc_amps=[1.0, 0.5])  # only m=1,3
        wcc = assemble_wcc(tmp_path / "magn", n_modes=3)
        assert wcc.shape == (4, len(s) + 1)
        assert np.allclose(wcc[3, 1:], 0.0)  # m=5 absent
        assert wcc[3, 0] == pytest.approx(np.pi * 5 / D)

    def test_missing_wake01_raises(self, tmp_path):
        (tmp_path / "magn").mkdir(parents=True)
        with pytest.raises(FileNotFoundError):
            assemble_wcc(tmp_path / "magn")

    def test_missing_directory_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            assemble_wcc(tmp_path / "does_not_exist")


# ===========================================================================
# Recta geometry — Wlong / Wquad (PP_WakeLQ)
# ===========================================================================


class TestRectaLongQuad:
    """``compute_wake_long_quad`` — dimensions and formulas."""

    def _wcc(self):
        return _coupling_matrix(D, _s_grid(), [1.0, 0.5, 0.25])

    def test_shapes_and_keys(self):
        s = _s_grid()
        res = compute_wake_long_quad(self._wcc())
        assert res["s"].shape == (len(s),)
        assert res["Wlong"].shape == (len(s),)
        assert res["Wquad"].shape == (len(s),)
        assert res["D"] == pytest.approx(D)
        assert res["k_values"].shape == (3,)

    def test_wlong_formula(self):
        """Wlong = sum_i Wcc_i * (2/D) * 1e-3."""
        s = _s_grid()
        wcc = self._wcc()
        res = compute_wake_long_quad(wcc)
        expected = wcc[1:4, 1:].sum(axis=0) * (2.0 / D) * 1e-3
        assert np.allclose(res["Wlong"], expected)

    def test_wquad_formula(self):
        """Wquad = -IntegrTr(hs, sum k_i^2*Wcc_i) * (2/D) * 1e-6."""
        s = _s_grid()
        wcc = self._wcc()
        res = compute_wake_long_quad(wcc)
        hs = s[1] - s[0]
        wq_sum = np.zeros(len(s))
        for i in range(1, 4):
            wq_sum += wcc[i, 0] ** 2 * wcc[i, 1:]
        expected = -integr_tr(hs, wq_sum) * (2.0 / D) * 1e-6
        assert np.allclose(res["Wquad"], expected)

    def test_wquad_starts_at_zero(self):
        res = compute_wake_long_quad(self._wcc())
        assert res["Wquad"][0] == pytest.approx(0.0)

    def test_k_values(self):
        res = compute_wake_long_quad(self._wcc())
        assert np.allclose(
            res["k_values"], np.array([np.pi / D, 3 * np.pi / D, 5 * np.pi / D])
        )

    def test_n_modes_clamped(self):
        """n_modes above the available rows is clamped."""
        wcc = self._wcc()
        res = compute_wake_long_quad(wcc, n_modes=10)
        assert res["k_values"].shape == (3,)
        assert np.allclose(res["Wlong"], wcc[1:4, 1:].sum(axis=0) * (2.0 / D) * 1e-3)

    def test_single_mode(self):
        s = _s_grid()
        wcc = self._wcc()
        res = compute_wake_long_quad(wcc, n_modes=1)
        hs = s[1] - s[0]
        assert np.allclose(res["Wlong"], wcc[1, 1:] * (2.0 / D) * 1e-3)
        assert np.allclose(
            res["Wquad"],
            -integr_tr(hs, wcc[1, 0] ** 2 * wcc[1, 1:]) * (2.0 / D) * 1e-6,
        )


# ===========================================================================
# Recta geometry — Wlong / Wquad / Wdipole (PP_WakeLQD)
# ===========================================================================


class TestRectaLongQuadDipole:
    """``compute_wake_long_quad_dipole`` — dipole wake and consistency."""

    def _mats(self):
        s = _s_grid()
        wcc = _coupling_matrix(D, s, [1.0, 0.5, 0.25])
        wss = _coupling_matrix(D, s, [0.3, 0.2, 0.1])
        return s, wcc, wss

    def test_shapes_and_keys(self):
        s, wcc, wss = self._mats()
        res = compute_wake_long_quad_dipole(wcc, wss)
        assert res["Wdipole"].shape == (len(s),)
        assert res["Wlong"].shape == (len(s),)
        assert res["Wquad"].shape == (len(s),)
        assert res["D"] == pytest.approx(D)
        assert res["k_cc"].shape == (3,)
        assert res["k_ss"].shape == (3,)

    def test_wdipole_formula(self):
        """Wdipole = -IntegrTr(hs, sum k_i^2*Wss_i) * (2/D) * 1e-6."""
        s, wcc, wss = self._mats()
        res = compute_wake_long_quad_dipole(wcc, wss)
        hs = s[1] - s[0]
        wd_sum = np.zeros(len(s))
        for i in range(1, 4):
            wd_sum += wss[i, 0] ** 2 * wss[i, 1:]
        expected = -integr_tr(hs, wd_sum) * (2.0 / D) * 1e-6
        assert np.allclose(res["Wdipole"], expected)
        assert res["Wdipole"][0] == pytest.approx(0.0)

    def test_matches_long_quad(self):
        _, wcc, wss = self._mats()
        res = compute_wake_long_quad_dipole(wcc, wss)
        lq = compute_wake_long_quad(wcc, n_modes=3)
        assert np.allclose(res["Wlong"], lq["Wlong"])
        assert np.allclose(res["Wquad"], lq["Wquad"])
        assert np.allclose(res["s"], lq["s"])

    def test_mismatched_columns_raises(self):
        s, wcc, _ = self._mats()
        wss_short = _coupling_matrix(D, s[:100], [0.3, 0.2, 0.1])
        with pytest.raises(ValueError):
            compute_wake_long_quad_dipole(wcc, wss_short)

    def test_mode_caps(self):
        s, wcc, wss = self._mats()
        res = compute_wake_long_quad_dipole(wcc, wss, n_modes_cc=2, n_modes_ss=1)
        hs = s[1] - s[0]
        k = wss[1, 0]
        expected = -integr_tr(hs, k ** 2 * wss[1, 1:]) * (2.0 / D) * 1e-6
        assert np.allclose(res["Wdipole"], expected)
        assert res["k_cc"].shape == (2,)
        assert res["k_ss"].shape == (1,)


# ===========================================================================
# Recta geometry — off-axis Wz / Wy (PP_WakeZY)
# ===========================================================================


class TestRectaZY:
    """``compute_wake_zy`` / ``compute_wake_off_axis`` — 2-D maps."""

    def _mats(self):
        s = _s_grid()
        wcc = _coupling_matrix(D, s, [1.0, 0.5, 0.25])
        wss = _coupling_matrix(D, s, [0.3, 0.2, 0.1])
        return s, wcc, wss

    def test_2d_map_shapes(self):
        s, wcc, wss = self._mats()
        y_offsets = np.array([0.0, 0.001, 0.002])
        res = compute_wake_zy(wcc, wss, y_offsets, y0=0.0)
        assert res["Wz"].shape == (3, len(s))
        assert res["Wy"].shape == (3, len(s))
        assert np.allclose(res["y_offsets"], y_offsets)
        assert res["s"].shape == (len(s),)
        assert res["D"] == pytest.approx(D)

    def test_on_axis_wz_sum_wcc(self):
        """On axis Wz = sum_i Wcc_i * (2/D) * 1e-3."""
        s, wcc, wss = self._mats()
        res = compute_wake_zy(wcc, wss, np.array([0.0]), y0=0.0)
        expected = wcc[1:4, 1:].sum(axis=0) * (2.0 / D) * 1e-3
        assert np.allclose(res["Wz"][0], expected)

    def test_on_axis_wy_zero(self):
        """On axis the transverse wake vanishes (sinh(0)=0)."""
        _, wcc, wss = self._mats()
        res = compute_wake_zy(wcc, wss, np.array([0.0]), y0=0.0)
        assert np.allclose(res["Wy"][0], 0.0)

    def test_off_axis_formula(self):
        """Wz/Wy match the cosh/sinh modal sum analytically."""
        s, wcc, wss = self._mats()
        y, y0 = 0.0015, 0.001
        res = compute_wake_zy(wcc, wss, np.array([y]), y0=y0)
        hs = s[1] - s[0]
        wz_ref = np.zeros(len(s))
        fy_ref = np.zeros(len(s))
        for i in range(3):
            k = wcc[i + 1, 0]
            wcc_i, wss_i = wcc[i + 1, 1:], wss[i + 1, 1:]
            chy, shy = np.cosh(k * y), np.sinh(k * y)
            chy0, shy0 = np.cosh(k * y0), np.sinh(k * y0)
            wz_ref += wcc_i * chy * chy0 + wss_i * shy * shy0
            fy_ref += k * (wcc_i * shy * chy0 + wss_i * chy * shy0)
        wz_ref *= (2.0 / D) * 1e-3
        wy_ref = -integr_tr(hs, fy_ref) * (2.0 / D) * 1e-3
        assert np.allclose(res["Wz"][0], wz_ref)
        assert np.allclose(res["Wy"][0], wy_ref)

    def test_mismatched_s_grid_raises(self):
        s, wcc, wss = self._mats()
        wcc_bad = wcc.copy()
        wcc_bad[0, 1:] = s + 1e-6
        with pytest.raises(ValueError):
            compute_wake_zy(wcc_bad, wss, np.array([0.0]), y0=0.0)

    def test_offsets_not_1d_raises(self):
        _, wcc, wss = self._mats()
        with pytest.raises(ValueError):
            compute_wake_zy(wcc, wss, np.zeros((2, 2)), y0=0.0)

    def test_no_modes_raises(self):
        s = _s_grid()
        wcc0 = np.zeros((1, len(s) + 1))
        wcc0[0, 0] = D
        wcc0[0, 1:] = s
        wss0 = wcc0.copy()
        with pytest.raises(ValueError):
            compute_wake_zy(wcc0, wss0, np.array([0.0]), y0=0.0)

    def test_off_axis_matches_zy_single(self):
        """compute_wake_off_axis == compute_wake_zy with y_offsets=[y]."""
        s, wcc, wss = self._mats()
        y, y0 = 0.0015, 0.001
        res1 = compute_wake_off_axis(wcc, wss, y0, y)
        res2 = compute_wake_zy(wcc, wss, np.array([y]), y0=y0)
        assert np.allclose(res1["Wz"], res2["Wz"][0])
        assert np.allclose(res1["Wy"], res2["Wy"][0])
        assert np.allclose(res1["s"], res2["s"])
        assert res1["D"] == pytest.approx(res2["D"])
        assert np.allclose(res1["k_cc"], res2["k_cc"])
        assert np.allclose(res1["k_ss"], res2["k_ss"])


# ===========================================================================
# Recta geometry — Tm / Tq / Td wakes (PP_WakeL_Tm_Tq_Td)
# ===========================================================================


class TestRectaTmTqTd:
    """``compute_wake_tm_tq_td`` — on-axis / off-axis monopole/quad/dipole."""

    def _mats(self):
        s = _s_grid()
        wcc = _coupling_matrix(D, s, [1.0, 0.5, 0.25])
        wss = _coupling_matrix(D, s, [0.3, 0.2, 0.1])
        return s, wcc, wss

    def test_result_keys(self):
        _, wcc, wss = self._mats()
        res = compute_wake_tm_tq_td(wcc, wss)
        for key in (
            "s", "D", "y0", "y", "Wlong", "Tm", "Tq", "Td",
            "Wm", "Wquad", "Wdipole", "Fm", "FQ", "FD",
            "k_cc", "k_ss",
            "error_long", "error_m", "error_quad", "error_dipole",
        ):
            assert key in res

    def test_on_axis_tm_zero(self):
        """Tm vanishes on axis (sinh(0)=0)."""
        s, wcc, wss = self._mats()
        res = compute_wake_tm_tq_td(wcc, wss, y0=0.0, y=0.0)
        assert np.allclose(res["Tm"], 0.0)
        assert np.allclose(res["Wm"], 0.0)
        assert res["Tm"].shape == (len(s),)

    def test_on_axis_wlong(self):
        """On axis Wlong = sum_i Wcc_i * (2/D) * 1e-3."""
        s, wcc, wss = self._mats()
        res = compute_wake_tm_tq_td(wcc, wss, y0=0.0, y=0.0)
        expected = wcc[1:4, 1:].sum(axis=0) * (2.0 / D) * 1e-3
        assert np.allclose(res["Wlong"], expected)

    def test_on_axis_tq_matches_long_quad(self):
        """On axis Tq equals compute_wake_long_quad's Wquad."""
        _, wcc, wss = self._mats()
        res = compute_wake_tm_tq_td(wcc, wss, y0=0.0, y=0.0)
        lq = compute_wake_long_quad(wcc, n_modes=3)
        assert np.allclose(res["Tq"], lq["Wquad"])

    def test_on_axis_td_matches_dipole(self):
        """On axis Td equals compute_wake_long_quad_dipole's Wdipole."""
        _, wcc, wss = self._mats()
        res = compute_wake_tm_tq_td(wcc, wss, y0=0.0, y=0.0)
        lqd = compute_wake_long_quad_dipole(wcc, wss, n_modes_cc=3, n_modes_ss=3)
        assert np.allclose(res["Td"], lqd["Wdipole"])

    def test_off_axis_formula(self):
        """Wlong/Tm/Tq/Td match the analytic modal-sum formulas."""
        s, wcc, wss = self._mats()
        y, y0 = 0.0015, 0.001
        res = compute_wake_tm_tq_td(wcc, wss, y0=y0, y=y)
        hs = s[1] - s[0]
        wl_ref = np.zeros(len(s))
        fm_sum = np.zeros(len(s))
        fq_sum = np.zeros(len(s))
        fd_sum = np.zeros(len(s))
        for i in range(3):
            k = wcc[i + 1, 0]
            wcc_i, wss_i = wcc[i + 1, 1:], wss[i + 1, 1:]
            chy, shy = np.cosh(k * y), np.sinh(k * y)
            chy0, shy0 = np.cosh(k * y0), np.sinh(k * y0)
            dW = wcc_i * chy * chy0 + wss_i * shy * shy0
            ddy = wcc_i * shy * chy0 + wss_i * chy * shy0
            wl_ref += dW
            fm_sum += k * ddy
            fq_sum += k ** 2 * dW
            fd_sum += k ** 2 * (wcc_i * shy * shy0 + wss_i * chy * chy0)
        wl_ref *= (2.0 / D) * 1e-3
        tm_ref = -integr_tr(hs, fm_sum) * (2.0 / D) * 1e-3
        tq_ref = -integr_tr(hs, fq_sum) * (2.0 / D) * 1e-6
        td_ref = -integr_tr(hs, fd_sum) * (2.0 / D) * 1e-6
        assert np.allclose(res["Wlong"], wl_ref)
        assert np.allclose(res["Tm"], tm_ref)
        assert np.allclose(res["Tq"], tq_ref)
        assert np.allclose(res["Td"], td_ref)
        assert res["y0"] == pytest.approx(y0)
        assert res["y"] == pytest.approx(y)

    def test_matlab_aliases(self):
        _, wcc, wss = self._mats()
        res = compute_wake_tm_tq_td(wcc, wss)
        assert np.allclose(res["Wm"], res["Tm"])
        assert np.allclose(res["Wquad"], res["Tq"])
        assert np.allclose(res["Wdipole"], res["Td"])

    def test_modal_terms_shape(self):
        s, wcc, wss = self._mats()
        res = compute_wake_tm_tq_td(wcc, wss)
        assert res["Fm"].shape == (3, len(s))
        assert res["FQ"].shape == (3, len(s))
        assert res["FD"].shape == (3, len(s))
        assert res["k_cc"].shape == (3,)
        assert res["k_ss"].shape == (3,)

    def test_error_terms_non_negative(self):
        _, wcc, wss = self._mats()
        res = compute_wake_tm_tq_td(wcc, wss)
        for key in ("error_long", "error_m", "error_quad", "error_dipole"):
            assert res[key] >= 0.0

    def test_mismatched_s_grid_raises(self):
        s, wcc, wss = self._mats()
        wcc_bad = wcc.copy()
        wcc_bad[0, 1:] = s + 1e-6
        with pytest.raises(ValueError):
            compute_wake_tm_tq_td(wcc_bad, wss)


# ===========================================================================
# Recta geometry — full pipeline (process_recta_wake)
# ===========================================================================


class TestProcessRectaWake:
    """``process_recta_wake`` — full magn+elec pipeline with loss factors."""

    def test_full_keys(self, tmp_path):
        _make_recta_tree(
            tmp_path, wcc_amps=[1.0, 0.5, 0.25], wss_amps=[0.3, 0.2, 0.1],
        )
        res = process_recta_wake(
            tmp_path / "magn", tmp_path / "elec", n_modes_cc=3, n_modes_ss=3,
        )
        for key in (
            "wcc", "wss", "s", "Wlong", "Wquad", "Wdipole", "D",
            "k_cc", "k_ss", "bunch", "loss_long", "loss_quad", "loss_dipole",
        ):
            assert key in res
        s = _s_grid()
        assert np.allclose(res["bunch"], gauss(s, SIGMA))
        assert res["wcc"].shape == (4, len(s) + 1)
        assert res["wss"].shape == (4, len(s) + 1)
        assert res["D"] == pytest.approx(D)

    def test_loss_factors_match_analytic(self, tmp_path):
        """loss_long/quad/dipole match -sum(bunch * (+/-)wake)*h."""
        _make_recta_tree(
            tmp_path, wcc_amps=[1.0, 0.5, 0.25], wss_amps=[0.3, 0.2, 0.1],
        )
        res = process_recta_wake(
            tmp_path / "magn", tmp_path / "elec", n_modes_cc=3, n_modes_ss=3,
        )
        s = _s_grid()
        hs = s[1] - s[0]
        lam = gauss(s, SIGMA)
        loss_long_ref = -np.sum(lam * res["Wlong"]) * hs
        loss_quad_ref = -np.sum(lam * (-res["Wquad"])) * hs
        loss_dipole_ref = -np.sum(lam * (-res["Wdipole"])) * hs
        assert res["loss_long"] == pytest.approx(loss_long_ref, rel=1e-8)
        assert res["loss_quad"] == pytest.approx(loss_quad_ref, rel=1e-8)
        assert res["loss_dipole"] == pytest.approx(loss_dipole_ref, rel=1e-8)

    def test_magn_only_pipeline(self, tmp_path):
        """Without elec_dir only Wlong/Wquad are produced."""
        _make_recta_tree(tmp_path, wcc_amps=[1.0, 0.5])
        res = process_recta_wake(tmp_path / "magn", elec_dir=None, n_modes_cc=2)
        assert res["wss"] is None
        assert "Wdipole" not in res
        assert "loss_dipole" not in res
        assert "loss_long" in res
        s = _s_grid()
        assert res["Wlong"].shape == (len(s),)
        assert res["Wquad"].shape == (len(s),)

    def test_no_iz_skips_loss(self, tmp_path):
        """Missing Iz0.txt -> bunch is None and loss keys are absent."""
        _make_recta_tree(tmp_path, wcc_amps=[1.0], wss_amps=[0.3])
        (tmp_path / "magn" / "Iz0.txt").unlink()
        res = process_recta_wake(
            tmp_path / "magn", tmp_path / "elec", n_modes_cc=1, n_modes_ss=1,
        )
        assert res["bunch"] is None
        assert "loss_long" not in res


# ===========================================================================
# PostProcessor — geometry detection & dispatch
# ===========================================================================


class TestPostProcessor:
    """Geometry auto-detection and round/recta dispatch."""

    def test_round_detection(self, tmp_path):
        s = _s_grid()
        _make_round_tree(
            tmp_path, s=s, w0=_gauss_wake(s, A=1.0) / 1e-3,
            iz_profiles=_gaussian_iz(s),
        )
        pp = PostProcessor(tmp_path)
        assert pp.geometry_type == "round"

    def test_recta_detection(self, tmp_path):
        _make_recta_tree(tmp_path, wcc_amps=[1.0, 0.5], wss_amps=[0.3, 0.2])
        pp = PostProcessor(tmp_path)
        assert pp.geometry_type == "recta"

    def test_round_monopole_dispatch(self, tmp_path):
        s = _s_grid()
        _make_round_tree(
            tmp_path, s=s, w0=_gauss_wake(s, A=1.0) / 1e-3,
            iz_profiles=_gaussian_iz(s),
        )
        pp = PostProcessor(tmp_path)
        res = pp.process_wake_monopole()
        assert res.units == "V/pC"
        assert res.label == "m=0 monopole"

    def test_round_dipole_dispatch(self, tmp_path):
        s = _s_grid()
        dy = (OFFSET + 0.5) * HR
        _make_round_tree(
            tmp_path, s=s, w0=_gauss_wake(s, A=1.0) / 1e-3,
            w1=_gauss_wake(s, A=0.5) * dy ** 2 / 1e-3,
            iz_profiles=_gaussian_iz(s),
        )
        pp = PostProcessor(tmp_path)
        res = pp.process_wake_dipole()
        assert set(res) == {"longitudinal", "transverse", "dy", "sigma"}

    def test_monopole_on_recta_raises(self, tmp_path):
        _make_recta_tree(tmp_path, wcc_amps=[1.0], wss_amps=[0.3])
        pp = PostProcessor(tmp_path)
        assert pp.geometry_type == "recta"
        with pytest.raises(PostProcessError):
            pp.process_wake_monopole()

    def test_dipole_on_recta_raises(self, tmp_path):
        _make_recta_tree(tmp_path, wcc_amps=[1.0], wss_amps=[0.3])
        pp = PostProcessor(tmp_path)
        with pytest.raises(PostProcessError):
            pp.process_wake_dipole()

    def test_recta_pipeline_auto_modes(self, tmp_path):
        _make_recta_tree(tmp_path, wcc_amps=[1.0, 0.5], wss_amps=[0.3, 0.2])
        pp = PostProcessor(tmp_path)
        res = pp.process_recta_wake()  # n_modes auto-detected from files
        assert res["wcc"].shape == (3, len(_s_grid()) + 1)
        assert "Wdipole" in res

    def test_recta_off_axis(self, tmp_path):
        _make_recta_tree(tmp_path, wcc_amps=[1.0, 0.5], wss_amps=[0.3, 0.2])
        pp = PostProcessor(tmp_path)
        res = pp.process_off_axis(y0=0.001, y=0.002, n_modes_cc=2, n_modes_ss=2)
        assert res["Wz"].shape == (len(_s_grid()),)
        assert res["Wy"].shape == (len(_s_grid()),)
        assert res["D"] == pytest.approx(D)

    def test_off_axis_missing_elec_raises(self, tmp_path):
        _make_recta_tree(tmp_path, wcc_amps=[1.0, 0.5])  # magn only
        pp = PostProcessor(tmp_path)
        with pytest.raises(MissingOutputError):
            pp.process_off_axis(0.0, 0.0)

    def test_process_all_round(self, tmp_path):
        s = _s_grid()
        dy = (OFFSET + 0.5) * HR
        _make_round_tree(
            tmp_path, s=s, w0=_gauss_wake(s, A=1.0) / 1e-3,
            w1=_gauss_wake(s, A=0.5) * dy ** 2 / 1e-3,
            iz_profiles=_gaussian_iz(s),
        )
        pp = PostProcessor(tmp_path)
        res = pp.process_all()
        assert res["geometry_type"] == "round"
        assert res["monopole"] is not None
        assert res["dipole"] is not None

    def test_process_all_recta(self, tmp_path):
        _make_recta_tree(tmp_path, wcc_amps=[1.0, 0.5], wss_amps=[0.3, 0.2])
        pp = PostProcessor(tmp_path)
        res = pp.process_all()
        assert res["geometry_type"] == "recta"
        assert res["recta_wake"]["Wdipole"] is not None

    def test_process_all_unknown_geometry_raises(self, tmp_path):
        # Some output file exists, but no geometry marker and no wake files.
        (tmp_path / "BeamMomentsMonitor.txt").write_text("0\n")
        pp = PostProcessor(tmp_path)
        assert pp.geometry_type == "unknown"
        with pytest.raises(PostProcessError):
            pp.process_all()

    def test_process_all_empty_dir_raises(self, tmp_path):
        tmp_path.mkdir(parents=True, exist_ok=True)
        pp = PostProcessor(tmp_path)
        with pytest.raises(MissingOutputError):
            pp.process_all()

    def test_postprocessor_nonexistent_dir_raises(self, tmp_path):
        with pytest.raises(ParserError):
            PostProcessor(tmp_path / "missing")


# ===========================================================================
# Error cases & internal helpers
# ===========================================================================


class TestErrors:
    """Mismatched arrays, missing files/directories, empty mode dicts."""

    def test_load_all_wakes_empty_dict(self, tmp_path):
        """A directory with no wakeL files yields an empty mode dict."""
        (tmp_path / "round").mkdir(parents=True)
        loader = OutputLoader(tmp_path)
        assert loader.load_all_wakes() == {}

    def test_load_all_wakes_populated(self, tmp_path):
        s = _s_grid()
        _make_round_tree(
            tmp_path, s=s, w0=_gauss_wake(s, A=1.0) / 1e-3,
            w1=_gauss_wake(s, A=0.5) / 1e-3,
        )
        loader = OutputLoader(tmp_path)
        wakes = loader.load_all_wakes()
        assert set(wakes) == {0, 1}

    def test_outputloader_nonexistent_dir_raises(self, tmp_path):
        with pytest.raises(ParserError):
            OutputLoader(tmp_path / "does_not_exist")

    def test_process_recta_empty_magn_raises(self, tmp_path):
        """Empty magn/ directory -> wakeL_01.txt missing -> FileNotFoundError."""
        (tmp_path / "magn").mkdir(parents=True)
        pp = PostProcessor(tmp_path)
        with pytest.raises(FileNotFoundError):
            pp.process_recta_wake()

    def test_truncation_error_zero_denominator(self):
        assert _truncation_error(3, np.zeros(5), np.zeros(5)) == 0.0

    def test_truncation_error_positive(self):
        last = np.array([1.0, 2.0, 3.0])
        allm = np.array([[1.0, 0.0, 0.0], [0.0, 2.0, 0.0], [0.0, 0.0, 3.0]])
        # Nm * sum(last^2) / sum(all^2) * 100
        expected = 3.0 * np.sum(last ** 2) / np.sum(allm ** 2) * 100.0
        assert _truncation_error(3, last, allm) == pytest.approx(expected)

    def test_clamp_mode_count(self):
        assert _clamp_mode_count(None, 7) == 7
        assert _clamp_mode_count(3, 7) == 3
        assert _clamp_mode_count(10, 7) == 7
        assert _clamp_mode_count(0, 7) == 0
