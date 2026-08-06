"""Visualization functions for ECHO2D simulation results.

Provides plotting utilities for wake potentials, geometry files,
field monitor data, and multi-result comparisons.  All functions
return ``(fig, ax)`` tuples for further customisation.

Uses a clean scientific plotting style consistent with accelerator
physics conventions.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import numpy as np

from pyecho.errors import GeometryError

if TYPE_CHECKING:
    import matplotlib.pyplot as plt
    from pyecho.datamodel import MonitorData, SimulationResult, WakeResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Style defaults
# ---------------------------------------------------------------------------

#: Default figure size for wake plots.
_DEFAULT_FIGSIZE: tuple[int, int] = (10, 5)

#: Default figure size for geometry plots.
_DEFAULT_GEO_FIGSIZE: tuple[int, int] = (12, 4)

#: Default figure size for field plots.
_DEFAULT_FIELD_FIGSIZE: tuple[int, int] = (10, 6)


def _get_matplotlib() -> tuple[Any, Any]:
    """Lazy-import matplotlib."""
    import matplotlib.pyplot as plt
    return None, plt


# ---------------------------------------------------------------------------
# plot_wake_round
# ---------------------------------------------------------------------------

def plot_wake_round(
    result_or_s: Any,
    W: np.ndarray | None = None,
    *,
    bunch: np.ndarray | None = None,
    title: str = "",
    xlabel: str = "s [mm]",
    ylabel: str = "Wake potential [V/pC]",
    ax: "plt.Axes | None" = None,
    show_loss: bool = True,
    figsize: tuple[int, int] = _DEFAULT_FIGSIZE,
) -> tuple["plt.Figure", "plt.Axes"]:
    """Plot wake potential with optional bunch shape overlay.

    Parameters
    ----------
    result_or_s : SimulationResult, WakeResult, ModeResult, or np.ndarray
        Either a result object with ``s`` and ``W`` attributes, or the
        *s*-coordinate array directly.
    W : np.ndarray, optional
        Wake potential array [V/pC].  Required if *result_or_s* is an
        array.
    bunch : np.ndarray, optional
        Bunch charge-density profile (same length as *s*).
    title : str
        Plot title.
    xlabel : str
        X-axis label.
    ylabel : str
        Y-axis label.
    ax : plt.Axes, optional
        Existing axes to draw on.
    show_loss : bool
        If ``True`` and the result has a ``loss_factor`` attribute,
        annotate the plot with the loss factor.
    figsize : tuple
        Figure size ``(width, height)`` in inches.

    Returns
    -------
    tuple[plt.Figure, plt.Axes]
    """
    _, plt = _get_matplotlib()
    s, w = _extract_s_w(result_or_s, W)

    # Auto-extract bunch from result object if not explicitly provided
    if bunch is None and not isinstance(result_or_s, np.ndarray):
        obj = result_or_s
        # WakeResult has .bunch
        if hasattr(obj, "bunch"):
            bunch = obj.bunch
        # ModeResult / SimulationResult chain
        elif hasattr(obj, "wake_processed") and obj.wake_processed:
            bunch = obj.wake_processed.bunch
        elif hasattr(obj, "modes"):
            modes = obj.modes
            if modes:
                first = next(iter(modes.values()))
                if first.wake_processed:
                    bunch = first.wake_processed.bunch

    if ax is None:
        fig, ax = plt.subplots(figsize=figsize)
    else:
        fig = ax.figure

    ax.plot(s * 1e3, w, "b-", linewidth=1.5, label="Wake potential")
    ax.axhline(y=0, color="gray", linestyle="--", linewidth=0.8)

    if bunch is not None:
        # Scale bunch to match wake magnitude (same as MATLAB convention)
        B = np.asarray(bunch, dtype=float)
        B_max: float = np.max(np.abs(B))
        w_max: float = np.max(np.abs(w))
        if B_max > 0 and w_max > 0:
            K = w_max / B_max
            B_scaled = B * K
        else:
            B_scaled = B
        ax.plot(
            s * 1e3,
            B_scaled,
            "k-",
            linewidth=1.2,
            label="Bunch shape",
        )

    # Try to annotate loss factor
    if show_loss:
        loss = _extract_loss(result_or_s)
        if loss is not None:
            # Auto-detect units from result object
            loss_units = _extract_units(result_or_s) or "V/pC"
            ax.text(
                0.98,
                0.95,
                f"Loss = {loss:.4f} {loss_units}",
                transform=ax.transAxes,
                ha="right",
                va="top",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8),
            )

    # Auto-detect ylabel from result units if not explicitly overridden
    if ylabel == "Wake potential [V/pC]" and not isinstance(result_or_s, np.ndarray):
        auto_units = _extract_units(result_or_s)
        if auto_units and auto_units != "V/pC":
            ylabel = f"Wake potential [{auto_units}]"
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title or "Wake Potential")
    ax.legend(loc="best")
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    return fig, ax


# ---------------------------------------------------------------------------
# plot_round_wake
# ---------------------------------------------------------------------------

def plot_round_wake(
    result: Any,
    *,
    title: str = "",
    figsize: tuple[int, int] = (10, 8),
    bunch: np.ndarray | None = None,
) -> tuple["plt.Figure", "np.ndarray"]:
    """Plot round-geometry wake potentials in subplots.

    Parameters
    ----------
    result : RoundWakeResult
        Result from :func:`pyecho.api.quick_postprocess` with round geometry.
    title : str
        Overall figure title.
    figsize : tuple
        Figure size ``(width, height)`` in inches.
    bunch : np.ndarray, optional
        Bunch current profile (same length as wake arrays).  If not
        provided, auto-extracted from ``result.bunch``.

    Returns
    -------
    tuple[plt.Figure, np.ndarray of plt.Axes]
    """
    import numpy as np
    _, plt = _get_matplotlib()

    has_dipole = result.Wdipole is not None
    n_panels = 2 if has_dipole else 1
    fig, axes = plt.subplots(n_panels, 1, figsize=figsize, sharex=True)
    if n_panels == 1:
        axes = np.array([axes])

    s_mm = result.s * 1e3  # m → mm

    # ── Top: monopole (m=0) — longitudinal wake ──
    axes[0].plot(s_mm, result.Wlong, "b-", linewidth=1.5)
    axes[0].axhline(y=0, color="gray", linestyle="--", linewidth=0.8)
    axes[0].set_ylabel("Longitudinal wake potential [V/pC]")
    axes[0].grid(True, alpha=0.3)
    axes[0].text(
        0.98, 0.95, f"Loss_long = {result.loss_long:.4f} V/pC",
        transform=axes[0].transAxes, ha="right", va="top",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8),
    )

    # ── Bottom: dipole (m=1) — modal coefficient ──
    if has_dipole:
        axes[1].plot(s_mm, result.Wdipole, "r-", linewidth=1.5)
        axes[1].axhline(y=0, color="gray", linestyle="--", linewidth=0.8)
        axes[1].set_ylabel("Dipole wake potential [V/pC/m²]")
        axes[1].grid(True, alpha=0.3)
        if result.kick_dipole is not None:
            axes[1].text(
                0.98, 0.95, f"Kick_dipole = {result.kick_dipole:.4f} V/pC/m",
                transform=axes[1].transAxes, ha="right", va="top",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8),
            )

    # ── Bunch overlay ──
    if bunch is None:
        bunch = result.bunch
    if bunch is not None:
        b_max: float = np.max(np.abs(bunch))
        for i, ax in enumerate(axes):
            W_data = result.Wlong if i == 0 else result.Wdipole
            w_max: float = np.max(np.abs(W_data))
            bunch_scaled = bunch * (w_max / b_max) if b_max > 0 and w_max > 0 else bunch
            ax.plot(s_mm, bunch_scaled, "k-", linewidth=1.2, alpha=0.6,
                    label="Bunch (Iz0)")
        axes[0].legend(loc="upper left", fontsize=8)

    axes[-1].set_xlabel("s [mm]")
    if title:
        fig.suptitle(title, fontsize=13, fontweight="bold")
    fig.tight_layout()
    return fig, axes


# ---------------------------------------------------------------------------
# plot_flat_wake
# ---------------------------------------------------------------------------

def plot_flat_wake(
    result: Any,
    *,
    title: str = "",
    figsize: tuple[int, int] = (12, 10),
    bunch: np.ndarray | None = None,
) -> tuple["plt.Figure", "plt.Axes"]:
    """Plot rectangular-geometry wake potentials in three subplots.

    Parameters
    ----------
    result : FlatWakeResult
        Result from :func:`pyecho.api.quick_postprocess` with rectangular geometry.
    title : str
        Overall figure title.
    figsize : tuple
        Figure size ``(width, height)`` in inches.
    bunch : np.ndarray, optional
        Bunch current profile (same length as ``result.s``).  If provided,
        overlaid as a black solid line on all three subplots.

    Returns
    -------
    tuple[plt.Figure, np.ndarray of plt.Axes]
    """
    import numpy as np
    _, plt = _get_matplotlib()

    s_m = result.s  # in meters
    s = s_m * 1e3  # m → mm
    components = [
        (result.Wlong, result.loss_long, "Longitudinal wake [V/pC]", f"Loss_long = {result.loss_long:.6f} V/pC"),
        (result.Wquad, result.kick_quad, "Quadrupole wake [V/pC/mm]", f"Kick_quad = {result.kick_quad:.6f} V/pC/mm"),
        (result.Wdipole, result.kick_dipole, "Dipole wake [V/pC/mm]", f"Kick_dipole = {result.kick_dipole:.6f} V/pC/mm"),
    ]

    fig, axes = plt.subplots(3, 1, figsize=figsize, sharex=True)
    if title:
        fig.suptitle(title, fontsize=13, fontweight="bold")

    for ax, (W, kappa, ylabel, klabel) in zip(axes, components):
        ax.plot(s, W, "b-", linewidth=1.5)
        ax.axhline(y=0, color="gray", linestyle="--", linewidth=0.8)
        ax.set_ylabel(ylabel)
        ax.grid(True, alpha=0.3)
        ax.text(
            0.98, 0.95, klabel,
            transform=ax.transAxes, ha="right", va="top",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8),
            fontsize=9,
        )

    # Overlay bunch profile on all three subplots
    if bunch is not None:
        for ax, (W, _, _, _) in zip(axes, components):
            w_max: float = np.max(np.abs(W))
            b_max: float = np.max(np.abs(bunch))
            if b_max > 0 and w_max > 0:
                bunch_scaled = bunch * (w_max / b_max)
            else:
                bunch_scaled = bunch
            ax.plot(s, bunch_scaled, "k-", linewidth=1.2, alpha=0.6,
                    label="Bunch (Iz0)")
        axes[0].legend(loc="upper left", fontsize=8)

    axes[-1].set_xlabel("s [mm]")
    fig.tight_layout()
    return fig, axes


# ---------------------------------------------------------------------------
# plot_geometry
# ---------------------------------------------------------------------------

def plot_geometry(
    geometry_file: str | Path,
    *,
    units: str = "cm",
    ax: "plt.Axes | None" = None,
    show_materials: bool = True,
    figsize: tuple[int, int] = _DEFAULT_GEO_FIGSIZE,
) -> tuple["plt.Figure", "plt.Axes"]:
    """Plot ECHO2D geometry from a geometry file.

    Parameters
    ----------
    geometry_file : str or Path
        Path to the ``.txt`` geometry file.
    units : str
        Display units: ``"cm"``, ``"mm"``, or ``"m"``.
    ax : plt.Axes, optional
        Existing axes to draw on.
    show_materials : bool
        If ``True``, shade regions by material.
    figsize : tuple
        Figure size ``(width, height)`` in inches.

    Returns
    -------
    tuple[plt.Figure, plt.Axes]
    """
    from pyecho.geometry import load_geometry

    _, plt = _get_matplotlib()

    scale = _units_scale(units)

    try:
        geo = load_geometry(geometry_file)
    except Exception as exc:
        raise GeometryError(f"Cannot load geometry: {exc}") from exc

    if ax is None:
        fig, ax = plt.subplots(figsize=figsize)
    else:
        fig = ax.figure

    # Plot geometry as a boundary profile
    z_all: list[float] = []
    r_all: list[float] = []

    colors = plt.cm.tab10.colors if show_materials else ["blue"]

    for mat_idx, material in enumerate(geo.get("materials", [])):
        color = colors[mat_idx % len(colors)]
        for seg_idx in material.get("segments", []):
            seg = geo["segments"][seg_idx]
            z1 = seg["z1"] * scale
            z2 = seg["z2"] * scale
            r1 = seg["r1"] * scale
            r2 = seg["r2"] * scale

            ax.plot([z1, z2], [r1, r2], color=color, linewidth=2)

            if show_materials:
                # Shade the region below the wall
                ax.fill_between(
                    [z1, z2],
                    [0, 0],
                    [r1, r2],
                    alpha=0.15,
                    color=color,
                )

            z_all.extend([z1, z2])
            r_all.extend([r1, r2])

    # Draw axis of symmetry
    if z_all:
        ax.axhline(y=0, color="black", linewidth=0.5, linestyle="-")
        ax.set_xlim(min(z_all) * 0.95, max(z_all) * 1.05)
        ax.set_ylim(0, max(r_all) * 1.15)

    ax.set_xlabel(f"z [{units}]")
    ax.set_ylabel(f"r [{units}]" if geo.get("materials") else f"y [{units}]")
    ax.set_title(f"ECHO2D Geometry: {Path(geometry_file).name}")
    ax.set_aspect("equal" if units == "cm" else "auto")
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    return fig, ax


# ---------------------------------------------------------------------------
# plot_field
# ---------------------------------------------------------------------------

def plot_field(
    monitor: "MonitorData",
    *,
    time_step: int = 0,
    ax: "plt.Axes | None" = None,
    figsize: tuple[int, int] = _DEFAULT_FIELD_FIGSIZE,
) -> tuple["plt.Figure", "plt.Axes"]:
    """Plot field monitor data at a specific time step.

    Parameters
    ----------
    monitor : MonitorData
        Field monitor data container.
    time_step : int
        Index of the time step to display.
    ax : plt.Axes, optional
        Existing axes to draw on.
    figsize : tuple
        Figure size ``(width, height)`` in inches.

    Returns
    -------
    tuple[plt.Figure, plt.Axes]
    """
    _, plt = _get_matplotlib()

    if ax is None:
        fig, ax = plt.subplots(figsize=figsize)
    else:
        fig = ax.figure

    F = monitor.F
    if F.ndim == 3:
        field_slice = F[time_step, :, :]
    elif F.ndim == 2:
        field_slice = F
    else:
        field_slice = F

    Z_1d = monitor.Z
    R_1d = monitor.R

    # Use gouraud-shaded pcolormesh with contour overlay for smooth rendering
    # pcolormesh: X=z (nz,), Y=r (nr,), C needs (nr, nz)
    if field_slice.shape == (len(Z_1d), len(R_1d)):
        F_plot = field_slice.T
    elif field_slice.shape == (len(R_1d), len(Z_1d)):
        F_plot = field_slice
    else:
        # Fallback: line plot along z
            ax.plot(monitor.Z * 1e3, field_slice[0, :] if field_slice.ndim == 2 else field_slice)
            ax.set_ylabel(f"{monitor.field_component}")
            ax.set_xlabel("z [mm]")
            ax.set_title(
                f"{monitor.field_component} — Monitor {monitor.monitor_id}"
            )
            ax.grid(True, alpha=0.3)
            fig.tight_layout()
            return fig, ax

    Z_mm = Z_1d * 1e3
    R_mm = R_1d * 1e3
    vmin, vmax = float(np.min(F_plot)), float(np.max(F_plot))

    im = ax.pcolormesh(Z_mm, R_mm, F_plot,
                       shading="gouraud", cmap="RdBu_r",
                       vmin=vmin, vmax=vmax)
    levels = np.linspace(vmin, vmax, 15)
    ax.contour(Z_mm, R_mm, F_plot, levels=levels,
               colors="black", linewidths=0.4, alpha=0.5)

    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label(monitor.field_component)
    ax.set_xlabel("z [mm]" if monitor.time_type == "s" else "s [mm]")
    ax.set_ylabel("r/mm")
    ax.set_title(
        f"{monitor.field_component} — t = {monitor.T[time_step]:.3e} s"
    )
    ax.set_aspect("auto")

    fig.tight_layout()
    return fig, ax


# ---------------------------------------------------------------------------
# plot_comparison
# ---------------------------------------------------------------------------

def plot_comparison(
    results: list[tuple[str, np.ndarray, np.ndarray]],
    *,
    labels: list[str] | None = None,
    title: str = "",
    difference: bool = False,
    figsize: tuple[int, int] = _DEFAULT_FIGSIZE,
    ax: "plt.Axes | None" = None,
) -> tuple["plt.Figure", "plt.Axes"]:
    """Compare multiple wake results on the same plot.

    Parameters
    ----------
    results : list[tuple]
        List of ``(label, s_array, W_array)`` tuples, or list of
        objects with ``s``, ``W``, and ``label`` attributes.
    labels : list[str], optional
        Override labels for each result.
    title : str
        Plot title.
    difference : bool
        If ``True``, plot the difference of each result relative to
        the first.
    figsize : tuple
        Figure size ``(width, height)`` in inches.

    Returns
    -------
    tuple[plt.Figure, plt.Axes]
    """
    _, plt = _get_matplotlib()

    if ax is None:
        fig, ax = plt.subplots(figsize=figsize)
    else:
        fig = ax.figure

    n = len(results)
    colors = plt.cm.viridis(np.linspace(0, 1, max(n, 1)))

    ref_w = None
    for i, item in enumerate(results):
        if isinstance(item, tuple) and len(item) == 3:
            label, s, w = item
        else:
            # Assume object with attributes
            label = getattr(item, "label", f"Result {i}")
            s = getattr(item, "s", None)
            w = getattr(item, "W", getattr(item, "W_raw", None))

        if s is None or w is None:
            logger.warning("Skipping result %d: missing s or W", i)
            continue

        if labels and i < len(labels):
            label = labels[i]

        if difference and i > 0 and ref_w is not None:
            w = w - ref_w
            label = f"Δ({label})"
        elif difference and i == 0:
            ref_w = w.copy()
            label = f"{label} (reference)"

        ax.plot(s * 1e3, w, color=colors[i], linewidth=1.5, label=label)

    ax.axhline(y=0, color="gray", linestyle="--", linewidth=0.8)
    ax.set_xlabel("s [mm]")
    ax.set_ylabel("Wake potential [V/pC]" if not difference else "Δ Wake potential [V/pC]")
    ax.set_title(title or "Wake Potential Comparison")
    ax.legend(loc="best")
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    return fig, ax


# ---------------------------------------------------------------------------
# plot_wake_modes
# ---------------------------------------------------------------------------

def plot_wake_modes(
    data_dir: str | Path,
    *,
    n_modes: int | None = None,
    show_bunch: bool = True,
    title: str = "",
    figsize: tuple[int, int] = _DEFAULT_FIGSIZE,
    ax: "plt.Axes | None" = None,
) -> tuple["plt.Figure", "plt.Axes"]:
    """Plot each Fourier mode's wake contribution on the same 2D axes.

    For recta (rectangular) geometry, each odd mode m=1,3,5,... is
    drawn as a different coloured line.  The bunch profile from
    ``Iz0.txt`` is optionally overlaid (dashed curve) for reference.

    This replaces the MATLAB 3D mesh with an easier-to-read 2D
    line plot.  Modes are shown as raw modal wakes — no offset
    normalisation is applied (that step belongs to the post-processing
    pipeline, not visualisation).

    Parameters
    ----------
    data_dir : str or Path
        Path to ``magn/`` or ``elec/`` with ``wakeL_XX.txt`` files
        and ``Iz0.txt`` for bunch data.
    n_modes : int, optional
        Number of odd modes.  Auto-detected if ``None``.
    show_bunch : bool
        Overlay bunch profile from ``Iz0.txt``.
    title : str
        Plot title.
    figsize : tuple
        Figure size.
    ax : plt.Axes, optional
        Existing axes.

    Returns
    -------
    tuple[plt.Figure, plt.Axes]
    """
    # -- v0.1.1: 2D modal decomposition (replaces MATLAB 3D mesh) --
    import glob

    _, plt = _get_matplotlib()
    data_dir = Path(data_dir)

    # ---- auto-detect modes ----
    if n_modes is None:
        files = sorted(glob.glob(str(data_dir / "wakeL_*.txt")))
        n_modes = len(files) if files else 1

    # ---- load each mode (skip 2 non-comment header rows) ----
    s: np.ndarray | None = None
    wakes: list[tuple[int, np.ndarray]] = []
    offset_all: int = 0
    W: float = 0.0  # total width [m] (= Width parameter, recta only)

    for i in range(1, n_modes + 1):
        m = 2 * i - 1
        fpath = data_dir / f"wakeL_{m:02d}.txt"
        if not fpath.exists():
            continue

        # lines[0]="hr offset", lines[1]="W sigma", lines[2:]=wake data
        with open(fpath) as fh:
            lines = [ln.strip() for ln in fh
                     if not ln.startswith("%") and ln.strip()]
        offset_all = int(float(lines[0].split()[1]))
        if W == 0.0:
            W = float(lines[1].split()[0])

        data = np.array(
            [list(map(float, ln.split())) for ln in lines[2:]]
        )
        if s is None:
            s = data[:, 0]           # s [m]
        w = data[:, 1] * 1e-3        # m·V/nC → V/pC

        wakes.append((m, w))

    if s is None or not wakes:
        raise ValueError(f"No valid wake files in {data_dir}")

    # ---- plot ----
    if ax is None:
        fig, ax = plt.subplots(figsize=figsize)
    else:
        fig = ax.figure

    n = len(wakes)
    colors = plt.cm.viridis(np.linspace(0.05, 0.95, max(n, 1)))

    for idx, (m, w) in enumerate(wakes):
        ax.plot(s * 1e3, w, color=colors[idx], linewidth=1.2,
                label=f"m={m}")

    # ---- bunch overlay from Iz0.txt ----
    if show_bunch:
        from pyecho.parser import load_bunch_profile
        s_bunch, I_bunch = load_bunch_profile(data_dir, offset_all, s)
        if I_bunch is not None and len(I_bunch) > 0:
            w_max: float = max(np.max(np.abs(w)) for _, w in wakes)
            b_max: float = np.max(np.abs(I_bunch))
            if b_max > 0 and w_max > 0:
                I_scaled = I_bunch * (w_max / b_max)
            else:
                I_scaled = I_bunch
            ax.plot(s * 1e3, I_scaled, "k--", linewidth=1.2,
                    alpha=0.7, label="Bunch (Iz0)")

    ax.axhline(y=0, color="gray", linestyle="--", linewidth=0.8)
    ax.set_xlabel("s [mm]")
    ax.set_ylabel("Raw modal wake [V/pC]")
    ax.set_title(title or f"Modal decomposition ({n} odd modes)")
    ax.legend(loc="best", ncol=2, fontsize=8)
    ax.grid(True, alpha=0.3)

    # ---- annotate k_x ↔ m relationship ----
    if W > 0:
        kx_note = (
            r"$k_x = \frac{\pi m}{W}$"
            + f"  (W = {W*1e3:.1f} mm)"
        )
        ax.text(
            0.5, -0.12, kx_note,
            transform=ax.transAxes, ha="center", va="top",
            fontsize=8, color="gray",
        )

    fig.tight_layout()
    return fig, ax


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_s_w(
    result_or_s: Any,
    W: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Extract (s, W) from various result types.

    Parameters
    ----------
    result_or_s : Any
        Can be a ``SimulationResult``, ``WakeResult``, ``ModeResult``,
        or raw ``np.ndarray``.
    W : np.ndarray, optional
        Required if *result_or_s* is an array.

    Returns
    -------
    tuple[np.ndarray, np.ndarray]
        ``(s, W)`` arrays.
    """
    if isinstance(result_or_s, np.ndarray):
        if W is None:
            raise ValueError("W must be provided when passing raw arrays")
        return result_or_s, W

    # Try datamodel types
    obj = result_or_s

    # WakeResult
    if hasattr(obj, "s") and hasattr(obj, "W"):
        return obj.s, obj.W

    # FlatWakeResult — use longitudinal component
    if hasattr(obj, "s") and hasattr(obj, "Wlong"):
        return obj.s, obj.Wlong

    # ModeResult
    if hasattr(obj, "s_raw") and hasattr(obj, "W_raw"):
        return obj.s_raw, obj.W_raw

    # SimulationResult — get first mode
    if hasattr(obj, "modes"):
        modes = obj.modes
        if modes:
            first = next(iter(modes.values()))
            if first.wake_processed:
                return first.wake_processed.s, first.wake_processed.W
            return first.s_raw, first.W_raw

    raise TypeError(
        f"Cannot extract s, W from type {type(obj).__name__}. "
        "Pass raw arrays or a WakeResult/ModeResult/SimulationResult."
    )


def _extract_loss(result_or_s: Any) -> float | None:
    """Try to extract loss factor from a result object.

    Parameters
    ----------
    result_or_s : Any
        Any result type that might have loss information.

    Returns
    -------
    float or None
    """
    obj = result_or_s
    if isinstance(obj, np.ndarray):
        return None
    if hasattr(obj, "loss_factor"):
        return cast(float, obj.loss_factor)
    if hasattr(obj, "loss_long"):
        return cast(float, obj.loss_long)
    if hasattr(obj, "wake_processed") and obj.wake_processed:
        return cast(float, obj.wake_processed.loss_factor)
    if hasattr(obj, "modes"):
        modes = obj.modes
        if modes:
            first = next(iter(modes.values()))
            if first.wake_processed:
                return cast(float, first.wake_processed.loss_factor)
    return None


def _extract_units(result_or_s: Any) -> str | None:
    """Try to extract physical units from a result object."""
    obj = result_or_s
    if isinstance(obj, np.ndarray):
        return None
    if hasattr(obj, "units"):
        return cast(str, obj.units)
    if hasattr(obj, "wake_processed") and obj.wake_processed:
        return getattr(obj.wake_processed, "units", None)
    return None


def _units_scale(units: str) -> float:
    """Return scaling factor to convert cm → *units*.

    Parameters
    ----------
    units : str
        One of ``"cm"``, ``"mm"``, ``"m"``.

    Returns
    -------
    float
    """
    _map = {"cm": 1.0, "mm": 10.0, "m": 0.01}
    return _map.get(units.lower(), 1.0)
