"""Tests for :mod:`pyecho.api`.

All tests mock :class:`pyecho.runner.ECHO2DRunner` and
:class:`pyecho.postprocess.PostProcessor` so no solver executable or
real ECHO2D output is required.  Synthetic ``wakeL_*.txt`` files (the
format produced by the parser tests) exercise the ``OutputLoader`` path
where the API reads back wake files.

Covered workflows:

- ``quick_simulate`` — basic flow, external geometry copy, geometry
  type → template mapping, temp-dir cleanup, error propagation.
- ``quick_postprocess`` — round (monopole-only), round + dipole, flat
  (recta), auto-detection, and missing output directory.
- ``compare_runs`` — basic monopole comparison, dipole mode, skipping
  failed runs, and the empty-input case.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from pyecho.api import compare_runs, quick_postprocess, quick_simulate
from pyecho.datamodel import (
    RectaWakeResult,
    RoundWakeResult,
    SimulationResult,
    WakeResult,
)
from pyecho.errors import (
    ParserError,
    PostProcessError,
    SimulationCrashedError,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_wake(tmp_path: Path, subdir: str, name: str) -> Path:
    """Write a minimal, well-formed ``wakeL_XX.txt`` file."""
    path = tmp_path / subdir / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "0.001 3\n"
        "0.02 0.005\n"
        "0.0 1.0\n"
        "0.001 0.9\n"
        "0.002 0.8\n"
    )
    return path


def _mono_wake() -> WakeResult:
    """A plausible monopole (m=0) processed wake."""
    return WakeResult(
        s=np.array([0.0, 0.001, 0.002]),
        W=np.array([1.0, 0.9, 0.8]),
        bunch=np.array([0.1, 0.2, 0.3]),
        loss_factor=-0.85,
        rms_spread=0.1,
        peak=1.0,
    )


def _dipole_result() -> dict:
    """A plausible ``process_wake_dipole`` return dict."""
    return {
        "longitudinal": WakeResult(
            s=np.array([0.0, 0.001, 0.002]),
            W=np.array([5.0, 4.0, 3.0]),
            bunch=np.zeros(3),
            loss_factor=-4.5,
            rms_spread=1.0,
            peak=5.0,
        ),
        "transverse": WakeResult(
            s=np.array([0.0, 0.001, 0.002]),
            W=np.array([0.5, 0.4, 0.3]),
            bunch=np.zeros(3),
            loss_factor=0.25,
            rms_spread=1.0,
            peak=0.5,
        ),
        "dy": 0.001,
        "sigma": 0.001,
    }


def _recta_result() -> dict:
    """A plausible ``process_recta_wake`` return dict (post-fix: includes
    bunch-weighted loss/kick keys set by _add_bunch_and_loss_factors)."""
    return {
        "s": np.array([0.0, 0.001]),
        "Wlong": np.array([1.0, 0.8]),
        "Wquad": np.array([0.5, 0.4]),
        "Wdipole": np.array([0.2, 0.1]),
        "loss_long": -0.5 * 1.8 * 0.001,    # -∫Wlong·ds via trapezoidal (= bunch-weighted for uniform bunch)
        "loss_quad": -0.5 * 0.9 * 0.001,     # -∫Wquad·ds
        "loss_dipole": -0.5 * 0.3 * 0.001,   # -∫Wdipole·ds
        "wcc": np.eye(1),
        "wss": np.eye(1),
    }


def _make_fake_postprocessor(
    geometry_type: str = "round",
    dipole: dict | None = None,
    recta: dict | None = None,
    fail_dirs: frozenset[str] = frozenset(),
):
    """Build a configurable stand-in for ``PostProcessor``.

    The fake accepts either an ``OutputLoader`` (as used by
    ``quick_postprocess``) or a directory path (as used by
    ``compare_runs``) as its constructor argument.
    """

    geo_type = geometry_type

    class _FakePP:
        geometry_type = geo_type

        def __init__(self, loader_or_dir=None) -> None:
            self.loader = loader_or_dir
            self._key = str(loader_or_dir) if loader_or_dir is not None else ""

        def process_wake_monopole(self):
            if self._key in fail_dirs:
                raise PostProcessError(f"monopole failed for {self._key}")
            return _mono_wake()

        def process_wake_dipole(self):
            return dipole if dipole is not None else _dipole_result()

        def process_recta_wake(self):
            return recta if recta is not None else _recta_result()

    return _FakePP


def _fake_mkdtemp_for(tmp_path: Path, name: str):
    """Return an ``mkdtemp`` stand-in that creates *tmp_path/name*."""
    target = tmp_path / name

    def _fake_mkdtemp(prefix: str = "echo2d_") -> str:
        target.mkdir(parents=True, exist_ok=True)
        return str(target)

    return _fake_mkdtemp


# ---------------------------------------------------------------------------
# quick_simulate
# ---------------------------------------------------------------------------

def test_quick_simulate_basic_flow(tmp_path: Path, monkeypatch) -> None:
    """Runner is constructed with the temp dir + executable and run() with params."""
    captured: dict = {}
    auto_dir = tmp_path / "auto_work"
    exe = str(tmp_path / "bin" / "echo2d")

    class RecordingRunner:
        def __init__(self, work_dir, executable=None) -> None:
            self.work_dir = Path(work_dir)
            captured["runner_args"] = (self.work_dir, executable)

        def run(self, params, np=1):
            captured["params"] = params
            captured["np"] = np
            return SimulationResult(
                geometry_file=params.GeometryFile, output_dir=str(self.work_dir)
            )

    monkeypatch.setattr("tempfile.mkdtemp", _fake_mkdtemp_for(tmp_path, "auto_work"))
    monkeypatch.setattr("pyecho.runner.ECHO2DRunner", RecordingRunner)

    result = quick_simulate(
        "round_collimator.txt",
        sigma=0.001,
        modes=[0, 1],
        executable=exe,
        clean=False,
    )

    work_dir, executable = captured["runner_args"]
    assert work_dir == auto_dir
    assert executable == exe
    assert captured["np"] == 1
    assert result.output_dir == str(auto_dir)

    params = captured["params"]
    assert params.GeometryFile == "round_collimator.txt"
    assert params.GeometryType == "round"
    assert params.Modes == [0, 1]
    assert params.BunchSigma == pytest.approx(0.001)
    assert params.StepY == pytest.approx(0.0002)
    assert params.StepZ == pytest.approx(0.0002)


def test_quick_simulate_copies_external_geometry(tmp_path: Path, monkeypatch) -> None:
    """An external geometry file is copied into the work dir and params updated."""
    geom = tmp_path / "src" / "my_geom.txt"
    geom.parent.mkdir()
    geom.write_text("geometry data\n")

    work = tmp_path / "work"
    captured: dict = {}

    class RecordingRunner:
        def __init__(self, work_dir, executable=None) -> None:
            self.work_dir = Path(work_dir)

        def run(self, params, np=1):
            captured["params"] = params
            return SimulationResult(output_dir=str(self.work_dir))

    monkeypatch.setattr("pyecho.runner.ECHO2DRunner", RecordingRunner)

    quick_simulate(str(geom), work_dir=str(work), clean=False)

    assert (work / geom.name).read_text() == "geometry data\n"
    assert captured["params"].GeometryFile == geom.name


def test_quick_simulate_type_mapping(tmp_path: Path, monkeypatch) -> None:
    """geometry_type round/flat maps to the correct template and GeometryType."""
    calls: list[tuple[str, dict]] = []

    class FakeParams:
        def __init__(self, **kwargs) -> None:
            self.__dict__.update(kwargs)

    def fake_from_template(name: str, **overrides):
        calls.append((name, overrides))
        return FakeParams(**overrides)

    monkeypatch.setattr("pyecho.config.ECHO2DParams.from_template", fake_from_template)

    class RecordingRunner:
        def __init__(self, work_dir, executable=None) -> None:
            pass

        def run(self, params, np=1):
            return params

    monkeypatch.setattr("pyecho.runner.ECHO2DRunner", RecordingRunner)

    quick_simulate("geom_a.txt", geometry_type="round", work_dir=str(tmp_path / "w1"))
    quick_simulate("geom_b.txt", geometry_type="flat", work_dir=str(tmp_path / "w2"))

    name_round, over_round = calls[0]
    assert name_round == "round_collimator"
    assert over_round["GeometryType"] == "round"
    assert over_round["GeometryFile"] == "geom_a.txt"

    name_flat, over_flat = calls[1]
    assert name_flat == "flat_absorber"
    assert over_flat["GeometryType"] == "recta"
    assert over_flat["GeometryFile"] == "geom_b.txt"


def test_quick_simulate_tempdir_cleanup(tmp_path: Path, monkeypatch) -> None:
    """clean=True removes the auto temp dir; clean=False preserves it."""
    auto_dir = tmp_path / "auto_work"
    runner_dirs: list[Path] = []

    class RecordingRunner:
        def __init__(self, work_dir, executable=None) -> None:
            self.work_dir = Path(work_dir)
            runner_dirs.append(self.work_dir)

        def run(self, params, np=1):
            return SimulationResult(output_dir=str(self.work_dir))

    monkeypatch.setattr("tempfile.mkdtemp", _fake_mkdtemp_for(tmp_path, "auto_work"))
    monkeypatch.setattr("pyecho.runner.ECHO2DRunner", RecordingRunner)

    # clean=True → the temporary directory is removed after the run.
    quick_simulate("round_collimator.txt", clean=True)
    assert not auto_dir.exists()

    # clean=False → the temporary directory survives.
    quick_simulate("round_collimator.txt", clean=False)
    assert auto_dir.exists()

    assert runner_dirs == [auto_dir, auto_dir]


def test_quick_simulate_error_propagation(tmp_path: Path, monkeypatch) -> None:
    """Runner errors propagate and temp-dir cleanup still runs in finally."""
    auto_dir = tmp_path / "auto_work"

    class FailingRunner:
        def __init__(self, work_dir, executable=None) -> None:
            pass

        def run(self, params, np=1):
            raise SimulationCrashedError("boom", returncode=3)

    monkeypatch.setattr("tempfile.mkdtemp", _fake_mkdtemp_for(tmp_path, "auto_work"))
    monkeypatch.setattr("pyecho.runner.ECHO2DRunner", FailingRunner)

    with pytest.raises(SimulationCrashedError):
        quick_simulate("round_collimator.txt", clean=True)

    assert not auto_dir.exists()


# ---------------------------------------------------------------------------
# quick_postprocess
# ---------------------------------------------------------------------------

def test_quick_postprocess_round(tmp_path: Path, monkeypatch) -> None:
    """Explicit round geometry produces a monopole-only RoundWakeResult."""
    _write_wake(tmp_path, "round", "wakeL_00.txt")
    monkeypatch.setattr(
        "pyecho.postprocess.PostProcessor",
        _make_fake_postprocessor(geometry_type="round"),
    )

    result = quick_postprocess(str(tmp_path), geometry="round")

    assert isinstance(result, RoundWakeResult)
    np.testing.assert_allclose(result.Wlong, [1.0, 0.9, 0.8])
    np.testing.assert_allclose(result.bunch, [0.1, 0.2, 0.3])
    assert result.loss_long == pytest.approx(-0.85)
    # No m=1 wake file → dipole fields are left as None.
    assert result.Wdipole is None
    assert result.kick_dipole is None


def test_quick_postprocess_dipole(tmp_path: Path, monkeypatch) -> None:
    """When m=1 is present, dipole wake + kick are populated."""
    _write_wake(tmp_path, "round", "wakeL_00.txt")
    _write_wake(tmp_path, "round", "wakeL_01.txt")
    monkeypatch.setattr(
        "pyecho.postprocess.PostProcessor",
        _make_fake_postprocessor(geometry_type="round", dipole=_dipole_result()),
    )

    result = quick_postprocess(str(tmp_path), geometry="round")

    assert isinstance(result, RoundWakeResult)
    np.testing.assert_allclose(result.Wdipole, [5.0, 4.0, 3.0])
    assert result.kick_dipole == pytest.approx(0.25)


def test_quick_postprocess_flat(tmp_path: Path, monkeypatch) -> None:
    """Explicit flat geometry runs the recta pipeline (incl. trapz integration)."""
    _write_wake(tmp_path, "magn", "wakeL_01.txt")
    monkeypatch.setattr(
        "pyecho.postprocess.PostProcessor",
        _make_fake_postprocessor(geometry_type="recta", recta=_recta_result()),
    )

    result = quick_postprocess(str(tmp_path), geometry="flat")

    assert isinstance(result, RectaWakeResult)
    np.testing.assert_allclose(result.Wlong, [1.0, 0.8])
    np.testing.assert_allclose(result.Wquad, [0.5, 0.4])
    np.testing.assert_allclose(result.Wdipole, [0.2, 0.1])
    # loss_long = -∫Wlong ds via trapezoidal rule
    assert result.loss_long == pytest.approx(-0.5 * 1.8 * 0.001)
    assert result.kick_quad == pytest.approx(-0.5 * 0.9 * 0.001)
    assert result.kick_dipole == pytest.approx(-0.5 * 0.3 * 0.001)


def test_quick_postprocess_autodetect(tmp_path: Path, monkeypatch) -> None:
    """geometry=None auto-detects the type via PostProcessor.geometry_type."""
    _write_wake(tmp_path, "round", "wakeL_00.txt")
    monkeypatch.setattr(
        "pyecho.postprocess.PostProcessor",
        _make_fake_postprocessor(geometry_type="round"),
    )

    result = quick_postprocess(str(tmp_path))

    assert isinstance(result, RoundWakeResult)
    np.testing.assert_allclose(result.Wlong, [1.0, 0.9, 0.8])


def test_quick_postprocess_missing_dir(tmp_path: Path) -> None:
    """A non-existent output directory raises ParserError from OutputLoader."""
    with pytest.raises(ParserError):
        quick_postprocess(str(tmp_path / "does_not_exist"))


# ---------------------------------------------------------------------------
# compare_runs
# ---------------------------------------------------------------------------

def test_compare_runs_basic(tmp_path: Path, monkeypatch) -> None:
    """Default monopole comparison across two runs."""
    monkeypatch.setattr(
        "pyecho.postprocess.PostProcessor",
        _make_fake_postprocessor(geometry_type="round"),
    )

    result = compare_runs(
        [str(tmp_path / "run0"), str(tmp_path / "run1")]
    )

    assert result["labels"] == ["Run 0", "Run 1"]
    np.testing.assert_allclose(result["s"], [0.0, 0.001, 0.002])
    assert len(result["W_list"]) == 2
    np.testing.assert_allclose(result["W_list"][0], [1.0, 0.9, 0.8])
    np.testing.assert_allclose(result["W_list"][1], [1.0, 0.9, 0.8])
    np.testing.assert_allclose(result["losses"], [-0.85, -0.85])


def test_compare_runs_dipole(tmp_path: Path, monkeypatch) -> None:
    """mode=1 compares the dipole longitudinal wake component."""
    monkeypatch.setattr(
        "pyecho.postprocess.PostProcessor",
        _make_fake_postprocessor(geometry_type="round", dipole=_dipole_result()),
    )

    result = compare_runs([str(tmp_path / "run0")], mode=1)

    np.testing.assert_allclose(result["W_list"][0], [5.0, 4.0, 3.0])
    assert len(result["losses"]) == 1


def test_compare_runs_skip_failed(tmp_path: Path, monkeypatch) -> None:
    """Runs that fail to load are skipped without aborting the comparison."""
    dirs = [
        str(tmp_path / "run0"),
        str(tmp_path / "run1"),
        str(tmp_path / "run2"),
    ]
    monkeypatch.setattr(
        "pyecho.postprocess.PostProcessor",
        _make_fake_postprocessor(geometry_type="round", fail_dirs=frozenset({dirs[1]})),
    )

    result = compare_runs(dirs, labels=["a", "b", "c"])

    assert len(result["W_list"]) == 2
    assert len(result["losses"]) == 2
    np.testing.assert_allclose(result["losses"], [-0.85, -0.85])
    np.testing.assert_allclose(result["W_list"][0], [1.0, 0.9, 0.8])
    np.testing.assert_allclose(result["W_list"][1], [1.0, 0.9, 0.8])
    # Labels are taken verbatim from the caller and are not filtered.
    assert result["labels"] == ["a", "b", "c"]


def test_compare_runs_empty(tmp_path: Path, monkeypatch) -> None:
    """Empty input returns empty lists with s=None."""
    monkeypatch.setattr(
        "pyecho.postprocess.PostProcessor",
        _make_fake_postprocessor(geometry_type="round"),
    )

    result = compare_runs([])

    assert result["s"] is None
    assert result["W_list"] == []
    assert result["labels"] == []
    assert result["losses"] == []
