"""Tests for :mod:`pyecho.converge` (grid-convergence automation).

All project / runner / post-process I/O is mocked so no real ECHO2D
binary or on-disk project manifest is required.  Covers:

- ``ConvergencePoint`` defaults
- ``ConvergenceReport.converged`` (5% tolerance, edge cases)
- ``ConvergenceReport.summary`` report generation
- ``ConvergenceRunner.__init__`` run selection (latest / prefix / errors)
- ``ConvergenceRunner.run`` mesh refinement, default factors & modes,
  all-fail / mixed-failure / single-point edge cases
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from pyecho.config import ECHO2DParams
from pyecho.converge import ConvergencePoint, ConvergenceReport, ConvergenceRunner
from pyecho.project import ProjectManifest, RunManifest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _params(
    step: float = 0.0004,
    mesh_len: int = 100,
    sigma: float = 0.002,
    modes: list[int] | None = None,
) -> ECHO2DParams:
    """Standard base parameters for convergence fixtures."""
    return ECHO2DParams(
        StepY=step,
        StepZ=step,
        MeshLength=mesh_len,
        BunchSigma=sigma,
        Modes=modes if modes is not None else [0],
    )


def _runner(project_dir: Path, params: ECHO2DParams) -> ConvergenceRunner:
    """Build a ConvergenceRunner with all project I/O mocked.

    Uses the latest-run code path (``run_ref=None``).
    """
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
        return ConvergenceRunner(project_dir)


# ---------------------------------------------------------------------------
# ConvergencePoint
# ---------------------------------------------------------------------------


def test_point_defaults_pending() -> None:
    point = ConvergencePoint(label="hx1.0", step_y=0.0002, step_z=0.0002, mesh_length=52)
    assert point.loss_factor is None
    assert point.kick_factor is None
    assert point.elapsed_s == 0.0
    assert point.status == "pending"


# ---------------------------------------------------------------------------
# ConvergenceReport.converged
# ---------------------------------------------------------------------------


def test_converged_true_within_5_percent() -> None:
    report = ConvergenceReport(geometry_type="round", base_sigma=0.001)
    report.points.append(
        ConvergencePoint("hx2.0", 0.0004, 0.0004, 26, loss_factor=10.0, status="completed")
    )
    report.points.append(
        ConvergencePoint("hx1.0", 0.0002, 0.0002, 52, loss_factor=10.4, status="completed")
    )
    assert report.converged is True  # (10.4 - 10.0) / 10.4 = 3.8% < 5%


def test_converged_false_exceeding_5_percent() -> None:
    report = ConvergenceReport(geometry_type="round", base_sigma=0.001)
    report.points.append(
        ConvergencePoint("hx2.0", 0.0004, 0.0004, 26, loss_factor=10.0, status="completed")
    )
    report.points.append(
        ConvergencePoint("hx1.0", 0.0002, 0.0002, 52, loss_factor=11.0, status="completed")
    )
    assert report.converged is False  # (11.0 - 10.0) / 11.0 = 9.1% >= 5%


def test_converged_false_with_one_completed_point() -> None:
    report = ConvergenceReport(geometry_type="round", base_sigma=0.001)
    report.points.append(
        ConvergencePoint("hx1.0", 0.0002, 0.0002, 52, loss_factor=10.0, status="completed")
    )
    report.points.append(
        ConvergencePoint("hx0.5", 0.0001, 0.0001, 104, loss_factor=None, status="failed")
    )
    assert report.converged is False  # only one point with a loss factor


def test_converged_false_with_no_completed_points() -> None:
    report = ConvergenceReport(geometry_type="round", base_sigma=0.001)
    report.points.append(
        ConvergencePoint("hx2.0", 0.0004, 0.0004, 26, status="failed")
    )
    assert report.converged is False


def test_converged_false_when_finest_loss_zero() -> None:
    report = ConvergenceReport(geometry_type="round", base_sigma=0.001)
    report.points.append(
        ConvergencePoint("hx2.0", 0.0004, 0.0004, 26, loss_factor=5.0, status="completed")
    )
    report.points.append(
        ConvergencePoint("hx1.0", 0.0002, 0.0002, 52, loss_factor=0.0, status="completed")
    )
    assert report.converged is False  # division by ~zero is rejected


def test_converged_uses_only_last_two_completed() -> None:
    report = ConvergenceReport(geometry_type="round", base_sigma=0.001)
    report.points.append(
        ConvergencePoint("hx4.0", 0.0008, 0.0008, 13, loss_factor=1.0, status="completed")
    )
    report.points.append(
        ConvergencePoint("hx2.0", 0.0004, 0.0004, 26, loss_factor=100.0, status="completed")
    )
    report.points.append(
        ConvergencePoint("hx1.0", 0.0002, 0.0002, 52, loss_factor=100.0, status="completed")
    )
    report.points.append(
        ConvergencePoint("hx0.5", 0.0001, 0.0001, 104, loss_factor=102.0, status="completed")
    )
    # Earlier divergent points are ignored; only the finest two are compared.
    assert report.converged is True


# ---------------------------------------------------------------------------
# ConvergenceReport.summary
# ---------------------------------------------------------------------------


def test_summary_includes_header_and_rows() -> None:
    report = ConvergenceReport(geometry_type="round", base_sigma=0.001)
    report.points.append(
        ConvergencePoint("hx1.0", 0.0002, 0.0002, 52, loss_factor=10.123456, elapsed_s=3.5)
    )
    summary = report.summary()
    assert "Convergence Study" in summary
    assert "Mesh" in summary and "Loss [V/pC]" in summary
    assert "hx1.0" in summary
    assert "10.123456" in summary
    assert "Converged:" in summary


def test_summary_shows_failed_for_missing_loss() -> None:
    report = ConvergenceReport(geometry_type="round", base_sigma=0.001)
    report.points.append(
        ConvergencePoint("hx2.0", 0.0004, 0.0004, 26, status="failed")
    )
    summary = report.summary()
    assert "FAILED" in summary
    assert "Converged: NO" in summary


def test_summary_formats_sigma() -> None:
    report = ConvergenceReport(geometry_type="recta", base_sigma=0.00235)
    report.points.append(
        ConvergencePoint("hx1.0", 0.0002, 0.0002, 52, loss_factor=8.0, status="completed")
    )
    summary = report.summary()
    assert "recta" in summary
    assert "sigma=0.0024 m" in summary


# ---------------------------------------------------------------------------
# ConvergenceRunner.__init__
# ---------------------------------------------------------------------------


def test_init_uses_latest_run_when_no_ref(tmp_path: Path) -> None:
    project_dir = tmp_path / "proj"
    with (
        patch("pyecho.converge.load_project", return_value=ProjectManifest(name="proj")),
        patch(
            "pyecho.converge.list_runs",
            return_value=[RunManifest(id="001", name="baseline"), RunManifest(id="002", name="fine")],
        ),
        patch(
            "pyecho.converge.load_run_meta",
            return_value=RunManifest(id="002", name="fine", geometry_type="round"),
        ),
        patch("pyecho.converge.load_params", return_value=_params(sigma=0.003)),
    ):
        cr = ConvergenceRunner(project_dir)
    assert cr._base_run_dir == (project_dir.resolve() / "runs" / "002_fine")


def test_init_resolves_run_ref_by_prefix(tmp_path: Path) -> None:
    project_dir = tmp_path / "proj"
    (project_dir / "runs" / "007_fine").mkdir(parents=True)
    (project_dir / "runs" / "008_coarser").mkdir()
    with (
        patch("pyecho.converge.load_project", return_value=ProjectManifest(name="proj")),
        patch(
            "pyecho.converge.load_run_meta",
            return_value=RunManifest(id="007", name="fine", geometry_type="round"),
        ),
        patch("pyecho.converge.load_params", return_value=_params()),
    ):
        cr = ConvergenceRunner(project_dir, run_ref="007")
    assert cr._base_run_dir == (project_dir.resolve() / "runs" / "007_fine")


def test_init_raises_when_run_ref_missing(tmp_path: Path) -> None:
    project_dir = tmp_path / "proj"
    (project_dir / "runs" / "999_other").mkdir(parents=True)
    with (
        patch("pyecho.converge.load_project", return_value=ProjectManifest(name="proj")),
        patch(
            "pyecho.converge.load_run_meta",
            return_value=RunManifest(id="999", name="other"),
        ),
        patch("pyecho.converge.load_params", return_value=_params()),
    ):
        with pytest.raises(ValueError, match="not found"):
            ConvergenceRunner(project_dir, run_ref="007")


def test_init_raises_when_no_runs(tmp_path: Path) -> None:
    project_dir = tmp_path / "proj"
    with (
        patch("pyecho.converge.load_project", return_value=ProjectManifest(name="proj")),
        patch("pyecho.converge.list_runs", return_value=[]),
        patch(
            "pyecho.converge.load_run_meta",
            return_value=RunManifest(id="001"),
        ),
        patch("pyecho.converge.load_params", return_value=_params()),
    ):
        with pytest.raises(ValueError, match="No runs found"):
            ConvergenceRunner(project_dir)


def test_init_stores_base_params_and_sigma(tmp_path: Path) -> None:
    params = _params(sigma=0.004, step=0.0005)
    cr = _runner(tmp_path / "proj", params)
    assert cr._base_params is params
    assert cr._base_sigma == pytest.approx(0.004)


# ---------------------------------------------------------------------------
# ConvergenceRunner.run
# ---------------------------------------------------------------------------


def test_run_uses_default_mesh_factors(tmp_path: Path) -> None:
    params = _params(step=0.0004, mesh_len=100)
    cr = _runner(tmp_path / "proj", params)
    cr._run_single = Mock(return_value=10.0)

    report = cr.run(mesh_factors=None, modes=None, verbose=False)

    assert [p.label for p in report.points] == ["hx2.0", "hx1.0", "hx0.5"]
    calls = cr._run_single.call_args_list
    assert calls[0].kwargs["step_y"] == pytest.approx(0.0008)
    assert calls[0].kwargs["step_z"] == pytest.approx(0.0008)
    assert calls[0].kwargs["mesh_length"] == max(10, int(100 / 2.0))
    assert calls[2].kwargs["mesh_length"] == max(10, int(100 / 0.5))
    assert report.points[0].step_y == pytest.approx(0.0008)
    assert report.points[0].step_z == pytest.approx(0.0008)
    assert report.points[2].mesh_length == max(10, int(100 / 0.5))
    assert all(p.status == "completed" for p in report.points)
    assert report.geometry_type == "round"
    assert report.base_sigma == pytest.approx(0.002)


def test_run_uses_default_modes_from_base(tmp_path: Path) -> None:
    params = _params(modes=[0, 2, 4])
    cr = _runner(tmp_path / "proj", params)
    cr._run_single = Mock(return_value=10.0)

    cr.run(mesh_factors=[1.0], modes=None, verbose=False)

    assert cr._run_single.call_args.kwargs["modes"] == [0, 2, 4]
    assert cr._run_single.call_args.kwargs["threads"] == 1


def test_run_custom_mesh_factors_and_modes(tmp_path: Path) -> None:
    cr = _runner(tmp_path / "proj", _params())
    cr._run_single = Mock(side_effect=[10.0, 10.2])

    report = cr.run(mesh_factors=[1.0, 0.5], modes=[1, 3], threads=4, verbose=False)

    assert [p.label for p in report.points] == ["hx1.0", "hx0.5"]
    assert cr._run_single.call_args_list[0].kwargs["modes"] == [1, 3]
    assert cr._run_single.call_args_list[0].kwargs["threads"] == 4
    assert cr._run_single.call_args_list[1].kwargs["step_y"] == pytest.approx(0.0002)
    assert report.points[1].loss_factor == 10.2
    assert report.points[1].status == "completed"
    assert report.converged is True


def test_run_all_points_failed(tmp_path: Path) -> None:
    cr = _runner(tmp_path / "proj", _params())
    cr._run_single = Mock(side_effect=RuntimeError("solver crashed"))

    report = cr.run(mesh_factors=[2.0, 1.0], verbose=False)

    assert len(report.points) == 2
    assert all(p.status == "failed" for p in report.points)
    assert all(p.loss_factor is None for p in report.points)
    assert report.converged is False


def test_run_mixed_failed_and_completed(tmp_path: Path) -> None:
    cr = _runner(tmp_path / "proj", _params())
    cr._run_single = Mock(side_effect=[RuntimeError("boom"), 10.0, 10.2])

    report = cr.run(mesh_factors=[2.0, 1.0, 0.5], verbose=False)

    assert report.points[0].status == "failed"
    assert report.points[0].loss_factor is None
    assert report.points[1].status == "completed"
    assert report.points[1].loss_factor == 10.0
    assert report.points[2].loss_factor == 10.2
    # The failed coarse point is ignored; finest two still converge.
    assert report.converged is True


def test_run_single_point_not_converged(tmp_path: Path) -> None:
    cr = _runner(tmp_path / "proj", _params())
    cr._run_single = Mock(return_value=10.0)

    report = cr.run(mesh_factors=[1.0], verbose=False)

    assert len(report.points) == 1
    assert report.points[0].status == "completed"
    assert report.converged is False  # cannot converge with one point
