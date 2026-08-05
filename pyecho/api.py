"""High-level convenience API for common ECHO2D workflows.

Provides one-liner functions for simulation, post-processing, and
comparison tasks.  These functions orchestrate the lower-level modules
(``config``, ``runner``, ``parser``, ``visualize``, etc.) into concise
workflows.

Usage::

    >>> from pyecho.api import quick_simulate, quick_postprocess
    >>> result = quick_simulate("collimator.txt", sigma=0.001, modes=[0])
    >>> wake = quick_postprocess(result.output_dir)
    >>> print(f"Loss factor: {wake.loss_factor:.4f} V/pC")
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyecho.datamodel import SimulationResult, WakeResult, FlatWakeResult

logger = logging.getLogger(__name__)


def quick_simulate(
    geometry: str,
    sigma: float = 0.001,
    modes: list[int] | None = None,
    geometry_type: str = "round",
    step_y: float | None = None,
    step_z: float | None = None,
    executable: str | None = None,
    work_dir: str | None = None,
    np: int = 1,
    clean: bool = True,
) -> "SimulationResult":
    """One-line ECHO2D simulation.

    Auto-generates an ``input_in.txt``, runs ECHO2D, and loads the
    results.

    Parameters
    ----------
    geometry : str
        Path to the geometry file, or name of a built-in template
        (e.g., ``"round_collimator"``).
    sigma : float
        RMS bunch length [m].
    modes : list[int], optional
        Azimuthal modes to compute.  Defaults to ``[0]``.
    geometry_type : str
        ``"round"`` or ``"flat"``.
    step_y : float, optional
        Transverse mesh step [m].  Defaults to ``sigma / 5``.
    step_z : float, optional
        Longitudinal mesh step [m].  Defaults to ``sigma / 5``.
    executable : str, optional
        Path to the ECHO2D binary.  Auto-detected if ``None``.
    work_dir : str, optional
        Working directory.  A temporary directory is created if
        ``None`` (and cleaned up if *clean* is ``True``).
    np : int
        Number of OpenMP threads.
    clean : bool
        If ``True`` and *work_dir* is ``None``, remove the temporary
        directory after loading results.

    Returns
    -------
    SimulationResult
        Complete simulation result.

    Raises
    ------
    RunnerError
        If the simulation fails.
    """
    from pyecho.config import ECHO2DParams
    from pyecho.runner import ECHO2DRunner

    if modes is None:
        modes = [0]

    mesh_step = sigma / 5.0
    step_y = step_y or mesh_step
    step_z = step_z or mesh_step

    # Determine template
    if geometry_type == "flat":
        template_name = "flat_absorber"
    else:
        template_name = "round_collimator"

    params = ECHO2DParams.from_template(
        template_name,
        BunchSigma=sigma,
        Modes=modes,
        StepY=step_y,
        StepZ=step_z,
        GeometryFile=geometry,
        GeometryType="round" if geometry_type == "round" else "recta",
    )

    # Handle work directory
    _cleanup = False
    if work_dir is None:
        work_dir_path = Path(tempfile.mkdtemp(prefix="echo2d_"))
        _cleanup = clean
    else:
        work_dir_path = Path(work_dir)
        work_dir_path.mkdir(parents=True, exist_ok=True)

    try:
        # Copy geometry file if it's an external file
        geom_path = Path(geometry)
        if geom_path.is_file() and geom_path.parent != work_dir_path:
            import shutil
            dest = work_dir_path / geom_path.name
            shutil.copy2(geom_path, dest)
            params.GeometryFile = geom_path.name

        runner = ECHO2DRunner(work_dir_path, executable)
        result = runner.run(params, np=np)
    finally:
        if _cleanup:
            import shutil
            try:
                shutil.rmtree(work_dir_path)
            except OSError:
                logger.warning("Could not clean up temp dir: %s", work_dir_path)

    return result


def quick_postprocess(
    output_dir: str,
    geometry: str | None = None,
    **kwargs,
) -> "RoundWakeResult | FlatWakeResult":
    """One-line postprocessing of ECHO2D output.

    Auto-detects the geometry type and applies the appropriate
    post-processing pipeline.

    Parameters
    ----------
    output_dir : str
        Path to the ECHO2D output directory.
    geometry : str, optional
        ``"round"`` or ``"flat"``.  Auto-detected if ``None``.
    **kwargs
        Additional arguments passed to the post-processor.

    Returns
    -------
    RoundWakeResult or FlatWakeResult
        Processed wake result.
    """
    from pyecho.parser import OutputLoader

    loader = OutputLoader(output_dir)
    if geometry is not None:
        geo_type = geometry
    else:
        # Auto-detect using PostProcessor
        from pyecho.postprocess import PostProcessor
        geo_type = PostProcessor(loader).geometry_type

    if geo_type in ("round",):
        return _postprocess_round(loader, **kwargs)
    elif geo_type in ("recta", "flat", "magn", "elec"):
        # Accept "flat" as legacy alias for backward compatibility
        return _postprocess_flat(loader, **kwargs)
    else:
        # Try round first, then recta
        try:
            return _postprocess_round(loader, **kwargs)
        except Exception:
            return _postprocess_flat(loader, **kwargs)


def compare_runs(
    output_dirs: list[str],
    labels: list[str] | None = None,
    mode: int = 0,
) -> dict:
    """Compare wake results from multiple simulation runs.

    Parameters
    ----------
    output_dirs : list[str]
        Paths to output directories.
    labels : list[str], optional
        Labels for each run.
    mode : int
        Azimuthal mode to compare (0 = monopole, 1 = dipole).

    Returns
    -------
    dict
        Keys: ``s`` (common s-grid), ``W_list``, ``labels``,
        ``losses``.
    """
    import numpy as np
    from pyecho.postprocess import PostProcessor

    w_list: list[np.ndarray] = []
    s_common: np.ndarray | None = None
    losses: list[float] = []

    if labels is None:
        labels = [f"Run {i}" for i in range(len(output_dirs))]

    for d in output_dirs:
        try:
            pp = PostProcessor(d)
            if mode == 1:
                dipole = pp.process_wake_dipole()
                wake = dipole["longitudinal"]
            else:
                wake = pp.process_wake_monopole()

            s = wake.s
            W = wake.W
            loss = wake.loss_factor
        except Exception as exc:
            logger.warning("Cannot load wake from %s: %s", d, exc)
            continue

        if s_common is None:
            s_common = s
        w_list.append(W)
        losses.append(loss)

    return {
        "s": s_common,
        "W_list": w_list,
        "labels": labels,
        "losses": losses,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _postprocess_round(
    loader,
    **kwargs,
) -> "RoundWakeResult":
    """Post-process round-geometry results.

    Returns a :class:`RoundWakeResult` containing monopole (m=0)
    longitudinal wake and optionally dipole (m=1) modal coefficient
    and kick factor.
    """
    from pyecho.datamodel import RoundWakeResult
    from pyecho.postprocess import PostProcessor

    pp = PostProcessor(loader)
    all_wakes = loader.load_all_wakes()
    if not all_wakes:
        raise ValueError("No wake files found in output directory.")

    available_modes = sorted(all_wakes.keys())

    # Monopole (m=0) — longitudinal wake potential
    mono = pp.process_wake_monopole()

    Wdipole = None
    kick_dipole = None

    # Dipole (m=1) — modal coefficient + kick
    if 1 in available_modes:
        try:
            dipole = pp.process_wake_dipole()
            Wdipole = dipole["longitudinal"].W
            kick_dipole = dipole["transverse"].loss_factor
        except Exception:
            logger.warning("Dipole (m=1) processing failed; monopole result is still valid.")

    return RoundWakeResult(
        s=mono.s,
        Wlong=mono.W,
        Wdipole=Wdipole,
        loss_long=mono.loss_factor,
        kick_dipole=kick_dipole,
        bunch=mono.bunch,
        peak=mono.peak,
        rms_spread=mono.rms_spread,
    )


def _postprocess_flat(
    loader,
    **kwargs,
) -> "FlatWakeResult":
    """Post-process flat-geometry results.

    Uses the full flat-geometry pipeline (Wcc/Wss assembly, mode
    summation, and cumulative integration) to produce Wlong, Wquad,
    and Wdipole in their correct physical units.
    """
    from pyecho.datamodel import FlatWakeResult
    from pyecho.postprocess import PostProcessor
    import numpy as np

    pp = PostProcessor(loader)
    result = pp.process_flat_wake()

    s = result["s"]
    Wlong = result["Wlong"]
    Wquad = result["Wquad"]
    Wdipole = result.get("Wdipole", np.zeros_like(Wlong))

    # Compute loss/kick factors via trapezoidal integration
    def _trapz(y: "np.ndarray", x: "np.ndarray") -> float:
        """Trapezoidal integration (compatible with numpy 1.x and 2.x)."""
        return float(0.5 * np.sum((y[1:] + y[:-1]) * (x[1:] - x[:-1])))

    loss_long = -_trapz(Wlong, s)
    kick_quad = -_trapz(Wquad, s)
    kick_dipole = -_trapz(Wdipole, s)

    return FlatWakeResult(
        s=s,
        Wlong=Wlong,
        Wquad=Wquad,
        Wdipole=Wdipole,
        loss_long=loss_long,
        kick_quad=kick_quad,
        kick_dipole=kick_dipole,
        wcc=result.get("wcc"),
        wss=result.get("wss"),
    )
