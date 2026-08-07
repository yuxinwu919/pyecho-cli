"""Tests for :mod:`pyecho.runner` (ECHO2DRunner) and :mod:`pyecho.converge`.

Covers pure / non-subprocess behaviour only:

- ``_get_platform_key`` platform/arch key format
- ``_find_project_root`` ECHO2D_v3_5 marker discovery
- ``ECHO2DRunner.executable`` setter resolution / rejection
- ``_ensure_geometry_in_work_dir`` geometry copy behaviour
- ``ECHO2DRunner.kill`` no-op / swallow / reference clearing
- ``ECHO2DRunner`` constructor work-dir creation
- ``ConvergenceReport`` convergence checks and summary formatting
- ``ConvergenceRunner`` constructor base-run discovery

Subprocess integration tests (mocks of ``subprocess.Popen`` /
``ECHO2DRunner.run``) are intentionally removed.  They require a real ECHO2D
binary — run with:

    echo2d run single ...
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

import pyecho.runner as runner_mod
from pyecho.config import ECHO2DParams
from pyecho.converge import ConvergencePoint, ConvergenceReport, ConvergenceRunner
from pyecho.errors import ExecutableNotFoundError
from pyecho.project import ProjectManifest, RunManifest
from pyecho.runner import ECHO2DRunner, _get_platform_key


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_runner(tmp_path: Path, name: str = "work") -> ECHO2DRunner:
    """Build a runner with a real on-disk fake executable."""
    exe = tmp_path / "bin" / "echo2d"
    exe.parent.mkdir(exist_ok=True)
    exe.write_text("#!/bin/sh\n")
    return ECHO2DRunner(tmp_path / name, executable=str(exe))


# ---------------------------------------------------------------------------
# _get_platform_key
# ---------------------------------------------------------------------------


def test_get_platform_key_returns_system_arch_key() -> None:
    with (
        patch.object(runner_mod.platform, "system", return_value="Darwin"),
        patch.object(runner_mod.platform, "machine", return_value="arm64"),
    ):
        assert _get_platform_key() == "Darwin_arm64"


def test_get_platform_key_normalizes_amd64_to_x86_64() -> None:
    with (
        patch.object(runner_mod.platform, "system", return_value="Linux"),
        patch.object(runner_mod.platform, "machine", return_value="AMD64"),
    ):
        assert _get_platform_key() == "Linux_x86_64"


# ---------------------------------------------------------------------------
# _find_project_root
# ---------------------------------------------------------------------------


def test_find_project_root_locates_echo2d_marker(tmp_path: Path) -> None:
    fake_file = tmp_path / "proj" / "pkg" / "mod.py"
    fake_file.parent.mkdir(parents=True)
    (tmp_path / "proj" / "ECHO2D_v3_5").mkdir()
    runner = _make_runner(tmp_path, name="work")

    with patch.object(runner_mod, "__file__", str(fake_file)):
        root = runner._find_project_root()

    assert root == (tmp_path / "proj").resolve()


def test_find_project_root_falls_back_to_cwd(tmp_path: Path) -> None:
    fake_file = tmp_path / "x" / "y" / "z" / "mod.py"
    fake_file.parent.mkdir(parents=True)
    expected = tmp_path / "elsewhere"
    runner = _make_runner(tmp_path, name="work")

    with patch.object(
        runner_mod.Path, "cwd", new=staticmethod(lambda: expected)
    ):
        with patch.object(runner_mod, "__file__", str(fake_file)):
            root = runner._find_project_root()

    assert root == expected


# ---------------------------------------------------------------------------
# executable setter
# ---------------------------------------------------------------------------


def test_executable_setter_resolves_absolute_path(tmp_path: Path) -> None:
    exe = tmp_path / "bin" / "echo2d"
    exe.parent.mkdir()
    exe.write_text("#!/bin/sh\n")

    runner = ECHO2DRunner(tmp_path / "work", executable=str(exe))

    assert runner.executable == str(exe.resolve())


def test_executable_setter_resolves_relative_from_project_root(
    tmp_path: Path,
) -> None:
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "echo2d").write_text("#!/bin/sh\n")
    runner = _make_runner(tmp_path, name="work")

    with patch.object(runner, "_find_project_root", return_value=proj):
        runner.executable = "echo2d"

    assert runner.executable == str((proj / "echo2d").resolve())


def test_executable_setter_rejects_missing_path(tmp_path: Path) -> None:
    runner = _make_runner(tmp_path, name="work")

    with pytest.raises(ExecutableNotFoundError) as excinfo:
        runner.executable = "definitely_missing_binary_xyz"

    assert "definitely_missing_binary_xyz" in str(excinfo.value)
    assert "searched_paths" in excinfo.value.ctx


def test_executable_getter_lazily_auto_detects(tmp_path: Path) -> None:
    runner = _make_runner(tmp_path, name="work")
    runner._executable_path = None

    with patch.object(runner, "_auto_detect", return_value="/fake/echo2d") as m:
        assert runner.executable == "/fake/echo2d"

    m.assert_called_once()


# ---------------------------------------------------------------------------
# _ensure_geometry_in_work_dir
# ---------------------------------------------------------------------------


def test_ensure_geometry_copies_external_file(tmp_path: Path) -> None:
    runner = _make_runner(tmp_path, name="work")
    geom_src = tmp_path / "external" / "struct.txt"
    geom_src.parent.mkdir()
    geom_src.write_text("geometry")
    params = ECHO2DParams(GeometryFile=str(geom_src))

    result = runner._ensure_geometry_in_work_dir(params)

    assert result is params
    assert params.GeometryFile == "struct.txt"
    assert (tmp_path / "work" / "struct.txt").is_file()


def test_ensure_geometry_skips_bare_filename(tmp_path: Path) -> None:
    runner = _make_runner(tmp_path, name="work")
    params = ECHO2DParams(GeometryFile="collimator.txt")

    runner._ensure_geometry_in_work_dir(params)

    assert params.GeometryFile == "collimator.txt"
    assert not (tmp_path / "work" / "collimator.txt").exists()


def test_ensure_geometry_skips_dash_marker(tmp_path: Path) -> None:
    runner = _make_runner(tmp_path, name="work")
    params = ECHO2DParams(GeometryFile="-")

    assert runner._ensure_geometry_in_work_dir(params) is params
    assert params.GeometryFile == "-"


def test_ensure_geometry_skips_missing_source(tmp_path: Path) -> None:
    runner = _make_runner(tmp_path, name="work")
    params = ECHO2DParams(GeometryFile="data/geom.txt")

    runner._ensure_geometry_in_work_dir(params)

    assert params.GeometryFile == "data/geom.txt"
    assert not (tmp_path / "work" / "geom.txt").exists()


def test_ensure_geometry_skips_when_already_in_work_dir(tmp_path: Path) -> None:
    runner = _make_runner(tmp_path, name="work")
    geom = tmp_path / "work" / "inside.txt"
    geom.write_text("x")
    params = ECHO2DParams(GeometryFile=str(geom))

    runner._ensure_geometry_in_work_dir(params)

    assert params.GeometryFile == str(geom)


# ---------------------------------------------------------------------------
# kill()
# ---------------------------------------------------------------------------


def test_kill_noop_without_process(tmp_path: Path) -> None:
    runner = _make_runner(tmp_path, name="work")
    runner._current_process = None
    runner.kill()  # should not raise


def test_kill_terminates_and_clears_reference(tmp_path: Path) -> None:
    runner = _make_runner(tmp_path, name="work")
    proc = Mock()
    proc.pid = 1234
    proc.poll.return_value = 0
    runner._current_process = proc

    runner.kill()

    proc.kill.assert_called_once()
    proc.wait.assert_called_once_with(timeout=5)
    assert runner._current_process is None


def test_kill_swallows_oserror_keeps_reference(tmp_path: Path) -> None:
    runner = _make_runner(tmp_path, name="work")
    proc = Mock()
    proc.pid = 1234
    proc.kill.side_effect = OSError("no such process")
    proc.poll.return_value = None
    runner._current_process = proc

    runner.kill()  # should not raise

    assert runner._current_process is proc  # retry possible


def test_kill_handles_timeout_expired(tmp_path: Path) -> None:
    runner = _make_runner(tmp_path, name="work")
    proc = Mock()
    proc.pid = 1234
    proc.wait.side_effect = subprocess.TimeoutExpired("echo2d", 5)
    proc.poll.return_value = None
    runner._current_process = proc

    runner.kill()  # should not raise

    assert runner._current_process is proc


# ---------------------------------------------------------------------------
# constructor
# ---------------------------------------------------------------------------


def test_constructor_creates_work_dir(tmp_path: Path) -> None:
    work = tmp_path / "a" / "b" / "work"
    assert not work.exists()

    runner = _make_runner(tmp_path, name="a/b/work")

    assert work.is_dir()
    assert runner.work_dir == work.resolve()
    assert runner._current_process is None


def test_constructor_auto_detects_executable(tmp_path: Path) -> None:
    with patch.object(
        ECHO2DRunner, "_auto_detect", return_value=str(tmp_path / "bin" / "e")
    ) as m:
        exe = tmp_path / "bin" / "e"
        exe.parent.mkdir()
        exe.write_text("#!/bin/sh\n")
        runner = ECHO2DRunner(tmp_path / "work")

    m.assert_called_once()
    assert runner.executable == str(exe.resolve())


# ---------------------------------------------------------------------------
# ConvergenceRunner / ConvergenceReport
# ---------------------------------------------------------------------------


def test_convergence_report_converged_within_tolerance() -> None:
    report = ConvergenceReport(geometry_type="round", base_sigma=0.001)
    report.points.append(
        ConvergencePoint(
            label="hx2.0", step_y=0.0004, step_z=0.0004,
            mesh_length=26, loss_factor=10.0, status="completed",
        )
    )
    report.points.append(
        ConvergencePoint(
            label="hx1.0", step_y=0.0002, step_z=0.0002,
            mesh_length=52, loss_factor=10.2, status="completed",
        )
    )

    assert report.converged is True


def test_convergence_report_not_converged_outside_tolerance() -> None:
    report = ConvergenceReport(geometry_type="round", base_sigma=0.001)
    report.points.append(
        ConvergencePoint(
            label="hx2.0", step_y=0.0004, step_z=0.0004,
            mesh_length=26, loss_factor=10.0, status="completed",
        )
    )
    report.points.append(
        ConvergencePoint(
            label="hx1.0", step_y=0.0002, step_z=0.0002,
            mesh_length=52, loss_factor=12.0, status="completed",
        )
    )

    assert report.converged is False


def test_convergence_report_requires_two_completed_points() -> None:
    report = ConvergenceReport(geometry_type="round", base_sigma=0.001)
    assert report.converged is False

    report.points.append(
        ConvergencePoint(
            label="hx1.0", step_y=0.0002, step_z=0.0002,
            mesh_length=52, loss_factor=10.0, status="completed",
        )
    )
    assert report.converged is False  # only one completed point


def test_convergence_report_summary_format() -> None:
    report = ConvergenceReport(geometry_type="round", base_sigma=0.001)
    report.points.append(
        ConvergencePoint(
            label="hx1.0", step_y=0.0002, step_z=0.0002,
            mesh_length=52, loss_factor=10.123456, status="completed",
        )
    )

    summary = report.summary()

    assert "Convergence Study" in summary
    assert "round" in summary
    assert "hx1.0" in summary
    assert "Converged:" in summary


def test_convergence_runner_init_uses_latest_run(tmp_path: Path) -> None:
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    runs = [
        RunManifest(id="001", name="baseline"),
        RunManifest(id="002", name="fine"),
    ]

    with (
        patch("pyecho.converge.load_project", return_value=ProjectManifest(name="proj")),
        patch("pyecho.converge.list_runs", return_value=runs),
        patch(
            "pyecho.converge.load_run_meta",
            return_value=RunManifest(id="002", name="fine", geometry_type="round"),
        ),
        patch("pyecho.converge.load_params", return_value=ECHO2DParams(BunchSigma=0.001)),
    ):
        cr = ConvergenceRunner(project_dir)

    assert cr._base_run_dir == (project_dir.resolve() / "runs" / "002_fine")
    assert cr._base_sigma == 0.001
