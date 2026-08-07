"""Interactive visualization backend using pyqtgraph.

Provides native Qt-window interactive plots for ECHO2D data.

Usage::

    from pyecho.visualize_interactive import plot_wake_interactive

Requires: ``pyqtgraph`` and ``PySide2`` (or ``PyQt5``).
Install with: ``pip install pyqtgraph PySide2``
"""

from __future__ import annotations

import numpy as np

try:
    import pyqtgraph as pg
    HAS_PYQTGRAPH = True
except ImportError:
    HAS_PYQTGRAPH = False


def _check() -> None:
    if not HAS_PYQTGRAPH:
        raise ImportError(
            "pyqtgraph is required for interactive visualization.\n"
            "Install with:  pip install pyqtgraph PySide2"
        )


def _to_mm(arr: np.ndarray) -> np.ndarray:
    return arr * 1000.0 if np.max(np.abs(arr)) < 1.0 else arr


# ---------------------------------------------------------------------------
# Wake potential
# ---------------------------------------------------------------------------

def plot_wake_interactive(
    s: np.ndarray,
    W: np.ndarray,
    *,
    title: str = "Wake Potential",
    xlabel: str = "s [mm]",
    ylabel: str = "W [V/pC]",
    bunch_s: np.ndarray | None = None,
    bunch_profile: np.ndarray | None = None,
    loss: float | None = None,
) -> None:
    """Interactive wake potential plot in a native Qt window."""
    _check()

    win = pg.GraphicsLayoutWidget(title=title)
    win.resize(1000, 600)

    p = win.addPlot(title=title)
    p.setLabel("bottom", xlabel)
    p.setLabel("left", ylabel)
    p.addLegend()
    p.showGrid(x=True, y=True, alpha=0.3)

    s_mm = _to_mm(s)
    p.plot(s_mm, W, pen=pg.mkPen("b", width=2), name="W(s)")
    p.addLine(y=0, pen=pg.mkPen("gray", style=pg.QtCore.Qt.DashLine))

    if bunch_s is not None and bunch_profile is not None:
        bs_mm = _to_mm(bunch_s)
        scale = np.max(np.abs(W)) / max(float(np.max(bunch_profile)), 1e-20) * 0.8
        p.plot(
            bs_mm,
            bunch_profile * scale,
            pen=pg.mkPen("r", width=1, style=pg.QtCore.Qt.DotLine),
            name="Bunch (scaled)",
        )

    if loss is not None:
        label = pg.LabelItem(f"Loss = {loss:.4f} V/pC", color="w", size="12pt")
        label.setParentItem(p.graphicsItem())
        label.anchor(itemPos=(1, 0), parentPos=(1, 0), offset=(-10, 10))

    pg.exec()


# ---------------------------------------------------------------------------
# Impedance spectrum
# ---------------------------------------------------------------------------

def plot_impedance_interactive(
    f: np.ndarray,
    Z: np.ndarray,
    *,
    title: str = "Impedance Spectrum",
) -> None:
    """Interactive impedance — |Z(f)| + Re/Im dual-panel."""
    _check()

    win = pg.GraphicsLayoutWidget(title=title)
    win.resize(1000, 700)

    p1 = win.addPlot(row=0, col=0, title="|Z(f)|")
    p1.setLabel("bottom", "f", units="Hz")
    p1.setLabel("left", "|Z|", units="Ω")
    p1.showGrid(x=True, y=True, alpha=0.3)
    p1.setLogMode(x=True, y=True)
    p1.plot(f, np.abs(Z), pen=pg.mkPen("#7c3aed", width=2))

    win.nextRow()
    p2 = win.addPlot(row=1, col=0, title="Re(Z) and Im(Z)")
    p2.setLabel("bottom", "f", units="Hz")
    p2.setLabel("left", "Re(Z)", units="Ω")
    p2.addLegend()
    p2.showGrid(x=True, y=True, alpha=0.3)
    p2.plot(f, np.real(Z), pen=pg.mkPen("g", width=2), name="Re(Z)")

    p2r = pg.ViewBox()
    p2.showAxis("right")
    p2.scene().addItem(p2r)
    p2.getAxis("right").linkToView(p2r)
    p2r.setXLink(p2)
    p2r.addItem(pg.PlotCurveItem(
        f, np.imag(Z),
        pen=pg.mkPen("r", width=2, style=pg.QtCore.Qt.DashLine),
    ))

    pg.exec()


# ---------------------------------------------------------------------------
# Geometry structure
# ---------------------------------------------------------------------------

def plot_geometry_interactive(
    coords: list[tuple[np.ndarray, np.ndarray, str]],
    *,
    title: str = "Geometry",
) -> None:
    """Interactive geometry plot. *coords*: list of (z, r, label)."""
    _check()

    win = pg.GraphicsLayoutWidget(title=title)
    win.resize(900, 500)

    p = win.addPlot(title=title)
    p.setLabel("bottom", "z", units="mm")
    p.setLabel("left", "r", units="mm")
    p.showGrid(x=True, y=True, alpha=0.3)

    colors = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6"]
    for i, (z, r, label) in enumerate(coords):
        color = colors[i % len(colors)]
        p.plot(_to_mm(z), _to_mm(r), pen=pg.mkPen(color, width=2), name=label)

    p.addLine(y=0, pen=pg.mkPen("gray", style=pg.QtCore.Qt.DashLine))
    pg.exec()


# ---------------------------------------------------------------------------
# Multi-run comparison
# ---------------------------------------------------------------------------

def plot_comparison_interactive(
    runs: list[dict],
    *,
    title: str = "Wake Comparison",
) -> None:
    """Interactive multi-run comparison. *runs*: [{"s": ..., "W": ..., "label": ...}]."""
    _check()

    win = pg.GraphicsLayoutWidget(title=title)
    win.resize(1000, 600)

    p = win.addPlot(title=title)
    p.setLabel("bottom", "s", units="mm")
    p.setLabel("left", "W", units="V/pC")
    p.addLegend()
    p.showGrid(x=True, y=True, alpha=0.3)

    colors = ["#3b82f6", "#ef4444", "#10b981", "#f59e0b", "#8b5cf6", "#ec4899"]
    for i, run in enumerate(runs):
        s_mm = _to_mm(run["s"])
        color = colors[i % len(colors)]
        p.plot(s_mm, run["W"], pen=pg.mkPen(color, width=2),
               name=run.get("label", f"Run {i+1}"))

    p.addLine(y=0, pen=pg.mkPen("gray", style=pg.QtCore.Qt.DashLine))
    pg.exec()
