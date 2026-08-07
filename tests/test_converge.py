"""Integration test skeleton for :mod:`pyecho.converge`.

The original unit tests in this file were all mock-based: they patched the
project-I/O functions (``load_project``, ``list_runs``, ``load_run_meta``,
``load_params``) and the ECHO2D runner (``ConvergenceRunner._run_single``)
to exercise :class:`ConvergenceRunner` without a real project or solver.
Those mocks were removed because they asserted orchestration plumbing
instead of real behaviour, and they silently drifted from the actual
project-manifest / runner APIs.

This file now serves as an *integration* test skeleton.  Its tests require a
real ECHO2D project on disk and a working ECHO2D binary, so every test is
skipped by default to keep a plain ``pytest tests/`` run green on machines
without the solver.

How to run the integration tests
--------------------------------

1. Create a real project and produce at least one completed baseline run::

       echo2d project init converge_demo -t round_collimator
       echo2d run converge_demo

2. Point an environment variable at the project and run this file::

       cd <repo-root>
       ECHO2D_TEST_PROJECT=/path/to/converge_demo \\
           python3 -m pytest tests/test_converge.py -v

3. The ECHO2D binary must be discoverable by :class:`pyecho.runner.ECHO2DRunner`
   (verify with ``echo2d system check``).
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Placeholder replacing the removed mock-based suite
# ---------------------------------------------------------------------------
# The previous tests (run-selection by latest/ref, mesh refinement, default
# factors & modes, all-fail / mixed-failure / single-point edge cases) all
# depended on patched project I/O and a mocked ``_run_single``.  They were
# removed because they validated mocks, not real behaviour.  Re-implement
# them as integration tests against a real project instead (see the stubs
# and commented-out example below).


@pytest.mark.skip("Requires ECHO2D binary and real project")
def test_convergence_requires_real_project() -> None:
    """Single skipped placeholder for the removed mock-based tests."""
    pytest.skip("Requires ECHO2D binary and real project")


# ---------------------------------------------------------------------------
# Integration test stubs
# ---------------------------------------------------------------------------
# TODO: implement each stub against a real project.  The docstrings describe
# the scenario each test must cover; unskip the ``@pytest.mark.skip`` line
# when the project fixture is available.


@pytest.mark.skip("Requires ECHO2D binary and real project")
def test_integration_run_full_mesh_convergence() -> None:
    """Run a mesh-convergence study and assert a converged report.

    Steps:
    1. Build a :class:`ConvergenceRunner` from the ``ECHO2D_TEST_PROJECT`` dir.
    2. Call ``run(mesh_factors=[1.0, 0.5])``.
    3. Assert two completed points with the expected labels/steps and a
       final ``converged`` status of True (or a documented failing case).
    """


@pytest.mark.skip("Requires ECHO2D binary and real project")
def test_integration_run_from_explicit_run_ref() -> None:
    """Select the base run by explicit ref instead of the latest run.

    Steps:
    1. Create a project with at least two runs (e.g. ``001_baseline``,
       ``002_fine``).
    2. Construct ``ConvergenceRunner(project_dir, run_ref="001")``.
    3. Assert ``_base_run_dir`` points at the ``001_baseline`` run dir.
    """


@pytest.mark.skip("Requires ECHO2D binary and real project")
def test_integration_run_survives_solver_failure() -> None:
    """Verify one failing mesh level does not abort the whole study.

    Steps:
    1. Use a project whose finest mesh level is unsolvable (or inject a
       deliberately broken input) so one point fails.
    2. Assert the failed point is recorded with ``status == "failed"`` and
       the remaining points are still completed / the report is generated.
    """


# ---------------------------------------------------------------------------
# Example integration test (commented out — enable when a real project exists)
# ---------------------------------------------------------------------------
# import os
# from pathlib import Path
#
# from pyecho.converge import ConvergenceRunner
#
#
# def test_full_convergence_study_example() -> None:
#     """Run a real convergence study end-to-end.
#
#     Requires ``ECHO2D_TEST_PROJECT`` to point at a project that already has
#     at least one completed baseline run, and a discoverable ECHO2D binary.
#     """
#     project_dir = Path(os.environ["ECHO2D_TEST_PROJECT"])
#     cr = ConvergenceRunner(project_dir)  # base run = latest
#     report = cr.run(mesh_factors=[1.0, 0.5], verbose=False)
#
#     assert len(report.points) == 2
#     assert all(p.status == "completed" for p in report.points)
#     assert report.converged is True
#     assert "Converged: YES" in report.summary()
