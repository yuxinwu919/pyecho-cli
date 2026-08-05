"""Field monitor post-processing.

Replicates ECHO2D's field monitor MATLAB scripts:
* ``PP_FieldMonitor_rect.m``  — rectangular geometry field extraction
* ``PP_FieldMonitor_round.m`` — round geometry field extraction
* ``PP_CreateTotalField_EzEyBx.m`` — modal field synthesis

Field monitors in ECHO2D record electromagnetic field components on
a 2-D (or 3-D) grid.  This module provides point extraction via 2-D
interpolation and modal field synthesis for flat geometries.

References
----------
* ``Examples/N8_FlatTaperWithFieldMonitor/PostProcessor2D/PP_FieldMonitor_rect.m``
* ``Examples/N1_RoundCollimatorLong/PostProcessor2D/PP_FieldMonitor_round.m``
* ``Examples/N6_PohangDechirper/PostProcessor2D/PP_CreateTotalField_EzEyBx.m``
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Sequence

import numpy as np
from scipy.interpolate import RegularGridInterpolator

from pyecho.datamodel import MonitorData
from pyecho.errors import PostProcessError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Point extraction from field monitors
# ---------------------------------------------------------------------------


def extract_field_at_point(
    monitor: MonitorData,
    t: float | None = None,
    z: float | None = None,
    r: float | None = None,
) -> float:
    """Extract the field value at a specific (t, z, r) point using linear
    interpolation.

    Replicates the logic in ``PP_FieldMonitor_rect.m`` and
    ``PP_FieldMonitor_round.m`` which extract a 1-D trace from a 2-D
    monitor slice by interpolating at fixed transverse/longitudinal
    coordinates.

    Parameters
    ----------
    monitor : MonitorData
        A parsed monitor data container.
    t : float, optional
        Time (or *s*) coordinate [s or m].  If ``None``, extracts
        the full slice at the given *(z, r)* point.
    z : float, optional
        Longitudinal coordinate [m].  If ``None``, averages or
        interpolates across *z*.
    r : float, optional
        Transverse (radial or *y*) coordinate [m].

    Returns
    -------
    float or np.ndarray
        Interpolated field value.  If *t* is ``None`` and the monitor
        has a time axis, returns a 1-D array over time.

    Notes
    -----
    Uses :class:`scipy.interpolate.RegularGridInterpolator` with linear
    interpolation, equivalent to MATLAB's ``interp2`` with ``'linear'``.
    """
    F = monitor.F
    T = monitor.T
    Z = monitor.Z
    R = monitor.R

    # Determine which axes we have
    if F.ndim == 1:
        # 1-D trace: assume it's along time or s
        if t is not None:
            interp = RegularGridInterpolator(
                (T,), F, bounds_error=False, fill_value=0.0
            )
            return float(interp(np.atleast_1d(t))[0])
        else:
            return F

    if F.ndim == 2:
        # 2-D: (nt, nspace) where nspace could be nz or nr
        # Try to determine if second axis is Z or R by comparing sizes
        nrows, ncols = F.shape
        if ncols == len(R):
            # (nt, nr) — fixed z
            if t is not None and r is not None:
                interp = RegularGridInterpolator(
                    (T, R), F, bounds_error=False, fill_value=0.0
                )
                return float(interp(np.array([[t, r]]))[0])
            elif r is not None:
                # Extract 1-D at fixed r over time
                interp_r = np.interp(r, R, np.arange(len(R)))
                idx_lo = int(np.floor(interp_r))
                idx_hi = min(idx_lo + 1, len(R) - 1)
                frac = interp_r - idx_lo
                return F[:, idx_lo] * (1 - frac) + F[:, idx_hi] * frac
            elif t is not None:
                interp = RegularGridInterpolator(
                    (T, R), F, bounds_error=False, fill_value=0.0
                )
                r_mid = float(np.median(R))
                return float(interp(np.array([[t, r_mid]]))[0])
            else:
                return F
        elif ncols == len(Z):
            # (nt, nz) — fixed r
            if t is not None and z is not None:
                interp = RegularGridInterpolator(
                    (T, Z), F, bounds_error=False, fill_value=0.0
                )
                return float(interp(np.array([[t, z]]))[0])
            elif z is not None:
                interp_z = np.interp(z, Z, np.arange(len(Z)))
                idx_lo = int(np.floor(interp_z))
                idx_hi = min(idx_lo + 1, len(Z) - 1)
                frac = interp_z - idx_lo
                return F[:, idx_lo] * (1 - frac) + F[:, idx_hi] * frac
            else:
                return F

    if F.ndim == 3:
        # 3-D: (nt, nz, nr) — full 3-D monitor
        points = []
        axes = []
        if t is not None:
            points.append(t)
            axes.append(T)
        if z is not None:
            points.append(z)
            axes.append(Z)
        if r is not None:
            points.append(r)
            axes.append(R)

        if len(points) == 0:
            return F

        interp = RegularGridInterpolator(
            tuple(axes), F, bounds_error=False, fill_value=0.0
        )
        return float(interp(np.atleast_2d(points))[0])

    logger.warning(
        "Unsupported monitor dimensionality %dD; returning raw data.", F.ndim
    )
    return F


def process_field_monitor(
    monitor: MonitorData,
    point_t: float | None = None,
    point_z: float | None = None,
    point_r: float | None = None,
) -> dict:
    """Extract field trace from a field monitor.

    High-level wrapper around :func:`extract_field_at_point` that
    returns a dictionary with coordinate arrays and field values.

    Parameters
    ----------
    monitor : MonitorData
        Parsed monitor data.
    point_t : float, optional
        Fixed time (or *s*) coordinate [s or m].
    point_z : float, optional
        Fixed longitudinal coordinate [m].
    point_r : float, optional
        Fixed transverse coordinate [m].

    Returns
    -------
    dict
        Keys: ``component`` (str), ``coords`` (list of np.ndarray),
        ``field`` (np.ndarray), ``point`` (dict of fixed coordinates used).
    """
    field = extract_field_at_point(monitor, t=point_t, z=point_z, r=point_r)

    coords = []
    if point_t is None and hasattr(monitor, "T") and len(monitor.T) > 1:
        coords.append(monitor.T)
    if point_z is None and hasattr(monitor, "Z") and len(monitor.Z) > 1:
        coords.append(monitor.Z)
    if point_r is None and hasattr(monitor, "R") and len(monitor.R) > 1:
        coords.append(monitor.R)

    return {
        "component": monitor.field_component,
        "coords": coords,
        "field": field if isinstance(field, np.ndarray) else np.array([field]),
        "point": {
            "t": point_t,
            "z": point_z,
            "r": point_r,
        },
    }


# ---------------------------------------------------------------------------
# Modal field synthesis (PP_CreateTotalField_EzEyBx.m)
# ---------------------------------------------------------------------------


def synthesize_total_field(
    monitor_files: list[str | Path],
    x0: float = 0.0,
    x: float = 0.0,
    n_modes: int = 35,
    D: float | None = None,
) -> np.ndarray:
    """Synthesize the total field from modal monitor files.

    Replicates ``PP_CreateTotalField_EzEyBx.m`` exactly.

    In a flat rectangular structure of width *D*, the total field at
    transverse position *x* for a source at *x0* is::

        F_total = (2/D) * Σ_m F_m * sin(k_m*(x0 + D/2)) * sin(k_m*(x + D/2))

    where :math:`k_m = \\pi \\cdot m / D`, m = 1, 3, 5, ..., 2*Nm-1.
    The ``+D/2`` shift accounts for the side-wall boundary condition
    (see PRSTAB 18 (2015) 104401, Eq. 3).

    Parameters
    ----------
    monitor_files : list of str or Path
        Paths to monitor files for modes 1, 3, 5, ..., in order.
    x0 : float
        Source transverse offset [m] (beam position).
    x : float
        Observation transverse position [m].
    n_modes : int
        Number of odd modes to include.  Default 35 (MATLAB convention).
    D : float, optional
        Structure width [m].  If ``None``, auto-detected from the first
        file's ``width=...`` header.

    Returns
    -------
    np.ndarray
        Synthesised total field array, same shape as each modal field
        (including the leading coordinate column if present).

    Raises
    ------
    PostProcessError
        If monitor files cannot be read or have inconsistent shapes.
    """
    if len(monitor_files) == 0:
        raise PostProcessError("No monitor files provided for synthesis.")

    total_field: np.ndarray | None = None
    prev_norm: float | None = None

    for i, fpath in enumerate(monitor_files[:n_modes]):
        fpath = Path(fpath)
        if not fpath.exists():
            logger.warning("Monitor file %s not found; skipping.", fpath)
            continue

        try:
            data = np.loadtxt(fpath, comments="%")
        except Exception as exc:
            raise PostProcessError(f"Failed to load {fpath}: {exc}") from exc

        m = 2 * i + 1  # odd mode: 1, 3, 5, ...

        # Auto-detect D from first file header
        if D is None and i == 0:
            D = _parse_width_from_monitor(fpath)
            if D is None:
                raise PostProcessError(
                    "Cannot determine structure width D from monitor files. "
                    "Please provide the `D` parameter explicitly."
                )

        # Leading column (ct or z-position) excluded from field data
        # (MATLAB: F(:,2:p) = ... where p = kz*kr+1)
        if data.shape[1] > 1:
            field_only = data[:, 1:]
        else:
            field_only = data

        k_m = np.pi / D * m
        # MATLAB weight: sin(k_m*(x0 + D/2)) * sin(k_m*(x + D/2))
        weight = np.sin(k_m * (x0 + 0.5 * D)) * np.sin(k_m * (x + 0.5 * D))

        weighted = field_only * weight
        norm = float(np.linalg.norm(weighted))

        if total_field is None:
            total_field = weighted
            prev_norm = norm
        else:
            if weighted.shape != total_field.shape:
                raise PostProcessError(
                    f"Shape mismatch in mode {m}: {weighted.shape} vs "
                    f"{total_field.shape}"
                )
            total_field += weighted
            # MATLAB convergence check: err = (N-N1)/N*100
            if prev_norm and prev_norm > 0:
                err_pct = abs(norm - prev_norm) / norm * 100
                logger.debug("Mode %d: norm error %.2f%%", m, err_pct)
            prev_norm = norm

    if total_field is None:
        raise PostProcessError("No valid monitor data loaded for synthesis.")

    # Apply 2/D normalisation (MATLAB: F(:,2:p) = F(:,2:p)/D*2)
    total_field = total_field * (2.0 / D)

    return total_field


def _parse_width_from_monitor(filepath: Path) -> float | None:
    """Extract structure width D from a monitor file header.

    Looks for ``width=X.XXXe+XX`` in the first ``% Field=...`` header line.
    """
    try:
        with open(filepath, "r", encoding="utf-8") as fh:
            first_line = fh.readline().strip()
    except OSError:
        return None
    if not first_line.startswith("%"):
        return None
    # "% Field=Ez time=z  width=5.000000e-02"
    for token in first_line.lstrip("%").strip().split():
        if token.startswith("width="):
            try:
                return float(token.split("=", 1)[1])
            except (ValueError, IndexError):
                pass
    return None


def synthesize_total_field_from_loader(
    magn_dir: str | Path,
    component: str = "Ez",
    monitor_id: int = 1,
    x0: float = 0.0,
    x: float = 0.0,
    n_modes: int = 35,
    D: float | None = None,
) -> np.ndarray:
    """Convenience wrapper that loads monitor files automatically.

    Given a directory containing ``Monitor_mXX_NYY.txt`` files for
    the magnetic (cos-cos) geometry, synthesise the total field.

    Parameters
    ----------
    magn_dir : str or Path
        Directory with monitor files.
    component : str
        Field component label (e.g. ``"Ez"``, ``"Ey"``, ``"Hx"``).
    monitor_id : int
        Monitor index (N in Monitor_mXX_NYY.txt).
    x0 : float
        Source transverse offset [m] (beam position).
    x : float
        Observation transverse position [m].
    n_modes : int
        Number of odd modes to include.  Default 35 (MATLAB convention).
    D : float, optional
        Structure width [m].  Auto-detected from first file if None.

    Returns
    -------
    np.ndarray
        Synthesised total field (2-D: n_time × n_space).

    Raises
    ------
    PostProcessError
        If no monitor files are found.
    """
    magn_dir = Path(magn_dir)
    files: list[Path] = []
    for i in range(1, n_modes + 1):
        m = 2 * i - 1
        # ECHO2D produces zero-padded filenames: Monitor_m09_N01.txt
        # Try zero-padded first, then unpadded (backward compatibility)
        fname = f"Monitor_m{m:02d}_N{monitor_id:02d}.txt"
        fname_with_comp = f"Monitor_m{m:02d}_N{monitor_id:02d}_{component}.txt"
        candidate = magn_dir / fname_with_comp
        if not candidate.exists():
            candidate = magn_dir / fname
        if not candidate.exists():
            # Fallback: unpadded legacy format
            candidate = magn_dir / f"Monitor_m{m}_N{monitor_id}_{component}.txt"
            if not candidate.exists():
                candidate = magn_dir / f"Monitor_m{m}_N{monitor_id}.txt"
        if candidate.exists():
            files.append(candidate)
        else:
            logger.debug("Monitor file for mode %d not found, stopping.", m)
            break

    if not files:
        raise PostProcessError(
            f"No monitor files found in {magn_dir} for component={component}, "
            f"monitor_id={monitor_id}"
        )

    return synthesize_total_field(
        [str(f) for f in files],
        x0=x0,
        x=x,
        n_modes=len(files),
        D=D,
    )
