"""Convergence analysis tools for ECHO2D mesh refinement studies.

Provides :class:`ConvergenceAnalyzer` to systematically scan mesh
parameters, run convergence tests, and estimate the numerical error
via Richardson extrapolation.

Usage::

    >>> from pyecho.converge import ConvergenceAnalyzer
    >>> from pyecho.config import ECHO2DParams
    >>> params = ECHO2DParams.from_template("round_collimator")
    >>> ca = ConvergenceAnalyzer(params)
    >>> results = ca.scan_mesh(points_on_sigma=[5, 10, 20])
    >>> ca.plot_convergence(metric="loss")
    >>> error_est = ca.estimate_error()
    >>> print(f"Estimated error: {error_est:.2e}")
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np

from pyecho.errors import PyEchoError

logger = logging.getLogger(__name__)


class ConvergenceAnalyzer:
    """Analyze convergence of ECHO2D results with mesh refinement.

    Runs a series of simulations with increasingly fine mesh resolution
    and analyses the convergence behaviour of key metrics (loss factor,
    kick factor) to estimate the numerical discretisation error.

    Parameters
    ----------
    base_params : ECHO2DParams
        Baseline simulation parameters.  The mesh steps (``StepY``,
        ``StepZ``) and ``NStepsInConductive`` are overridden during
        the scan.
    work_dir : str or Path, optional
        Parent directory for scan working directories.  If ``None``,
        a temporary directory is created.
    executable : str, optional
        Path to the ECHO2D binary.  Auto-detected if ``None``.
    np : int
        Number of OpenMP threads for each run.

    Attributes
    ----------
    base_params : ECHO2DParams
        The original (unmodified) base parameters.
    results : list[SimulationResult]
        Simulation results ordered by increasing mesh resolution.
    mesh_params : list[dict]
        Corresponding mesh parameter dicts for each result.

    Examples
    --------
    >>> ca = ConvergenceAnalyzer(params, np=4)
    >>> ca.scan_mesh(points_on_sigma=[5, 10, 20, 40])
    >>> ca.plot_convergence()
    >>> err = ca.estimate_error()
    """

    def __init__(
        self,
        base_params: Any,
        work_dir: str | Path | None = None,
        executable: str | None = None,
        np: int = 1,
    ) -> None:
        self.base_params = base_params
        self.np = np
        self.executable = executable

        if work_dir is None:
            import tempfile
            self._work_dir = Path(tempfile.mkdtemp(prefix="echo2d_conv_"))
            self._cleanup = True
        else:
            self._work_dir = Path(work_dir).resolve()
            self._work_dir.mkdir(parents=True, exist_ok=True)
            self._cleanup = False

        self.results: list[Any] = []
        self.mesh_params: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Mesh scan
    # ------------------------------------------------------------------

    def scan_mesh(
        self,
        points_on_sigma: list[int] | None = None,
        nsteps_conductive: list[int] | None = None,
    ) -> list[Any]:
        """Run convergence scan with different mesh resolutions.

        For each value in *points_on_sigma*, the mesh steps are set to
        ``sigma / n``, where *n* is the number of mesh points per RMS
        bunch length.

        Parameters
        ----------
        points_on_sigma : list[int], optional
            Number of mesh points per RMS bunch length.  Default is
            ``[5, 10, 20]``.
        nsteps_conductive : list[int], optional
            Values for ``NStepsInConductive`` to scan.  If ``None``,
            only the mesh steps are varied.

        Returns
        -------
        list[SimulationResult]
            Simulation results, one per mesh configuration, ordered
            from coarsest to finest.

        Raises
        ------
        PyEchoError
            If no runs complete successfully.
        """
        from pyecho.runner import ECHO2DRunner

        if points_on_sigma is None:
            points_on_sigma = [5, 10, 20]

        sigma = self.base_params.BunchSigma

        # Build mesh configurations
        configs: list[dict[str, Any]] = []
        for n in points_on_sigma:
            step = sigma / n
            cfg = {"StepY": step, "StepZ": step}
            if nsteps_conductive:
                for nc in nsteps_conductive:
                    c = cfg.copy()
                    c["NStepsInConductive"] = nc
                    configs.append(c)
            else:
                configs.append(cfg)

        logger.info(
            "Starting mesh convergence scan: %d configurations, "
            "sigma=%.3e m, points_on_sigma=%s",
            len(configs), sigma, points_on_sigma,
        )

        self.results = []
        self.mesh_params = []

        for i, cfg in enumerate(configs):
            run_dir = self._work_dir / f"mesh_{i:03d}"
            run_dir.mkdir(parents=True, exist_ok=True)

            # Copy base params and override mesh
            params = self.base_params.model_copy(update=cfg)

            logger.info(
                "Run %d/%d: StepY=%s, StepZ=%s",
                i + 1, len(configs),
                cfg.get("StepY", "default"),
                cfg.get("StepZ", "default"),
            )

            runner = ECHO2DRunner(
                run_dir,
                executable=self.executable,
            )

            try:
                result = runner.run(params=params, np=self.np)
                self.results.append(result)
                self.mesh_params.append(cfg)
            except Exception as exc:
                logger.warning("Run %d failed: %s", i + 1, exc)
                continue

        if not self.results:
            raise PyEchoError(
                "No convergence runs completed successfully."
            )

        logger.info(
            "Convergence scan complete: %d/%d runs succeeded",
            len(self.results), len(configs),
        )
        return self.results

    # ------------------------------------------------------------------
    # Convergence plot
    # ------------------------------------------------------------------

    def plot_convergence(
        self,
        metric: str = "loss",
        ax: Any = None,
    ) -> Any:
        """Plot convergence curve for a given metric.

        Parameters
        ----------
        metric : str
            Metric to plot: ``"loss"`` (loss factor) or ``"peak"``
            (peak wake amplitude).
        ax : matplotlib.axes.Axes, optional
            Existing axes to plot on.  If ``None``, a new figure and
            axes are created.

        Returns
        -------
        tuple
            ``(fig, ax)`` tuple from matplotlib.

        Examples
        --------
        >>> ca.plot_convergence(metric="loss")
        >>> import matplotlib.pyplot as plt
        >>> plt.show()
        """
        import matplotlib.pyplot as plt

        if not self.results:
            raise PyEchoError("No results available. Run scan_mesh() first.")

        # Extract metric values and mesh steps
        values: list[float] = []
        steps: list[float] = []
        for i, result in enumerate(self.results):
            step = self.mesh_params[i].get("StepY", 0.0)
            if step <= 0:
                continue
            try:
                v = _extract_metric(result, metric)
                if v is not None:
                    values.append(v)
                    steps.append(step)
            except Exception as exc:
                logger.debug("Could not extract metric from run %d: %s", i, exc)

        if not values:
            raise PyEchoError(f"Could not extract metric {metric!r} from any run.")

        steps_arr = np.array(steps)
        values_arr = np.array(values)

        if ax is None:
            fig, ax = plt.subplots(figsize=(8, 5))
        else:
            fig = ax.figure

        # Plot: metric vs 1/step (proportional to resolution)
        ax.plot(1.0 / steps_arr, values_arr, "o-", markersize=8, linewidth=1.5)
        ax.set_xlabel("1 / h  [m⁻¹]  (mesh resolution)")
        ax.set_ylabel(f"{metric} value")
        ax.set_title(f"ECHO2D Convergence — {metric}")
        ax.grid(True, alpha=0.3)

        # Also plot vs step size on top axis for reference
        ax2 = ax.twiny()
        ax2.set_xlim(ax.get_xlim())
        tick_positions = np.array(ax.get_xticks())
        tick_labels = [f"{1/t:.1e}" if t > 0 else "" for t in tick_positions]
        ax2.set_xticklabels(tick_labels)
        ax2.set_xlabel("h  [m]  (mesh step)")

        fig.tight_layout()
        return fig, ax

    # ------------------------------------------------------------------
    # Error estimation
    # ------------------------------------------------------------------

    def estimate_error(self, metric: str = "loss") -> float:
        """Estimate numerical error using Richardson extrapolation.

        Assumes the discretisation error scales as :math:`O(h^2)` for
        the second-order Yee scheme used by ECHO2D.  Fits the form
        :math:`f(h) = f_0 + C h^2` to the three finest meshes and
        returns :math:`|C h_{\\text{finest}}^2|` as the error estimate.

        Parameters
        ----------
        metric : str
            Metric to use: ``"loss"`` or ``"peak"``.

        Returns
        -------
        float
            Estimated absolute error of the finest-mesh result.

        Raises
        ------
        PyEchoError
            If fewer than 3 mesh levels are available.

        Notes
        -----
        For a second-order method:

        .. math::

            f(h) = f_{\\text{exact}} + A h^2 + O(h^4)

        Using two mesh levels :math:`h` and :math:`h/2`:

        .. math::

            f_{\\text{exact}} \\approx \\frac{4 f(h/2) - f(h)}{3}
        """
        if len(self.results) < 3:
            raise PyEchoError(
                "Richardson extrapolation requires at least 3 mesh levels. "
                f"Got {len(self.results)}."
            )

        # Extract (step, value) pairs sorted by increasing resolution
        pairs: list[tuple[float, float]] = []
        for i, result in enumerate(self.results):
            step = self.mesh_params[i].get("StepY", 0.0)
            if step <= 0:
                continue
            try:
                v = _extract_metric(result, metric)
                if v is not None:
                    pairs.append((step, v))
            except Exception:
                continue

        if len(pairs) < 3:
            raise PyEchoError(
                "Not enough valid metric values for Richardson extrapolation."
            )

        # Sort by step size (ascending = finest first)
        pairs.sort(key=lambda x: x[0])

        # Use the three finest meshes
        h = np.array([p[0] for p in pairs[:3]])
        f = np.array([p[1] for p in pairs[:3]])

        # Richardson extrapolation: f = f_exact + A*h^2
        # Build linear system for f_exact and A
        A_matrix = np.column_stack([np.ones(3), h**2])
        coeffs, residuals, rank, singular = np.linalg.lstsq(
            A_matrix, f, rcond=None
        )
        f_exact = coeffs[0]
        A_coeff = coeffs[1]

        error_est = abs(A_coeff * h[0]**2)

        logger.info(
            "Richardson extrapolation: f_exact=%.6e, A=%.6e, "
            "error_est(h=%.3e)=%.3e",
            f_exact, A_coeff, h[0], error_est,
        )

        return float(error_est)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_metric(result: Any, metric: str) -> float | None:
    """Extract a metric value from a SimulationResult."""
    if metric == "loss":
        # Try to get loss factor from mode 0's processed wake
        if 0 in result.modes:
            mode = result.modes[0]
            if mode.wake_processed is not None:
                return float(mode.wake_processed.loss_factor)
        # Fallback: compute from raw wake
        if 0 in result.modes:
            mode = result.modes[0]
            if mode.W_raw is not None and len(mode.W_raw) > 0:
                from pyecho.mathlib.integration import integr_tr
                return float(integr_tr(mode.W_raw))
    elif metric == "peak":
        if 0 in result.modes:
            mode = result.modes[0]
            if mode.wake_processed is not None:
                return float(mode.wake_processed.peak)
            if mode.W_raw is not None and len(mode.W_raw) > 0:
                return float(np.max(np.abs(mode.W_raw)))
    return None
