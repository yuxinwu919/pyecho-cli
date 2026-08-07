"""Tests for :mod:`pyecho.runner` (ECHO2DRunner) and :mod:`pyecho.converge`.

Covers:

- ``_get_platform_key`` platform/arch key format
- ``_find_project_root`` ECHO2D_v3_5 marker discovery
- ``ECHO2DRunner.executable`` setter resolution / rejection
- ``_ensure_geometry_in_work_dir`` geometry copy behaviour
- ``ECHO2DRunner.kill`` no-op / swallow / reference clearing
- ``ECHO2DRunner`` constructor work-dir creation
- ``ECHO2DRunner.run`` / ``run_stream`` subprocess flows with a mocked
  ``subprocess.Popen``
- ``ConvergenceReport`` convergence checks and summary formatting
- ``ConvergenceRunner`` constructor base-run discovery

The subprocess tests mock ``subprocess.Popen`` (no real ECHO2D binary is
needed) and mock ``pyecho.runner.OutputLoader`` so result building skips
file I/O.
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
    stdout_lines: list[str] | None = None,
    wait_return: int = 0,
) -> Mock:
    """Build a Mock ``subprocess.Popen`` process for ECHO2DRunner flows."""
    proc = Mock()
    proc.stdout = stdout_lines if stdout_lines is not None else [
        "Mode 0: 50%\n",
        "Mode 0: 100%\n",
    ]
    proc.stderr.read.return_value = ""
    proc.wait.return_value = wait_return
    proc.pid = 12345
    return proc


def _configure_output_loader(mock_output_loader: Mock) -> None:
    """Wire an empty OutputLoader so ``_build_result`` skips file I/O."""
    loader = mock_output_loader.return_value
    loader.load_all_wakes.return_value = {}
    loader.load_currents.return_value = None
    loader.load_currents_radial.return_value = None
    loader.load_particles.return_value = None
    loader.list_monitors.return_value = []
    loader.load_all_wake_monitors.return_value = {}
    loader.load_beam_moments.return_value = None


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
# run() / run_stream() — subprocess flows (mocked subprocess.Popen)
# ---------------------------------------------------------------------------


@patch("subprocess.Popen")
@patch("pyecho.runner.OutputLoader")
def test_run_success(
    mock_output_loader: Mock,
    mock_popen: Mock,
    tmp_path: Path,
) -> None:
    """Successful run returns a SimulationResult and a correct Popen call."""
    runner = _make_runner(tmp_path, name="work")
    params = ECHO2DParams(GeometryFile="collimator.txt")
    _configure_output_loader(mock_output_loader)
    mock_popen.return_value = _mock_process(
        stdout_lines=["Mode 0: 25%\n", "Mode 0: 50%\n", "Mode 0: 100%\n"]
    )

    result = runner.run(params, np=4)

    assert isinstance(result, SimulationResult)
    assert result.stdout == "Mode 0: 25%\nMode 0: 50%\nMode 0: 100%"
    assert result.output_dir == str(runner.work_dir)
    assert runner._current_process is None  # reference cleared after run

    mock_popen.assert_called_once()
    call = mock_popen.call_args
    assert call.args[0] == [runner.executable]
    assert call.kwargs["cwd"] == str(runner.work_dir)
    assert call.kwargs["env"]["OMP_NUM_THREADS"] == "4"
    assert call.kwargs["text"] is True


@patch("subprocess.Popen")
@patch("pyecho.runner.OutputLoader")
def test_run_nonzero_exit(
    mock_output_loader: Mock,
    mock_popen: Mock,
    tmp_path: Path,
) -> None:
    """Non-zero exit code raises SimulationCrashedError."""
    runner = _make_runner(tmp_path, name="work")
    params = ECHO2DParams(GeometryFile="collimator.txt")
    mock_popen.return_value = _mock_process(wait_return=1)

    with pytest.raises(SimulationCrashedError) as excinfo:
        runner.run(params)

    assert excinfo.value.ctx["returncode"] == 1


@patch("subprocess.Popen")
@patch("pyecho.runner.OutputLoader")
def test_run_timeout(
    mock_output_loader: Mock,
    mock_popen: Mock,
    tmp_path: Path,
) -> None:
    """TimeoutExpired from wait() becomes SimulationTimeoutError."""
    runner = _make_runner(tmp_path, name="work")
    params = ECHO2DParams(GeometryFile="collimator.txt")
    mock_proc = _mock_process()
    mock_proc.wait.side_effect = [
        subprocess.TimeoutExpired("echo2d", 5),  # timed wait raises
        0,  # post-kill wait succeeds
    ]
    mock_popen.return_value = mock_proc

    with pytest.raises(SimulationTimeoutError) as excinfo:
        runner.run(params, timeout=5)

    assert excinfo.value.ctx["timeout"] == "5s"
    mock_proc.kill.assert_called_once()
    assert mock_proc.wait.call_count == 2  # timed wait + post-kill wait
    assert runner._current_process is None


@patch("subprocess.Popen")
@patch("pyecho.runner.OutputLoader")
def test_run_timeout_deadline_enforced_mid_stdout(
    mock_output_loader: Mock,
    mock_popen: Mock,
    tmp_path: Path,
) -> None:
    """Hanging stdout is caught by the mid-loop deadline check."""
    runner = _make_runner(tmp_path, name="work")
    params = ECHO2DParams(GeometryFile="collimator.txt")
    mock_proc = _mock_process(stdout_lines=["Mode 0: 10%\n", "Mode 0: 20%\n"])
    mock_popen.return_value = mock_proc

    # start, check-line-1, check-line-2 (>deadline), elapsed
    times = iter([100.0, 100.5, 200.0, 200.0])
    with patch.object(
        runner_mod.time, "monotonic", side_effect=lambda: next(times)
    ):
        with pytest.raises(SimulationTimeoutError) as excinfo:
            runner.run(params, timeout=5)

    assert excinfo.value.ctx["timeout"] == "5s"
    assert excinfo.value.ctx["elapsed"] == "100.0s"  # 200.0 - 100.0
    mock_proc.kill.assert_called_once()
    mock_proc.wait.assert_called_once()
    assert runner._current_process is None


@patch("subprocess.Popen")
@patch("pyecho.runner.OutputLoader")
def test_run_file_not_found(
    mock_output_loader: Mock,
    mock_popen: Mock,
    tmp_path: Path,
) -> None:
    """FileNotFoundError from Popen becomes ExecutableNotFoundError."""
    runner = _make_runner(tmp_path, name="work")
    params = ECHO2DParams(GeometryFile="collimator.txt")
    mock_popen.side_effect = FileNotFoundError("no such executable")

    with pytest.raises(ExecutableNotFoundError) as excinfo:
        runner.run(params)

    assert "searched_paths" in excinfo.value.ctx


@patch("subprocess.Popen")
@patch("pyecho.runner.OutputLoader")
def test_run_with_geometry_override(
    mock_output_loader: Mock,
    mock_popen: Mock,
    tmp_path: Path,
) -> None:
    """geometry_file overrides params.GeometryFile without mutating params."""
    runner = _make_runner(tmp_path, name="work")
    params = ECHO2DParams(GeometryFile="original.txt")
    _configure_output_loader(mock_output_loader)
    mock_popen.return_value = _mock_process()

    result = runner.run(params, geometry_file="override.txt")

    assert result.geometry_file == "override.txt"
    assert params.GeometryFile == "original.txt"  # original not mutated
    input_text = (runner.work_dir / "input_in.txt").read_text()
    assert "GeometryFile=override.txt" in input_text


@patch("subprocess.Popen")
@patch("pyecho.runner.OutputLoader")
def test_run_creates_missing_work_dir(
    mock_output_loader: Mock,
    mock_popen: Mock,
    tmp_path: Path,
) -> None:
    """run() recreates a work_dir deleted after construction."""
    runner = _make_runner(tmp_path, name="work")
    shutil.rmtree(runner.work_dir)
    assert not runner.work_dir.exists()
    _configure_output_loader(mock_output_loader)
    mock_popen.return_value = _mock_process()

    runner.run(ECHO2DParams(GeometryFile="collimator.txt"))

    assert runner.work_dir.is_dir()
    assert (runner.work_dir / "input_in.txt").is_file()


@patch("subprocess.Popen")
@patch("pyecho.runner.OutputLoader")
def test_run_stream_yields_progress(
    mock_output_loader: Mock,
    mock_popen: Mock,
    tmp_path: Path,
) -> None:
    """run_stream yields progress dicts parsed from ECHO2D stdout."""
    runner = _make_runner(tmp_path, name="work")
    params = ECHO2DParams(GeometryFile="collimator.txt")
    _configure_output_loader(mock_output_loader)
    mock_popen.return_value = _mock_process(
        stdout_lines=["Mode 0: 42%\n", "no progress here\n", "Mode 0: 100%\n"]
    )

    gen = runner.run_stream(params)
    updates = list(gen)

    assert updates == [
        {"percent": 42.0, "message": "Mode 0: 42%"},
        {"percent": 100.0, "message": "Mode 0: 100%"},
    ]


@patch("subprocess.Popen")
@patch("pyecho.runner.OutputLoader")
def test_run_stream_sets_current_process(
    mock_output_loader: Mock,
    mock_popen: Mock,
    tmp_path: Path,
) -> None:
    """run_stream tracks the live process on _current_process mid-stream."""
    runner = _make_runner(tmp_path, name="work")
    params = ECHO2DParams(GeometryFile="collimator.txt")
    _configure_output_loader(mock_output_loader)
    mock_proc = _mock_process(stdout_lines=["Mode 0: 50%\n"])
    mock_popen.return_value = mock_proc

    gen = runner.run_stream(params)
    first = next(gen)

    assert first == {"percent": 50.0, "message": "Mode 0: 50%"}
    assert runner._current_process is mock_proc  # live while paused at yield

    with pytest.raises(StopIteration):
        next(gen)

    assert runner._current_process is None  # cleared once finished


@patch("subprocess.Popen")
@patch("pyecho.runner.OutputLoader")
def test_run_stream_returns_result(
    mock_output_loader: Mock,
    mock_popen: Mock,
    tmp_path: Path,
) -> None:
    """run_stream returns a SimulationResult via StopIteration.value."""
    runner = _make_runner(tmp_path, name="work")
    params = ECHO2DParams(GeometryFile="collimator.txt")
    _configure_output_loader(mock_output_loader)
    mock_popen.return_value = _mock_process(stdout_lines=["Mode 0: 100%\n"])

    gen = runner.run_stream(params)
    updates: list[dict[str, float]] = []
    result: SimulationResult | None = None
    while True:
        try:
            updates.append(next(gen))
        except StopIteration as exc:
            result = exc.value
            break

    assert updates == [{"percent": 100.0, "message": "Mode 0: 100%"}]
    assert isinstance(result, SimulationResult)
    assert result.stdout == "Mode 0: 100%"


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
