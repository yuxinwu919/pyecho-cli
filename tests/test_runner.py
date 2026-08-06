"""Tests for :mod:`pyecho.runner` (ECHO2DRunner) and :mod:`pyecho.converge`.

Subprocess execution is fully mocked via ``unittest.mock`` so no real
ECHO2D binary is ever launched.  Covers:

- ``_get_platform_key`` platform/arch key format
- ``_find_project_root`` ECHO2D_v3_5 marker discovery
- ``ECHO2DRunner.executable`` setter resolution / rejection
- ``_ensure_geometry_in_work_dir`` geometry copy behaviour
- ``ECHO2DRunner.kill`` no-op / swallow / reference clearing
- ``ECHO2DRunner`` constructor work-dir creation
- ``ECHO2DRunner.run`` success / timeout / crashed paths
- ``ConvergenceRunner`` mesh refinement, convergence check, report
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

import pyecho.runner as runner_mod
from pyecho.config import ECHO2DParams
from pyecho.converge import ConvergencePoint, ConvergenceReport, ConvergenceRunner
from pyecho.datamodel import SimulationResult
from pyecho.errors import (
    ExecutableNotFoundError,
    SimulationCrashedError,
    SimulationTimeoutError,
)
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


def _mock_process(
    stdout: list[str] | None = None,
    returncode: int = 0,
    stderr: str = "",
    wait_side_effect=None,
) -> Mock:
    """Build a Mock masquerading as a Popen process object."""
    proc = Mock()
    proc.stdout = list(stdout) if stdout is not None else ["ECHO2D done\n"]
    proc.stderr = Mock()
    proc.stderr.read.return_value = stderr
    proc.wait.return_value = returncode
    if wait_side_effect is not None:
        proc.wait.side_effect = wait_side_effect
    proc.pid = 1234
    proc.poll.return_value = returncode
    return proc


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
# run()
# ---------------------------------------------------------------------------


def test_run_success_returns_simulation_result(tmp_path: Path) -> None:
    runner = _make_runner(tmp_path, name="work")
    proc = _mock_process(stdout=["ECHO2D started\n", "Mode 0: 50%\n", "done\n"])
    params = ECHO2DParams()

    with patch("pyecho.runner.subprocess.Popen", return_value=proc) as popen:
        result = runner.run(params, np=2)

    assert isinstance(result, SimulationResult)
    assert result.metadata.return_code == 0
    assert result.output_dir == (tmp_path / "work").resolve().__str__()
    assert "Mode 0: 50%" in result.stdout

    popen.assert_called_once()
    args, kwargs = popen.call_args
    assert args[0] == [str((tmp_path / "bin" / "echo2d").resolve())]
    assert kwargs["cwd"] == (tmp_path / "work").resolve().__str__()
    assert kwargs["env"]["OMP_NUM_THREADS"] == "2"
    assert kwargs["stdout"] == subprocess.PIPE
    assert kwargs["stderr"] == subprocess.PIPE
    assert kwargs["text"] is True

    assert (tmp_path / "work" / "input_in.txt").is_file()


def test_run_timeout_raises_simulation_timeout(tmp_path: Path) -> None:
    runner = _make_runner(tmp_path, name="work")
    calls = {"n": 0}

    def fake_wait(timeout=None):  # noqa: ANN001
        calls["n"] += 1
        if calls["n"] == 1:
            raise subprocess.TimeoutExpired("echo2d", timeout)
        return 0

    proc = _mock_process(stdout=["running\n"], wait_side_effect=fake_wait)
    params = ECHO2DParams()

    with patch("pyecho.runner.subprocess.Popen", return_value=proc):
        with pytest.raises(SimulationTimeoutError) as excinfo:
            runner.run(params, timeout=5)

    assert "timed out" in str(excinfo.value).lower()
    assert excinfo.value.ctx.get("timeout") == "5s"
    proc.kill.assert_called()


def test_run_crashed_nonzero_exit_code(tmp_path: Path) -> None:
    runner = _make_runner(tmp_path, name="work")
    proc = _mock_process(
        stdout=["running\n"], returncode=1, stderr="FATAL: something broke\n"
    )
    params = ECHO2DParams()

    with patch("pyecho.runner.subprocess.Popen", return_value=proc):
        with pytest.raises(SimulationCrashedError) as excinfo:
            runner.run(params)

    assert excinfo.value.ctx.get("returncode") == 1
    assert "FATAL" in excinfo.value.ctx.get("stderr", "")


def test_run_crashed_on_empty_stdout(tmp_path: Path) -> None:
    runner = _make_runner(tmp_path, name="work")
    proc = _mock_process(stdout=[], returncode=0)
    params = ECHO2DParams()

    with patch("pyecho.runner.subprocess.Popen", return_value=proc):
        with pytest.raises(SimulationCrashedError) as excinfo:
            runner.run(params)

    assert "no output" in str(excinfo.value).lower()


def test_run_executable_not_found(tmp_path: Path) -> None:
    runner = _make_runner(tmp_path, name="work")
    params = ECHO2DParams()

    with patch(
        "pyecho.runner.subprocess.Popen", side_effect=FileNotFoundError
    ):
        with pytest.raises(ExecutableNotFoundError):
            runner.run(params)


def test_run_geometry_file_override(tmp_path: Path) -> None:
    runner = _make_runner(tmp_path, name="work")
    proc = _mock_process(stdout=["ok\n"])
    params = ECHO2DParams()

    with patch("pyecho.runner.subprocess.Popen", return_value=proc):
        result = runner.run(params, geometry_file="override.txt")

    assert result.geometry_file == "override.txt"


def test_run_recreates_missing_work_dir(tmp_path: Path) -> None:
    runner = _make_runner(tmp_path, name="work")
    shutil.rmtree(tmp_path / "work")
    proc = _mock_process(stdout=["ok\n"])
    params = ECHO2DParams()

    with patch("pyecho.runner.subprocess.Popen", return_value=proc):
        result = runner.run(params)

    assert (tmp_path / "work").is_dir()
    assert (tmp_path / "work" / "input_in.txt").is_file()
    assert result.metadata.return_code == 0


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


def test_convergence_runner_run_mesh_refinement(tmp_path: Path) -> None:
    project_dir = tmp_path / "proj"
    runs_dir = project_dir / "runs"
    (runs_dir / "007_fine").mkdir(parents=True)
    (runs_dir / "008_coarser").mkdir()
    params = ECHO2DParams(
        StepY=0.0004, StepZ=0.0004, MeshLength=100, BunchSigma=0.002, Modes=[0]
    )

    with (
        patch("pyecho.converge.load_project", return_value=ProjectManifest(name="proj")),
        patch(
            "pyecho.converge.load_run_meta",
            return_value=RunManifest(id="007", name="fine", geometry_type="round"),
        ),
        patch("pyecho.converge.load_params", return_value=params),
    ):
        cr = ConvergenceRunner(project_dir, run_ref="007")

    assert cr._base_run_dir == (runs_dir / "007_fine").resolve()

    cr._run_single = Mock(return_value=10.0)
    report = cr.run(mesh_factors=[2.0, 1.0, 0.5], verbose=False)

    assert [p.label for p in report.points] == ["hx2.0", "hx1.0", "hx0.5"]
    assert report.points[0].step_y == pytest.approx(0.0004 * 2.0)
    assert report.points[0].step_z == pytest.approx(0.0004 * 2.0)
    assert report.points[2].mesh_length == max(10, int(100 / 0.5))
    assert all(p.status == "completed" for p in report.points)
    assert report.geometry_type == "round"
    assert report.base_sigma == 0.002
    assert report.converged is True


def test_convergence_runner_run_handles_failed_point(tmp_path: Path) -> None:
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    params = ECHO2DParams(
        StepY=0.0004, StepZ=0.0004, MeshLength=100, BunchSigma=0.002, Modes=[0]
    )

    with (
        patch("pyecho.converge.load_project", return_value=ProjectManifest(name="proj")),
        patch(
            "pyecho.converge.list_runs",
            return_value=[RunManifest(id="001", name="baseline")],
        ),
        patch(
            "pyecho.converge.load_run_meta",
            return_value=RunManifest(id="001", name="baseline", geometry_type="round"),
        ),
        patch("pyecho.converge.load_params", return_value=params),
    ):
        cr = ConvergenceRunner(project_dir)

    cr._run_single = Mock(side_effect=[ValueError("boom"), 10.0])
    report = cr.run(mesh_factors=[2.0, 1.0], verbose=False)

    assert report.points[0].status == "failed"
    assert report.points[0].loss_factor is None
    assert report.points[1].status == "completed"
    assert report.points[1].loss_factor == 10.0
    assert report.converged is False  # only one completed point
