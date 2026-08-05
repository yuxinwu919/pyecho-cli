"""Field monitor post-processing.

Replicates ECHO2D's field monitor MATLAB scripts:
* ``PP_FieldMonitor_rect.m``  — rectangular geometry field extraction
* ``PP_FieldMonitor_round.m`` — round geometry field extraction
* ``PP_CreateTotalField_EzEyBx.m`` — modal field synthesis

Field monitors in ECHO2D record electromagnetic field components on
a 2-D (or 3-D) grid.  This module provides point extraction via 2-D
interpolation and modal field synthesis for recta (rectangular) geometries.

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
        # If t is given, interpolate at fixed (t, z, r) → scalar
        # If t is None but z,r given, extract 1-D trace over time
        if t is not None:
            # Single point interpolation
            points = [t]
            axes = [T]
            if z is not None:
                points.append(z); axes.append(Z)
            if r is not None:
                points.append(r); axes.append(R)
            interp = RegularGridInterpolator(
                tuple(axes), F, bounds_error=False, fill_value=0.0
            )
            return float(interp(np.atleast_2d(points))[0])
        elif z is not None and r is not None:
            # Extract 1-D trace over time at fixed (z, r)
            interp_zr = RegularGridInterpolator(
                (Z, R), F[0, :, :], bounds_error=False, fill_value=0.0
            )
            # Verify z,r are within bounds
            trace = np.zeros(len(T), dtype=np.float64)
            for i in range(len(T)):
                trace[i] = float(interp_zr(np.array([[z, r]]))[0])
            return trace
        elif z is not None:
            # Extract 2-D (t, z) slice at fixed r
            r_mid = float(np.median(R))
            interp_z = RegularGridInterpolator(
                (Z,), np.zeros(len(Z)), bounds_error=False, fill_value=0.0
            )
            r_idx = int(np.interp(r_mid, R, np.arange(len(R))))
            return F[:, :, r_idx]  # (nt, nz) slice
        elif r is not None:
            # Extract 2-D (t, r) slice at fixed z
            z_mid = float(np.median(Z))
            z_idx = int(np.interp(z_mid, Z, np.arange(len(Z))))
            return F[:, z_idx, :]  # (nt, nr) slice
        else:
            return F

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

    In a recta (rectangular) structure of width *D*, the total field at
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


# ---------------------------------------------------------------------------
# Point monitor extraction (replicates PP_FieldMonitor_rect.m / _round.m)
# ---------------------------------------------------------------------------

def extract_point_monitor(
    monitor: MonitorData,
    z: float,
    r: float,
    geometry: str = "recta",
) -> tuple[np.ndarray, np.ndarray]:
    """Extract a 1-D field trace at a fixed point (z, r) over all time steps.

    Replicates the MATLAB ``interp2`` loop in ``PP_FieldMonitor_rect.m``
    and ``PP_FieldMonitor_round.m``.

    For z-type monitors, the lab-frame position is reconstructed as
    ``z_lab = mesh_pos(i) + Z`` (MATLAB's ``MeshPos+Z`` shift).
    For s-type monitors, the window is static so ``mesh_pos = 0``.

    In round geometry, the Ep (E_phi) component is stored as Ep×r by
    ECHO2D.  The extracted value is divided by r to recover the physical
    Ep field (except at r=0 where Ep=0).  Magnetic field components
    (Bx/By/Bz) are stored as cB with the same units as E.

    Parameters
    ----------
    monitor : MonitorData
        Parsed field monitor.
    z : float
        Fixed longitudinal coordinate [m].
    r : float
        Fixed transverse coordinate [m] (radial for round, y for recta).
    geometry : str
        ``"round"`` or ``"recta"``.

    Returns
    -------
    T : np.ndarray
        Time (or ct) coordinates [m] for each time step.
    trace : np.ndarray
        Extracted field values at (z, r) for each time step.
    """
    from scipy.interpolate import RegularGridInterpolator

    F = monitor.F
    T = monitor.T
    Z = monitor.Z
    R = monitor.R

    nt = len(T)
    trace = np.zeros(nt, dtype=np.float64)

    if F.ndim != 3:
        raise ValueError(f"Expected 3-D monitor data (nt,nz,nr), got shape {F.shape}")

    # For z-type monitors, reconstruct lab-frame z using mesh position
    mesh_pos = getattr(monitor, "_mesh_pos", None)
    if mesh_pos is None:
        mesh_pos = np.zeros(nt, dtype=np.float64)

    for i in range(nt):
        z_lab = mesh_pos[i] + Z
        # MATLAB: FF = -F(i, 1:kr*kz); FF = reshape(FF, kz, kr)'
        # Note the TRANSPOSE: MATLAB reshape in column-major gives different
        # ordering. Our F is (nt, nz, nr), so F[i, :, :] directly works.
        FF = F[i, :, :]  # (nz, nr)
        interp = RegularGridInterpolator(
            (z_lab, R), FF, bounds_error=False, fill_value=0.0
        )
        trace[i] = float(-interp(np.array([[z, r]]))[0])  # MATLAB negates

    # Round Ep component: ECHO2D stores Ep*r, divide to get physical Ep
    comp = monitor.field_component.upper()
    if geometry == "round" and comp == "EP":
        if abs(r) > 1e-30:
            trace = trace / r
        # (at r=0, Ep=0 physically, trace stays 0)

    return T, trace


def save_point_monitor(
    out_path: Path,
    T: np.ndarray,
    trace: np.ndarray,
    component: str = "Ez",
    geometry: str = "recta",
) -> None:
    """Save point monitor trace in MATLAB-compatible ``PointMonitor.txt`` format.

    Two-column ASCII: ``ct [m]   Field/Q [V/m/nC]`` (same as MATLAB output).

    Parameters
    ----------
    out_path : Path
        Output file path.
    T : np.ndarray
        Time coordinates [s or m].
    trace : np.ndarray
        Field values.
    component : str
        Field component label (e.g. "Ez", "Ep").
    geometry : str
        ``"round"`` or ``"recta"``.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    header = f"% PointMonitor: {component} at fixed (z,r)\n% ct [m]  Field/Q [V/m/nC]"
    data = np.column_stack([T, trace])
    np.savetxt(str(out_path), data, header=header, fmt="%.8e")


# ---------------------------------------------------------------------------
# Animation (replicates MATLAB mesh + pause loop)
# ---------------------------------------------------------------------------

def _plot_field_2d(
    ax: "plt.Axes",
    Z: np.ndarray,
    R: np.ndarray,
    F_slice: np.ndarray,
    vmin: float | None = None,
    vmax: float | None = None,
    n_contours: int = 15,
) -> "plt.Axes":
    """Plot a 2-D field slice with smooth interpolation + contour overlay.

    Uses ``pcolormesh`` with gouraud shading for smooth rendering and
    overlays contour lines to show field structure clearly.  This
    replicates the visual clarity of MATLAB's ``mesh``/``contourf``.

    Parameters
    ----------
    ax : plt.Axes
        Matplotlib axes to draw on.
    Z : np.ndarray
        1-D longitudinal coordinate array [mm].
    R : np.ndarray
        1-D transverse coordinate array [mm].
    F_slice : np.ndarray
        2-D field data with shape ``(nz, nr)`` (will be transposed if
        needed to match ``(len(R), len(Z))`` for pcolormesh).
    vmin, vmax : float, optional
        Color scale limits.  If None, use data min/max.
    n_contours : int
        Number of contour levels to overlay.

    Returns
    -------
    plt.Axes
    """
    # Transpose: pcolormesh expects (nr, nz) for 1-D X=z, Y=r
    if F_slice.shape == (len(Z), len(R)):
        F_plot = F_slice.T
    elif F_slice.shape == (len(R), len(Z)):
        F_plot = F_slice
    else:
        F_plot = F_slice.T

    # Gouraud shading for smooth interpolation between grid points
    Z_mm = Z * 1e3
    R_mm = R * 1e3

    if vmin is None:
        vmin = float(np.min(F_plot))
    if vmax is None:
        vmax = float(np.max(F_plot))

    im = ax.pcolormesh(Z_mm, R_mm, F_plot,
                       shading="gouraud", cmap="RdBu_r",
                       vmin=vmin, vmax=vmax)

    # Contour overlay for clear field structure
    levels = np.linspace(vmin, vmax, n_contours)
    ax.contour(Z_mm, R_mm, F_plot, levels=levels,
               colors="black", linewidths=0.4, alpha=0.5)

    return ax


def animate_field_monitor(
    monitor: MonitorData,
    output: str | None = None,
    fps: int = 10,
    geometry: str = "recta",
) -> None:
    """Create an animated field monitor visualization.

    Iterates over time steps, plotting a 2-D pseudocolor slice at each
    step.  For z-type monitors, shows the moving-window position.
    Supports saving to GIF or MP4.

    Parameters
    ----------
    monitor : MonitorData
        Parsed field monitor (must be 3-D: nt × nz × nr).
    output : str, optional
        Save animation to file (``.gif`` or ``.mp4``).
    fps : int
        Frames per second for the output animation.
    geometry : str
        ``"round"`` or ``"recta"``.  Affects axis labels and units.
    """
    import matplotlib
    matplotlib.use("Agg")  # non-interactive backend for headless animation
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation

    F = monitor.F
    if F.ndim != 3:
        raise ValueError(f"Animation requires 3-D monitor, got shape {F.shape}")

    nt, nz, nr = F.shape
    Z = monitor.Z
    R = monitor.R
    mesh_pos = getattr(monitor, "_mesh_pos", np.zeros(nt))

    # Subsample to keep GIF size reasonable (max ~30 frames)
    step = max(1, nt // 30)
    frames = list(range(0, nt, step))
    n_frames = len(frames)

    vmin, vmax = float(np.min(F)), float(np.max(F))
    comp = monitor.field_component
    r_label = "r [mm]" if geometry == "round" else "y [mm]"
    z_label = "z [mm]" if monitor.time_type == "s" else "s [mm]"

    fig, ax = plt.subplots(figsize=(10, 6))
    _plot_field_2d(ax, Z, R, F[0, :, :], vmin=vmin, vmax=vmax)
    fig.colorbar(ax.collections[0], ax=ax, label=f"{comp}")
    ax.set_xlabel(z_label)
    ax.set_ylabel(r_label)
    title = ax.set_title("")

    def update(idx):
        frame = frames[idx]
        ax.clear()
        _plot_field_2d(ax, Z, R, F[frame, :, :], vmin=vmin, vmax=vmax)
        pos = mesh_pos[frame] if monitor.time_type == "z" else 0.0
        ax.set_title(
            f"{comp} — frame {frame}/{nt}, "
            f"ct={monitor.T[frame]*1e3:.1f}mm, "
            f"z_pos={pos*1e3:.1f}mm"
        )
        ax.set_xlabel(z_label)
        ax.set_ylabel(r_label)

    ani = FuncAnimation(fig, update, frames=n_frames, interval=1000//fps, blit=False)

    if output:
        if output.endswith(".gif"):
            ani.save(output, writer="pillow", fps=fps, dpi=100)
        elif output.endswith(".mp4"):
            ani.save(output, writer="ffmpeg", fps=fps, dpi=150)
        else:
            output_gif = output.rsplit(".", 1)[0] + ".gif"
            ani.save(output_gif, writer="pillow", fps=fps, dpi=100)
        plt.close(fig)
    else:
        plt.show()


def plot_field_3d(
    monitor: MonitorData,
    time_step: int = 0,
    output: str | None = None,
    geometry: str = "recta",
) -> None:
    """Plot a 3-D surface of the field monitor at a single time step.

    Uses matplotlib ``plot_surface`` for a mesh-like rendering
    (replicates MATLAB ``mesh(z, r, F)``).

    Parameters
    ----------
    monitor : MonitorData
        Parsed field monitor.
    time_step : int
        Time step index for 3-D data.
    output : str, optional
        Save plot to file.
    geometry : str
        ``"round"`` or ``"recta"``.
    """
    import matplotlib.pyplot as plt

    F = monitor.F
    if F.ndim != 3:
        raise ValueError(f"3-D surface requires 3-D monitor, got shape {F.shape}")

    idx = min(time_step, F.shape[0] - 1)
    # Transpose for surface plot: (nr, nz) order
    F_plot = F[idx, :, :].T
    Z_mm = monitor.Z * 1e3
    R_mm = monitor.R * 1e3
    Zg, Rg = np.meshgrid(Z_mm, R_mm, indexing="xy")

    fig = plt.figure(figsize=(12, 8))
    ax = fig.add_subplot(111, projection="3d")
    surf = ax.plot_surface(Zg, Rg, F_plot, cmap="RdBu_r",
                           linewidth=0, antialiased=True,
                           rstride=1, cstride=1, alpha=0.9)
    # Add contour projection on the bottom
    ax.contour(Zg, Rg, F_plot, zdir='z', offset=F_plot.min(),
               levels=15, cmap='RdBu_r', alpha=0.3, linewidths=0.5)
    fig.colorbar(surf, ax=ax, shrink=0.5, aspect=10, label=monitor.field_component)
    ax.set_xlabel("z [mm]" if monitor.time_type == "s" else "s [mm]")
    r_label = "r [mm]" if geometry == "round" else "y [mm]"
    ax.set_ylabel(r_label)
    ax.set_zlabel(monitor.field_component)
    ax.view_init(elev=25, azim=-60)
    ax.set_title(f"{monitor.field_component} — t={monitor.T[idx]*1e3:.1f}mm")
    fig.tight_layout()

    if output:
        fig.savefig(output, dpi=150, bbox_inches="tight")
        plt.close(fig)
    else:
        plt.show()
