"""Targeted tests for :class:`pyecho.postprocess.core.PostProcessor`.

These complement the geometry-dispatcher tests in
``tests/test_postprocess_wakes.py`` by exercising the uncovered paths of the
``core`` module: geometry detection from raw ``wakeL`` files, magn-only and
elec-only recta pipelines, off-axis magn fallback, field-monitor dispatch,
particle loading / ASTRA conversion, and the ``process_all`` failure
tolerances.

Synthetic ECHO2D output trees (``round/``, ``magn/``, ``elec/``,
``magn_*/``, ``elec_*/``) are written to ``tmp_path`` with real file names so
the real :class:`OutputLoader` / parser code paths run.  ``OutputLoader`` /
downstream functions are mocked only where the test targets ``core.py``'s own
dispatch logic rather than the parser internals.
"""

from __future__ import annotations

import struct
from unittest import mock

import numpy as np
import pytest

from pyecho.errors import MissingOutputError, PostProcessError
from pyecho.parser import OutputLoader
from pyecho.postprocess import PostProcessor

# ---------------------------------------------------------------------------
# Synthetic-data constants (mirror tests/test_postprocess_wakes.py)
# ---------------------------------------------------------------------------

SIGMA = 0.005
SIGMA_W = 0.010
HR = 0.001
OFFSET = 2
D = 0.02
N_S = 501
N_RADIAL = 5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _s_grid(n: int = N_S, s0: float = -0.05, s1: float = 0.05) -> np.ndarray:
    return np.linspace(s0, s1, n)


def _gauss_wake(s: np.ndarray, A: float = 1.0, sigma: float = SIGMA_W) -> np.ndarray:
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
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{hr} {offset}", f"{D_val} {sigma}"]
    lines += [f"{si:.16e} {wi:.16e}" for si, wi in zip(s, w)]
    path.write_text("\n".join(lines) + "\n")


def _gaussian_iz(s: np.ndarray, n_radial: int = N_RADIAL) -> np.ndarray:
    """Iz0 profile matrix: every radial column holds gauss(s, SIGMA)/1e9."""
    from pyecho.mathlib.gauss import gauss

    lam = gauss(s, SIGMA) / 1e9
    return np.column_stack([lam] * n_radial)


def _make_round_tree(
    tmp_path,
    *,
    s: np.ndarray | None = None,
    w0: np.ndarray | None = None,
    w1: np.ndarray | None = None,
    with_iz: bool = True,
):
    """Build ``tmp_path/round/`` with wakeL_00/01 (optional) + Iz0.txt."""
    s = _s_grid() if s is None else s
    rdir = tmp_path / "round"
    rdir.mkdir(parents=True, exist_ok=True)
    if w0 is not None:
        _write_wake_file(rdir / "wakeL_00.txt", HR, OFFSET, D, SIGMA, s, w0)
    if w1 is not None:
        _write_wake_file(rdir / "wakeL_01.txt", HR, OFFSET, D, SIGMA, s, w1)
    if with_iz:
        np.savetxt(rdir / "Iz0.txt", np.column_stack([s, _gaussian_iz(s)]), fmt="%.18e")
    return rdir


def _make_recta_tree(
    tmp_path,
    *,
    s: np.ndarray | None = None,
    wcc_amps: list[float] | None = None,
    wss_amps: list[float] | None = None,
):
    """Build ``tmp_path/magn/`` and ``tmp_path/elec/`` with odd-mode wakeL files."""
    s = _s_grid() if s is None else s
    dy = OFFSET * HR
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
            denom = np.cosh(dy * k) if parity == "cosh" else np.sinh(dy * k)
            raw = w * (denom ** 2)
            _write_wake_file(d / f"wakeL_{m:02d}.txt", HR, OFFSET, D, SIGMA, s, raw)
        np.savetxt(d / "Iz0.txt", np.column_stack([s] + [np.zeros_like(s)] * N_RADIAL), fmt="%.18e")
    return tmp_path


def _write_particles_out(path, n: int = 5, q0: float = 1.0e-11) -> None:
    """Write a valid ECHO2D ``particles.out`` binary (component-major)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    coords = np.linspace(0.0, 1.0, 6 * n).reshape(6, n)
    status = np.zeros(n, dtype=np.int64)
    raw = struct.pack("<dd", float(n), q0)
    raw += coords.astype(np.float64).tobytes()
    raw += status.tobytes()
    path.write_bytes(raw)


# ===========================================================================
# Construction & geometry detection
# ===========================================================================


class TestGeometryDetection:
    """``_detect_geometry`` — round / recta / unknown from directory layout."""

    def test_init_accepts_string_path(self, tmp_path):
        s = _s_grid()
        _make_round_tree(tmp_path, w0=_gauss_wake(s, A=1.0) / 1e-3,
                         w1=_gauss_wake(s, A=0.5) / 1e-3)
        pp = PostProcessor(str(tmp_path))  # str, not Path
        assert isinstance(pp.loader, OutputLoader)
        assert pp.loader.dir == tmp_path.resolve()
        assert pp.geometry_type == "round"

    def test_init_accepts_outputloader_instance(self, tmp_path):
        """An existing OutputLoader instance is reused without re-wrapping."""
        s = _s_grid()
        _make_round_tree(tmp_path, w0=_gauss_wake(s, A=1.0) / 1e-3,
                         w1=_gauss_wake(s, A=0.5) / 1e-3)
        loader = OutputLoader(tmp_path)
        pp = PostProcessor(loader)
        assert pp.loader is loader
        assert pp.geometry_type == "round"

    def test_detect_round_from_wakeL00_in_data_dir(self, tmp_path):
        """wakeL_00.txt directly in the directory (no round/ subdir) -> round."""
        s = _s_grid()
        _write_wake_file(tmp_path / "wakeL_00.txt", HR, OFFSET, D, SIGMA, s,
                         _gauss_wake(s, A=1.0))
        pp = PostProcessor(tmp_path)
        assert pp.geometry_type == "round"

    def test_detect_recta_from_wakeL01_with_wcc(self, tmp_path):
        """wakeL_01.txt + Wcc_odd.txt in data dir -> recta."""
        s = _s_grid()
        _write_wake_file(tmp_path / "wakeL_01.txt", HR, OFFSET, D, SIGMA, s,
                         _gauss_wake(s, A=1.0))
        (tmp_path / "Wcc_odd.txt").write_text("0\n")
        pp = PostProcessor(tmp_path)
        assert pp.geometry_type == "recta"

    def test_detect_round_from_wakeL01_only(self, tmp_path):
        """wakeL_01.txt without Wcc/magn/elec markers -> round."""
        s = _s_grid()
        _write_wake_file(tmp_path / "wakeL_01.txt", HR, OFFSET, D, SIGMA, s,
                         _gauss_wake(s, A=1.0))
        pp = PostProcessor(tmp_path)
        assert pp.geometry_type == "round"

    def test_detect_recta_from_prefixed_subdirs(self, tmp_path):
        """magn_*/elec_* prefix subdirectories are recognised as recta."""
        s = _s_grid()
        _write_wake_file(tmp_path / "magn_condition" / "wakeL_01.txt",
                         HR, OFFSET, D, SIGMA, s, _gauss_wake(s, A=1.0))
        _write_wake_file(tmp_path / "elec_condition" / "wakeL_01.txt",
                         HR, OFFSET, D, SIGMA, s, _gauss_wake(s, A=0.5))
        pp = PostProcessor(tmp_path)
        assert pp.geometry_type == "recta"


# ===========================================================================
# Recta pipelines — partial (magn-only / elec-only) & error paths
# ===========================================================================


class TestProcessRectaWake:
    """``process_recta_wake`` magn/elec resolution and partial pipelines."""

    def test_recta_wake_on_round_raises(self, tmp_path):
        s = _s_grid()
        _make_round_tree(tmp_path, w0=_gauss_wake(s, A=1.0) / 1e-3)
        pp = PostProcessor(tmp_path)
        assert pp.geometry_type == "round"
        with pytest.raises(PostProcessError, match="requires recta"):
            pp.process_recta_wake()

    def test_magn_only_partial_pipeline(self, tmp_path):
        """Loader pointed at a magn/ dir itself -> magn-only Wlong+Wquad."""
        s = _s_grid()
        magn = tmp_path / "magn"
        _write_wake_file(magn / "wakeL_01.txt", HR, OFFSET, D, SIGMA, s,
                         _gauss_wake(s, A=1.0))
        pp = PostProcessor(magn)
        assert pp.geometry_type == "recta"
        res = pp.process_recta_wake()
        assert res["wcc"] is not None
        assert res["wss"] is None
        assert res["Wdipole"].shape == res["Wlong"].shape
        assert np.all(res["Wdipole"] == 0.0)
        assert "Wquad" in res

    def test_elec_only_partial_pipeline(self, tmp_path):
        """Loader pointed at an elec/ dir itself -> elec-only Wdipole."""
        s = _s_grid()
        elec = tmp_path / "elec"
        _write_wake_file(elec / "wakeL_01.txt", HR, OFFSET, D, SIGMA, s,
                         _gauss_wake(s, A=1.0))
        pp = PostProcessor(elec)
        assert pp.geometry_type == "recta"
        res = pp.process_recta_wake()
        assert res["wcc"] is None
        assert res["wss"] is not None
        assert "Wdipole" in res
        assert np.all(res["Wlong"] == 0.0)
        assert np.all(res["Wquad"] == 0.0)

    def test_neither_magn_nor_elec_raises(self, tmp_path):
        """Both magn/ and elec/ unresolvable -> MissingOutputError."""
        s = _s_grid()
        _make_round_tree(tmp_path, w0=_gauss_wake(s, A=1.0) / 1e-3)
        pp = PostProcessor(tmp_path)
        pp._effective_type = "recta"  # type: ignore[attr-defined]
        pp._magn_dir = None  # type: ignore[attr-defined]
        pp._elec_dir = None  # type: ignore[attr-defined]
        elec_named = tmp_path / "elec"
        plain = tmp_path / "plain"
        # First _resolve_data_dir() call (magn fallback) returns an "elec"-named
        # path -> magn_dir becomes None; second call returns a non-elec path
        # -> elec_dir becomes None too.
        with mock.patch.object(
            pp.loader, "_resolve_data_dir", side_effect=[elec_named, plain]
        ):
            with pytest.raises(MissingOutputError):
                pp.process_recta_wake()


# ===========================================================================
# Off-axis wakes
# ===========================================================================


class TestOffAxis:
    """``process_off_axis`` — geometry guard and magn-dir fallback."""

    def test_off_axis_on_round_raises(self, tmp_path):
        s = _s_grid()
        _make_round_tree(tmp_path, w0=_gauss_wake(s, A=1.0) / 1e-3)
        pp = PostProcessor(tmp_path)
        with pytest.raises(PostProcessError, match="recta"):
            pp.process_off_axis(y0=0.0, y=0.0)

    def test_off_axis_magn_fallback(self, tmp_path):
        """elec/ subdir only -> magn/ falls back to the resolved data dir."""
        s = _s_grid()
        elec = tmp_path / "elec"
        _write_wake_file(elec / "wakeL_01.txt", HR, OFFSET, D, SIGMA, s,
                         _gauss_wake(s, A=1.0))
        _write_wake_file(elec / "wakeL_03.txt", HR, OFFSET, D, SIGMA, s,
                         _gauss_wake(s, A=0.5))
        pp = PostProcessor(tmp_path)
        assert pp.geometry_type == "recta"
        res = pp.process_off_axis(y0=0.001, y=0.002, n_modes_cc=2, n_modes_ss=2)
        assert res["Wz"].shape == (len(s),)
        assert res["Wy"].shape == (len(s),)
        assert res["D"] == pytest.approx(D)


# ===========================================================================
# Field monitors
# ===========================================================================


class TestFieldMonitor:
    """``process_field_monitor`` and ``synthesize_total_field`` dispatch."""

    def test_field_monitor_missing_raises(self, tmp_path):
        s = _s_grid()
        _make_round_tree(tmp_path, w0=_gauss_wake(s, A=1.0) / 1e-3)
        pp = PostProcessor(tmp_path)
        with mock.patch.object(pp.loader, "load_monitor", return_value=None):
            with pytest.raises(MissingOutputError):
                pp.process_field_monitor(mode=0, monitor_id=1)

    def test_field_monitor_dispatch(self, tmp_path):
        s = _s_grid()
        _make_round_tree(tmp_path, w0=_gauss_wake(s, A=1.0) / 1e-3)
        pp = PostProcessor(tmp_path)
        fake_monitor = mock.MagicMock()
        sentinel = {"component": "Ez", "coords": [], "field": np.array([1.0]), "point": {}}
        with mock.patch.object(pp.loader, "load_monitor", return_value=fake_monitor), \
             mock.patch("pyecho.postprocess.fields.process_field_monitor",
                        return_value=sentinel) as m:
            res = pp.process_field_monitor(mode=2, monitor_id=3, point_t=0.5)
        assert res == sentinel
        m.assert_called_once_with(fake_monitor, point_t=0.5, point_z=None, point_r=None)

    def test_synthesize_total_field_dispatch(self, tmp_path):
        s = _s_grid()
        _make_round_tree(tmp_path, w0=_gauss_wake(s, A=1.0) / 1e-3)
        pp = PostProcessor(tmp_path)
        arr = np.zeros((3, 5))
        with mock.patch("pyecho.postprocess.fields.synthesize_total_field_from_loader",
                        return_value=arr) as m:
            out = pp.synthesize_total_field(component="Ey", monitor_id=2,
                                            x0=0.1, x=0.2, n_modes=3)
        assert out is arr
        m.assert_called_once()
        # No magn/ subdir and no _magn_dir -> falls back to the resolved data dir.
        assert m.call_args.kwargs["magn_dir"] == tmp_path / "round"


# ===========================================================================
# Particles & ASTRA conversion
# ===========================================================================


class TestParticles:
    """``load_particles`` and ``convert_to_astra``."""

    def test_load_particles_missing_raises(self, tmp_path):
        s = _s_grid()
        _make_round_tree(tmp_path, w0=_gauss_wake(s, A=1.0) / 1e-3)
        pp = PostProcessor(tmp_path)
        with pytest.raises(MissingOutputError):
            pp.load_particles()

    def test_load_particles_parses_and_statistics(self, tmp_path):
        s = _s_grid()
        _make_round_tree(tmp_path, w0=_gauss_wake(s, A=1.0) / 1e-3)
        _write_particles_out(tmp_path / "round" / "particles.out")
        pp = PostProcessor(tmp_path)
        res = pp.load_particles()
        assert set(res) == {"particles", "statistics"}
        assert res["particles"]["Np"] == 5
        assert res["particles"]["q0"] == pytest.approx(1.0e-11)
        assert res["statistics"]["n_active"] == 5
        assert res["statistics"]["n_lost"] == 0
        assert "emit_x" in res["statistics"]

    def test_convert_to_astra_missing_raises(self, tmp_path):
        s = _s_grid()
        _make_round_tree(tmp_path, w0=_gauss_wake(s, A=1.0) / 1e-3)
        pp = PostProcessor(tmp_path)
        with pytest.raises(MissingOutputError):
            pp.convert_to_astra(tmp_path / "out.astra")

    def test_convert_to_astra_writes_file(self, tmp_path):
        s = _s_grid()
        _make_round_tree(tmp_path, w0=_gauss_wake(s, A=1.0) / 1e-3)
        _write_particles_out(tmp_path / "round" / "particles.out", n=5)
        pp = PostProcessor(tmp_path)
        out = tmp_path / "converted.astra"
        n_written = pp.convert_to_astra(out, total_charge=5.0e-11)
        assert n_written == 5
        assert out.exists()
        # Header int32 + 5 × 108-byte ASTRA records.
        assert out.stat().st_size == 4 + 5 * 108


# ===========================================================================
# process_all dispatch & failure tolerance
# ===========================================================================


class TestProcessAll:
    """``process_all`` — dispatch and per-step failure tolerance."""

    def test_round_calls_monopole_and_dipole(self, tmp_path):
        s = _s_grid()
        dy = (OFFSET + 0.5) * HR
        _make_round_tree(
            tmp_path, s=s,
            w0=_gauss_wake(s, A=1.0) / 1e-3,
            w1=_gauss_wake(s, A=0.5) * dy ** 2 / 1e-3,
        )
        pp = PostProcessor(tmp_path)
        with mock.patch.object(pp, "process_wake_monopole",
                               wraps=pp.process_wake_monopole) as m0, \
             mock.patch.object(pp, "process_wake_dipole",
                               wraps=pp.process_wake_dipole) as m1:
            res = pp.process_all()
        assert m0.call_count == 1
        assert m1.call_count == 1
        assert res["monopole"] is not None
        assert res["dipole"] is not None

    def test_round_monopole_failure_keeps_dipole(self, tmp_path):
        """Missing wakeL_00 -> monopole step fails, dipole still produced."""
        s = _s_grid()
        dy = (OFFSET + 0.5) * HR
        _make_round_tree(
            tmp_path, s=s,
            w1=_gauss_wake(s, A=0.5) * dy ** 2 / 1e-3,
        )
        pp = PostProcessor(tmp_path)
        assert pp.geometry_type == "round"
        res = pp.process_all()
        assert res["monopole"] is None
        assert res["dipole"] is not None

    def test_round_dipole_failure_keeps_monopole(self, tmp_path):
        """Missing wakeL_01 -> dipole step fails, monopole still produced."""
        s = _s_grid()
        _make_round_tree(tmp_path, s=s, w0=_gauss_wake(s, A=1.0) / 1e-3)
        pp = PostProcessor(tmp_path)
        res = pp.process_all()
        assert res["monopole"] is not None
        assert res["dipole"] is None

    def test_recta_calls_recta_wake(self, tmp_path):
        s = _s_grid()
        _make_recta_tree(tmp_path, s=s, wcc_amps=[1.0, 0.5], wss_amps=[0.3, 0.2])
        pp = PostProcessor(tmp_path)
        assert pp.geometry_type == "recta"
        with mock.patch.object(pp, "process_recta_wake",
                               wraps=pp.process_recta_wake) as m:
            res = pp.process_all()
        assert m.call_count == 1
        assert res["recta_wake"] is not None
        assert "Wdipole" in res["recta_wake"]

    def test_recta_synthesis_failure_tolerated(self, tmp_path):
        s = _s_grid()
        _make_recta_tree(tmp_path, s=s, wcc_amps=[1.0, 0.5], wss_amps=[0.3, 0.2])
        pp = PostProcessor(tmp_path)
        with mock.patch.object(pp.loader, "list_monitors", return_value=[(1, 1)]), \
             mock.patch.object(pp, "synthesize_total_field",
                               side_effect=RuntimeError("synthesis boom")):
            res = pp.process_all()
        assert res["recta_wake"] is not None
        assert "total_field" not in res

    def test_particles_failure_tolerated(self, tmp_path):
        s = _s_grid()
        _make_round_tree(
            tmp_path, s=s,
            w0=_gauss_wake(s, A=1.0) / 1e-3,
            w1=_gauss_wake(s, A=0.5) / 1e-3,
        )
        (tmp_path / "round" / "particles.out").write_bytes(b"\x00" * 32)
        pp = PostProcessor(tmp_path)
        with mock.patch.object(pp, "load_particles",
                               side_effect=RuntimeError("particle boom")):
            res = pp.process_all()
        assert res["monopole"] is not None
        assert "particles" not in res

    def test_all_steps_failed_raises(self, tmp_path):
        s = _s_grid()
        _make_round_tree(
            tmp_path, s=s,
            w0=_gauss_wake(s, A=1.0) / 1e-3,
            w1=_gauss_wake(s, A=0.5) / 1e-3,
        )
        pp = PostProcessor(tmp_path)
        with mock.patch.object(pp, "process_wake_monopole",
                               side_effect=RuntimeError("m0")), \
             mock.patch.object(pp, "process_wake_dipole",
                               side_effect=RuntimeError("m1")):
            with pytest.raises(PostProcessError, match="All postprocessing steps failed"):
                pp.process_all()
