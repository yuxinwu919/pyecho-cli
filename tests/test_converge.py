"""Mock-based unit tests for :mod:`pyecho.converge`.

Exercises :class:`ConvergenceRunner` without a real ECHO2D project or solver:

* Project I/O (``load_project``, ``list_runs``, ``load_run_meta``,
  ``load_params``) is patched via ``mock.patch.multiple``.
* The solver step (``ConvergenceRunner._run_single``) is replaced with a mock
  returning a float loss factor.  This matches the real implementation, where
  ``run()`` assigns the returned value straight to ``point.loss_factor``.
"""

from __future__ import annotations

from unittest import mock

import pytest

from pyecho.config import ECHO2DParams
from pyecho.converge import ConvergencePoint, ConvergenceReport, ConvergenceRunner
from pyecho.project import ProjectManifest, RunManifest, SubRunInfo


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

def _make_params(**overrides: object) -> ECHO2DParams:
    """Build an ECHO2DParams for a round-collimator-style base run."""
    defaults: dict[str, object] = {
        "GeometryType": "round",
        "GeometryFile": "collimator.txt",
        "BunchSigma": 0.001,
        "Modes": [0],
        "MeshLength": 52,
        "StepY": 0.0002,
        "StepZ": 0.0002,
    }
    defaults.update(overrides)
    return ECHO2DParams(**defaults)


def _make_run_manifest() -> RunManifest:
    """Build a completed baseline run manifest."""
    return RunManifest(
        id="001",
        name="baseline",
        geometry_type="round",
        sub_runs=[
            SubRunInfo(symmetry="magn", output_dir="round/", status="completed"),
        ],
    )


def _make_project_manifest(run: RunManifest) -> ProjectManifest:
    """Build a project manifest containing *run*."""
    return ProjectManifest(name="test_proj", geometry_type="round", runs=[run])


@pytest.fixture
def mocked_io() -> dict[str, mock.Mock]:
    """Patch the project-I/O imports so no real project or disk is needed.

    Yields the patch dictionary (``load_project``, ``list_runs``,
    ``load_run_meta``, ``load_params``) so tests can tweak return values.
    """
    run = _make_run_manifest()
    project = _make_project_manifest(run)
    params = _make_params()
    with mock.patch.multiple(
        "pyecho.converge",
        load_project=mock.DEFAULT,
        list_runs=mock.DEFAULT,
        load_run_meta=mock.DEFAULT,
        load_params=mock.DEFAULT,
    ) as patched:
        patched["load_project"].return_value = project
        patched["list_runs"].return_value = [run]
        patched["load_run_meta"].return_value = run
        patched["load_params"].return_value = params
        yield patched


@pytest.fixture
def make_runner(mocked_io: dict[str, mock.Mock]):
    """Build a ConvergenceRunner backed by the mocked project I/O."""

    def _make(
        run_ref: str | None = None,
        project_dir: str = "/fake/proj",
    ) -> ConvergenceRunner:
        return ConvergenceRunner(project_dir, run_ref=run_ref)

    return _make


# ---------------------------------------------------------------------------
# Mesh refinement behaviour
# ---------------------------------------------------------------------------

def test_default_mesh_factors(make_runner) -> None:
    """Default refinement runs factors [2.0, 1.0, 0.5] (coarse -> fine)."""
    runner = make_runner()
    with mock.patch.object(ConvergenceRunner, "_run_single") as run_single:
        run_single.side_effect = [1.0, 1.0, 1.0]
        report = runner.run(verbose=False)

    assert [p.label for p in report.points] == ["hx2.0", "hx1.0", "hx0.5"]
    # base StepY = 0.0002 m, scaled by each factor
    assert [p.step_y for p in report.points] == pytest.approx(
        [0.0004, 0.0002, 0.0001]
    )
    # mesh_length = max(10, int(52 / factor))
    assert [p.mesh_length for p in report.points] == [26, 52, 104]


def test_mesh_refinement_strategy(make_runner, mocked_io) -> None:
    """step_y/step_z scale with the factor and mesh_length grows for fine meshes."""
    mocked_io["load_params"].return_value = _make_params(
        StepY=0.001, StepZ=0.002, MeshLength=100
    )
    runner = make_runner()
    with mock.patch.object(ConvergenceRunner, "_run_single") as run_single:
        run_single.side_effect = [1.0, 1.0]
        report = runner.run(mesh_factors=[1.0, 0.5], verbose=False)

    assert [p.step_y for p in report.points] == pytest.approx([0.001, 0.0005])
    assert [p.step_z for p in report.points] == pytest.approx([0.002, 0.001])
    assert [p.mesh_length for p in report.points] == [100, 200]


def test_custom_mesh_factors(make_runner) -> None:
    """User-provided factors override the default refinement sequence."""
    runner = make_runner()
    with mock.patch.object(ConvergenceRunner, "_run_single") as run_single:
        run_single.return_value = 1.0
        report = runner.run(mesh_factors=[3.0, 1.0], verbose=False)

    assert [p.label for p in report.points] == ["hx3.0", "hx1.0"]
    assert [p.step_y for p in report.points] == pytest.approx([0.0006, 0.0002])
    assert [p.mesh_length for p in report.points] == [17, 52]  # int(52 / 3) = 17


def test_mesh_length_floor(make_runner) -> None:
    """mesh_length is floored at 10 grid lines for very coarse factors."""
    runner = make_runner()
    with mock.patch.object(ConvergenceRunner, "_run_single") as run_single:
        run_single.return_value = 1.0
        report = runner.run(mesh_factors=[10.0], verbose=False)

    assert report.points[0].mesh_length == 10  # int(52 / 10) = 5 -> floored
    assert report.points[0].step_y == pytest.approx(0.002)


# ---------------------------------------------------------------------------
# Convergence decision
# ---------------------------------------------------------------------------

def test_converged_true(make_runner) -> None:
    """Loss factors 1.0 vs 1.03 agree within 5% -> converged."""
    runner = make_runner()
    with mock.patch.object(ConvergenceRunner, "_run_single") as run_single:
        run_single.side_effect = [1.0, 1.03]
        report = runner.run(mesh_factors=[1.0, 0.5], verbose=False)

    assert report.converged is True
    assert [p.status for p in report.points] == ["completed", "completed"]


def test_converged_false(make_runner) -> None:
    """Loss factors 1.0 vs 1.20 differ by more than 5% -> not converged."""
    runner = make_runner()
    with mock.patch.object(ConvergenceRunner, "_run_single") as run_single:
        run_single.side_effect = [1.0, 1.20]
        report = runner.run(mesh_factors=[1.0, 0.5], verbose=False)

    assert report.converged is False


def test_single_mesh_point(make_runner) -> None:
    """A single mesh point can never be converged (<2 completed points)."""
    runner = make_runner()
    with mock.patch.object(ConvergenceRunner, "_run_single") as run_single:
        run_single.return_value = 1.0
        report = runner.run(mesh_factors=[1.0], verbose=False)

    assert len(report.points) == 1
    assert report.points[0].status == "completed"
    assert report.converged is False


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------

def test_run_method_returns_report(make_runner) -> None:
    """Full pipeline with a mocked ``_run_single`` returns a populated report."""
    runner = make_runner()
    with mock.patch.object(ConvergenceRunner, "_run_single") as run_single:
        run_single.side_effect = [1.0, 1.01, 1.03]
        report = runner.run(verbose=False)

    assert isinstance(report, ConvergenceReport)
    assert report.geometry_type == "round"
    assert report.base_sigma == pytest.approx(0.001)
    assert len(report.points) == 3
    assert all(p.status == "completed" for p in report.points)
    assert [p.loss_factor for p in report.points] == pytest.approx(
        [1.0, 1.01, 1.03]
    )
    assert report.converged is True


def test_all_runs_fail(make_runner) -> None:
    """Every solver run failing is recorded as FAILED, not a crash."""
    runner = make_runner()

    def _boom(*args: object, **kwargs: object) -> float:
        raise RuntimeError("solver crashed")

    with mock.patch.object(ConvergenceRunner, "_run_single") as run_single:
        run_single.side_effect = _boom
        report = runner.run(verbose=False)

    assert all(p.status == "failed" for p in report.points)
    assert all(p.loss_factor is None for p in report.points)
    assert report.converged is False
    assert "FAILED" in report.summary()


# ---------------------------------------------------------------------------
# Report summary
# ---------------------------------------------------------------------------

def test_report_summary_content() -> None:
    """The summary renders the header, per-point rows and FAILED markers."""
    report = ConvergenceReport(
        geometry_type="round",
        base_sigma=0.001,
        points=[
            ConvergencePoint(
                label="hx1.0", step_y=0.0002, step_z=0.0002,
                mesh_length=52, loss_factor=1.0, elapsed_s=1.5,
                status="completed",
            ),
            ConvergencePoint(
                label="hx0.5", step_y=0.0001, step_z=0.0001,
                mesh_length=104, status="failed",
            ),
        ],
    )
    summary = report.summary()

    assert "Convergence Study" in summary
    assert "round" in summary
    assert "sigma=0.0010" in summary
    assert "hx1.0" in summary
    assert "hx0.5" in summary
    assert "FAILED" in summary
    assert "Converged: NO" in summary


# ---------------------------------------------------------------------------
# Base-run selection
# ---------------------------------------------------------------------------

def test_run_ref_selects_base_run(mocked_io, tmp_path) -> None:
    """run_ref selects the matching run dir instead of the latest run."""
    proj_dir = tmp_path / "proj"
    (proj_dir / "runs" / "001_baseline").mkdir(parents=True)
    (proj_dir / "runs" / "002_fine").mkdir(parents=True)

    runner = ConvergenceRunner(str(proj_dir), run_ref="002")

    assert runner._base_run_dir == proj_dir / "runs" / "002_fine"
    mocked_io["list_runs"].assert_not_called()


def test_run_ref_not_found_raises(mocked_io, tmp_path) -> None:
    """An unknown run_ref raises ValueError during construction."""
    proj_dir = tmp_path / "proj"
    (proj_dir / "runs").mkdir(parents=True)

    with pytest.raises(ValueError, match="not found"):
        ConvergenceRunner(str(proj_dir), run_ref="999")
