"""Grid convergence automation for ECHO2D simulations.

Provides :class:`ConvergenceRunner` for automated mesh-refinement studies.
Given a project with geometry and bunch configuration, runs ECHO2D at
multiple mesh resolutions and analyses the convergence of the loss factor
(or kick factor) to determine the optimal mesh settings.

Reference: ECHO Manual §1 (Introduction), which recommends 5 mesh points
on sigma as the default and doubling resolution to check convergence.

Usage::

    >>> from pyecho.converge import ConvergenceRunner
    >>> runner = ConvergenceRunner("my_project", mesh_factors=[0.5, 1.0, 2.0])
    >>> report = runner.run()
    >>> print(report.summary())
"""

from __future__ import annotations

import logging
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

from pyecho.config import load_params
from pyecho.project import (
    load_project,
    load_run_meta,
    list_runs,
)

logger = logging.getLogger(__name__)


@dataclass
class ConvergencePoint:
    """A single point in a convergence study."""

    label: str
    step_y: float
    step_z: float
    mesh_length: int
    loss_factor: float | None = None
    kick_factor: float | None = None
    elapsed_s: float = 0.0
    status: str = "pending"  # pending | completed | failed


@dataclass
class ConvergenceReport:
    """Results of a convergence study."""

    geometry_type: str
    base_sigma: float
    points: list[ConvergencePoint] = field(default_factory=list)

    @property
    def converged(self) -> bool:
        """Check if finest two meshes agree within 5%."""
        completed = [p for p in self.points if p.loss_factor is not None]
        if len(completed) < 2:
            return False
        loss_a = completed[-2].loss_factor
        loss_b = completed[-1].loss_factor
        if loss_a is None or loss_b is None or abs(loss_b) < 1e-30:
            return False
        return abs(loss_a - loss_b) / abs(loss_b) < 0.05

    def summary(self) -> str:
        """Generate a human-readable convergence summary."""
        lines = [
            f"Convergence Study ({self.geometry_type}, sigma={self.base_sigma:.4f} m)",
            f"{'Mesh':<12} {'h_y [m]':>10} {'h_z [m]':>10} {'Loss [V/pC]':>14} {'Time':>8}",
            f"{'-'*12} {'-'*10} {'-'*10} {'-'*14} {'-'*8}",
        ]
        for p in self.points:
            loss_str = f"{p.loss_factor:.6f}" if p.loss_factor is not None else "FAILED"
            lines.append(
                f"{p.label:<12} {p.step_y:>10.2e} {p.step_z:>10.2e} {loss_str:>14} {p.elapsed_s:>7.1f}s"
            )
        lines.append("")
        lines.append(f"Converged: {'YES' if self.converged else 'NO'} (<5% between finest meshes)")
        return "\n".join(lines)


class ConvergenceRunner:
    """Run an automated mesh-convergence study.

    Parameters
    ----------
    project_dir : str or Path
        Path to the ECHO2D project root (must contain .echo2d.yaml).
    run_ref : str, optional
        Run ID or path to use as the base configuration.  Defaults to
        the latest run in the project.
    """

    def __init__(
        self,
        project_dir: str | Path,
        run_ref: str | None = None,
    ) -> None:
        self.project_dir = Path(project_dir).resolve()
        self._proj = load_project(self.project_dir)

        # Find base run
        if run_ref:
            runs_dir = self.project_dir / "runs"
            for child in sorted(runs_dir.iterdir()):
                if child.is_dir() and child.name.startswith(run_ref):
                    self._base_run_dir = child
                    break
            else:
                raise ValueError(f"Run '{run_ref}' not found in {self.project_dir}")
        else:
            runs = list_runs(self.project_dir)
            if not runs:
                raise ValueError(f"No runs found in {self.project_dir}")
            latest = runs[-1]
            self._base_run_dir = self.project_dir / "runs" / latest.dir_name

        self._base_meta = load_run_meta(self._base_run_dir)
        self._base_params = load_params(self._base_run_dir / "input_in.txt")
        self._base_sigma = self._base_params.BunchSigma

    def run(
        self,
        mesh_factors: list[float] | None = None,
        modes: list[int] | None = None,
        threads: int = 1,
        verbose: bool = True,
    ) -> ConvergenceReport:
        """Run the convergence study.

        Parameters
        ----------
        mesh_factors : list[float], optional
            Factors to multiply the base mesh step by.  Default:
            ``[2.0, 1.0, 0.5]`` (coarse → fine, convergence direction).
        modes : list[int], optional
            Modes to compute.  Defaults to the base configuration modes.
        threads : int
            Number of OpenMP threads per run.
        verbose : bool
            Print progress to stdout.

        Returns
        -------
        ConvergenceReport
        """
        if mesh_factors is None:
            mesh_factors = [2.0, 1.0, 0.5]

        if modes is None:
            modes = self._base_params.Modes

        base_hy = self._base_params.StepY
        base_hz = self._base_params.StepZ
        base_mesh_len = self._base_params.MeshLength

        geo_type = self._base_meta.geometry_type
        report = ConvergenceReport(
            geometry_type=geo_type,
            base_sigma=self._base_sigma,
        )

        for factor in mesh_factors:
            hy = base_hy * factor
            hz = base_hz * factor
            mesh_len = max(10, int(base_mesh_len / factor))
            label = f"hx{factor:.1f}"

            if verbose:
                print(f"  [{label}] hy={hy:.2e}, hz={hz:.2e}, Nz={mesh_len} ... ",
                      end="", flush=True)

            point = ConvergencePoint(
                label=label,
                step_y=hy,
                step_z=hz,
                mesh_length=mesh_len,
            )

            t0 = time.monotonic()
            try:
                loss = self._run_single(
                    step_y=hy, step_z=hz, mesh_length=mesh_len,
                    modes=modes, threads=threads, label=label,
                )
                point.loss_factor = loss
                point.status = "completed"
            except Exception as exc:
                point.status = "failed"
                if verbose:
                    print(f"FAILED: {exc}")
                logger.warning("Convergence point %s failed: %s", label, exc)

            point.elapsed_s = time.monotonic() - t0
            report.points.append(point)

            if verbose and point.status == "completed":
                print(f"loss={loss:.6f} V/pC ({point.elapsed_s:.1f}s)")

        if verbose:
            print()
            print(report.summary())

        return report

    def _run_single(
        self, step_y: float, step_z: float, mesh_length: int,
        modes: list[int], threads: int, label: str,
    ) -> float:
        """Run a single ECHO2D simulation and return the loss factor."""
        from pyecho.runner import ECHO2DRunner
        from pyecho.api import quick_postprocess
        from pyecho.config import save_params

        # Create a temporary run directory
        conv_dir = self.project_dir / "runs" / f"_converge_{label}"
        if conv_dir.exists():
            shutil.rmtree(conv_dir)
        conv_dir.mkdir(parents=True, exist_ok=True)

        # Copy geometry file
        geom_name = self._base_params.GeometryFile
        geom_src = self._base_run_dir / geom_name
        if not geom_src.is_file():
            geom_src = self.project_dir / geom_name
        if geom_src.is_file():
            shutil.copy2(str(geom_src), str(conv_dir / geom_name))

        # Write modified input
        params = self._base_params.model_copy(update={
            "StepY": step_y, "StepZ": step_z,
            "MeshLength": mesh_length, "Modes": modes,
        })
        save_params(params, conv_dir / "input_in.txt")

        # Run ECHO2D
        runner = ECHO2DRunner(conv_dir)
        result = runner.run(params, np=threads, show_progress=False)

        # Postprocess
        geo_type = self._base_meta.geometry_type
        try:
            wake = quick_postprocess(str(conv_dir), geometry=geo_type)
            return wake.loss_long
        finally:
            shutil.rmtree(conv_dir, ignore_errors=True)


def run_convergence(
    project: str,
    mesh_factors: str = "2.0 1.0 0.5",
    modes: str | None = None,
    threads: int = 1,
) -> ConvergenceReport:
    """CLI entry point for convergence study.

    Parameters
    ----------
    project : str
        Project name or path.
    mesh_factors : str
        Space-separated mesh factors (e.g. ``"2.0 1.0 0.5"``).
    modes : str, optional
        Space-separated mode numbers.
    threads : int
        OpenMP threads per run.

    Returns
    -------
    ConvergenceReport
    """
    factors = [float(x) for x in mesh_factors.split()]
    mode_list = [int(x) for x in modes.split()] if modes else None

    runner = ConvergenceRunner(project)
    return runner.run(
        mesh_factors=factors,
        modes=mode_list,
        threads=threads,
        verbose=True,
    )
