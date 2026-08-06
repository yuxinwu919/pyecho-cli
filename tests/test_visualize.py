"""Tests for the visualization functions in ``pyecho/visualize.py``.

Covers:
- ``plot_wake_round`` return values, bunch overlays, loss annotations
- ``plot_recta_wake`` three-subplot layout
- ``plot_geometry`` with synthetic geometry files
- ``plot_comparison`` with synthetic runs
- ``plot_wake_modes`` with synthetic wake files
- figure/axes type checks, save-to-file, and tight_layout
"""

from __future__ import annotations

from dataclasses import dataclass

import matplotlib

matplotlib.use("Agg")  # headless backend for CI

import numpy as np
import pytest

import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.axes import Axes

from pyecho import visualize
from pyecho.datamodel import ModeResult, RectaWakeResult, WakeResult
from pyecho.errors import GeometryError


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _close_figures():
    """Close any figures opened by a test, regardless of pass/fail."""
    yield
    plt.close("all")


def _make_s_w(n: int = 50, *, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    s = np.linspace(0.0, 0.01, n)
    w = rng.normal(size=n)
    return s, w


def _make_wake_result(n: int = 50) -> WakeResult:
    s, w = _make_s_w(n)
    return WakeResult(
        s=s,
        W=w,
        bunch=np.ones_like(s),
        loss_factor=1.234,
        rms_spread=0.1,
        peak=float(np.max(np.abs(w))),
        label="m=0",
        units="V/pC",
    )


def _make_recta_result(n: int = 50) -> RectaWakeResult:
    s, w = _make_s_w(n)
    return RectaWakeResult(
        s=s,
        Wlong=w,
        Wquad=0.5 * w,
        Wdipole=0.25 * w,
        loss_long=1.0,
        kick_quad=2.0,
        kick_dipole=3.0,
    )


def _make_mode_result(n: int = 50) -> ModeResult:
    s, w = _make_s_w(n)
    return ModeResult(
        mode_number=1,
        s_raw=s,
        W_raw=w,
        hr=1e-3,
        offset=0,
        D=0.05,
        sigma=0.001,
        wake_processed=WakeResult(
            s=s,
            W=w,
            bunch=np.ones_like(s),
            loss_factor=5.0,
            rms_spread=0.0,
            peak=1.0,
            units="V/pC",
        ),
    )


@pytest.fixture
def synthetic_geometry(tmp_path):
    """Create a two-segment synthetic geometry file."""
    geo = tmp_path / "geo.txt"
    geo.write_text(
        "\n".join(
            [
                "1",
                "2 1.0 1.0 0.0",
                "0.0 0.0 5.0 0.0 0 0 0 0 0 1.0",
                "0.0 1.0 5.0 1.0 0 0 0 0 0 1.0",
            ]
        )
        + "\n"
    )
    return geo


def _write_wake_file(path, *, offset: int = 0, W: float = 0.05):
    # Header rows parsed by plot_wake_modes:
    #   lines[0] -> offset = int(float(lines[0].split()[1]))
    #   lines[1] -> W = float(lines[1].split()[0])
    path.write_text(
        "\n".join(
            [
                f"hr 0 {offset}",
                f"{W:.6f} 0.001",
                "0.000 1.0",
                "0.001 0.5",
                "0.002 0.25",
            ]
        )
        + "\n"
    )


def _labeled_lines(ax) -> list:
    """Lines on *ax* excluding auto-generated (_childN) reference lines."""
    return [ln for ln in ax.lines
            if ln.get_label() and not ln.get_label().startswith("_")]


@pytest.fixture
def synthetic_wake_dir(tmp_path):
    """Directory with two wakeL files plus an Iz0 bunch profile."""
    _write_wake_file(tmp_path / "wakeL_01.txt", offset=0)
    _write_wake_file(tmp_path / "wakeL_03.txt", offset=0)
    # Iz0.txt: column 0 = s, columns 1/2 arbitrary; col = offset+2 = 2 used
    (tmp_path / "Iz0.txt").write_text(
        "0.000 0.0 1e-9\n0.001 0.0 1e-9\n0.002 0.0 1e-9\n"
    )
    return tmp_path


# ---------------------------------------------------------------------------
# plot_wake_round
# ---------------------------------------------------------------------------

def test_plot_wake_round_returns_figure_and_axes():
    s, w = _make_s_w()
    fig, ax = visualize.plot_wake_round(s, w)
    assert isinstance(fig, Figure)
    assert isinstance(ax, Axes)
    assert ax is fig.axes[0]


def test_plot_wake_round_with_arrays_and_W():
    s, w = _make_s_w()
    fig, ax = visualize.plot_wake_round(s, W=w)
    # one wake line + one axhline reference line
    assert len(ax.lines) == 2
    assert ax.get_xlabel() == "s [mm]"
    assert ax.get_ylabel() == "Wake potential [V/pC]"


def test_plot_wake_round_with_wake_result_loss_annotation():
    result = _make_wake_result()
    fig, ax = visualize.plot_wake_round(result)
    texts = [t.get_text() for t in ax.texts]
    assert any("1.2340" in t for t in texts)
    # Bunch overlay auto-extracted from WakeResult.bunch
    assert len(_labeled_lines(ax)) == 2  # wake + bunch


def test_plot_wake_round_with_mode_result():
    result = _make_mode_result()
    fig, ax = visualize.plot_wake_round(result)
    assert isinstance(fig, Figure)
    assert len(ax.lines) >= 1
    # units auto-detected from wake_processed.units -> still V/pC
    assert "V/pC" in ax.get_ylabel()


def test_plot_wake_round_bunch_overlay_scaled():
    s, w = _make_s_w()
    bunch = np.linspace(0.0, 2.0, len(s))
    fig, ax = visualize.plot_wake_round(s, w, bunch=bunch)
    assert len(_labeled_lines(ax)) == 2
    labels = [ln.get_label() for ln in _labeled_lines(ax)]
    assert "Bunch shape" in labels
    assert "Wake potential" in labels


def test_plot_wake_round_existing_axes():
    s, w = _make_s_w()
    fig, existing = plt.subplots()
    fig2, ax = visualize.plot_wake_round(s, w, ax=existing)
    assert fig2 is fig
    assert ax is existing
    assert len(fig.axes) == 1


def test_plot_wake_round_figsize():
    s, w = _make_s_w()
    fig, ax = visualize.plot_wake_round(s, w, figsize=(7, 4))
    w_in, h_in = fig.get_size_inches()
    assert w_in == pytest.approx(7.0)
    assert h_in == pytest.approx(4.0)


def test_plot_wake_round_raises_without_W():
    s = np.linspace(0, 1, 10)
    with pytest.raises(ValueError, match="W must be provided"):
        visualize.plot_wake_round(s)


def test_plot_wake_round_tight_layout_grid_enabled():
    s, w = _make_s_w()
    fig, ax = visualize.plot_wake_round(s, w, title="custom")
    assert ax.get_title() == "custom"
    assert ax.xaxis.get_gridlines()  # grid enabled via ax.grid(True)
    # tight_layout() runs without raising; figure must have at least one axe
    assert len(fig.axes) == 1


# ---------------------------------------------------------------------------
# plot_recta_wake
# ---------------------------------------------------------------------------

def test_plot_recta_wake_returns_figure_and_three_axes():
    result = _make_recta_result()
    fig, axes = visualize.plot_recta_wake(result)
    assert isinstance(fig, Figure)
    assert len(axes) == 3
    assert all(isinstance(a, Axes) for a in axes)
    assert axes[0].get_ylabel().startswith("Longitudinal")
    assert axes[1].get_ylabel().startswith("Quadrupole")
    assert axes[2].get_ylabel().startswith("Dipole")
    assert axes[2].get_xlabel() == "s [mm]"


def test_plot_recta_wake_with_bunch_overlay():
    result = _make_recta_result()
    fig, axes = visualize.plot_recta_wake(
        result, bunch=np.ones_like(result.s)
    )
    for a in axes:
        # wake line + bunch line + axhline reference line
        assert len(a.lines) == 3
    # legend only added on the top subplot
    assert any(a.get_legend() is not None for a in axes)


def test_plot_recta_wake_title_and_figsize():
    result = _make_recta_result()
    fig, axes = visualize.plot_recta_wake(result, title="Recta test", figsize=(9, 7))
    assert fig._suptitle.get_text() == "Recta test"
    w_in, h_in = fig.get_size_inches()
    assert w_in == pytest.approx(9.0)
    assert h_in == pytest.approx(7.0)


# ---------------------------------------------------------------------------
# plot_geometry
# ---------------------------------------------------------------------------

def test_plot_geometry_returns_figure_and_axes(synthetic_geometry):
    fig, ax = visualize.plot_geometry(synthetic_geometry)
    assert isinstance(fig, Figure)
    assert isinstance(ax, Axes)
    assert synthetic_geometry.name in ax.get_title()
    assert ax.get_xlabel() == "z [cm]"
    # Two segments -> two plotted lines, plus the axis-of-symmetry axhline
    assert len(ax.lines) == 3


def test_plot_geometry_units_scaling_mm(synthetic_geometry):
    fig, ax = visualize.plot_geometry(synthetic_geometry, units="mm")
    assert ax.get_xlabel() == "z [mm]"
    assert ax.get_ylabel() == "r [mm]"


def test_plot_geometry_existing_axes(synthetic_geometry):
    fig, existing = plt.subplots()
    fig2, ax = visualize.plot_geometry(synthetic_geometry, ax=existing)
    assert fig2 is fig
    assert ax is existing


def test_plot_geometry_missing_file_raises(tmp_path):
    with pytest.raises(GeometryError, match="Cannot load geometry"):
        visualize.plot_geometry(tmp_path / "does_not_exist.txt")


def test_plot_geometry_no_materials_no_shading(synthetic_geometry):
    fig, ax = visualize.plot_geometry(
        synthetic_geometry, show_materials=False
    )
    assert len(ax.lines) == 3  # two segment lines + axhline
    # No fill_between collectors when shading disabled
    assert not ax.collections


# ---------------------------------------------------------------------------
# plot_comparison
# ---------------------------------------------------------------------------

def _comparison_runs(n: int = 3, seed: int = 0):
    return [
        (f"Run {i}",) + _make_s_w(seed=seed + i) for i in range(n)
    ]


def test_plot_comparison_returns_figure_and_axes():
    results = _comparison_runs()
    fig, ax = visualize.plot_comparison(results)
    assert isinstance(fig, Figure)
    assert isinstance(ax, Axes)
    # three runs + axhline reference line
    assert len(ax.lines) == len(results) + 1
    assert "Wake Potential Comparison" in ax.get_title()


def test_plot_comparison_label_override():
    results = _comparison_runs()
    fig, ax = visualize.plot_comparison(results, labels=["A", "B", "C"])
    labels = [ln.get_label() for ln in _labeled_lines(ax)]
    assert labels == ["A", "B", "C"]


def test_plot_comparison_difference_mode():
    results = _comparison_runs()
    fig, ax = visualize.plot_comparison(results, difference=True)
    labels = [ln.get_label() for ln in _labeled_lines(ax)]
    assert labels[0].endswith("(reference)")
    assert all(l.startswith("Δ") for l in labels[1:])
    assert ax.get_ylabel().startswith("Δ Wake")


def test_plot_comparison_objects_with_attributes():
    @dataclass
    class FakeResult:
        label: str
        s: np.ndarray
        W: np.ndarray

    results = [
        FakeResult(f"obj {i}", *_make_s_w(seed=i)) for i in range(2)
    ]
    fig, ax = visualize.plot_comparison(results)
    assert len(_labeled_lines(ax)) == 2
    labels = [ln.get_label() for ln in _labeled_lines(ax)]
    assert labels == ["obj 0", "obj 1"]


@pytest.mark.filterwarnings("ignore:No artists with labels found to put in legend")
def test_plot_comparison_empty_results():
    fig, ax = visualize.plot_comparison([])
    assert isinstance(fig, Figure)
    assert isinstance(ax, Axes)
    # No lines plotted, but plot still works and has a reference line
    assert len(ax.lines) == 1  # the y=0 axhline


# ---------------------------------------------------------------------------
# plot_wake_modes
# ---------------------------------------------------------------------------

def test_plot_wake_modes_returns_figure_and_axes(synthetic_wake_dir):
    fig, ax = visualize.plot_wake_modes(synthetic_wake_dir)
    assert isinstance(fig, Figure)
    assert isinstance(ax, Axes)
    labels = [ln.get_label() for ln in ax.lines]
    # Two mode lines (m=1, m=3) plus the bunch overlay
    assert "m=1" in labels and "m=3" in labels
    assert "Bunch (Iz0)" in labels
    assert "modal decomposition" in ax.get_title().lower()


def test_plot_wake_modes_no_iz0_file(tmp_path):
    _write_wake_file(tmp_path / "wakeL_01.txt")
    _write_wake_file(tmp_path / "wakeL_03.txt")
    fig, ax = visualize.plot_wake_modes(tmp_path)
    labels = [ln.get_label() for ln in ax.lines]
    assert "m=1" in labels and "m=3" in labels
    assert "Bunch (Iz0)" not in labels  # gracefully skipped


def test_plot_wake_modes_n_modes_override(synthetic_wake_dir):
    fig, ax = visualize.plot_wake_modes(synthetic_wake_dir, n_modes=1)
    labels = [ln.get_label() for ln in ax.lines]
    assert "m=1" in labels
    assert "m=3" not in labels


def test_plot_wake_modes_raises_without_wake_files(tmp_path):
    with pytest.raises(ValueError, match="No valid wake files"):
        visualize.plot_wake_modes(tmp_path)


# ---------------------------------------------------------------------------
# save-to-file / types / tight_layout
# ---------------------------------------------------------------------------

def test_save_figure_to_file(tmp_path):
    s, w = _make_s_w()
    fig, ax = visualize.plot_wake_round(s, w)
    out = tmp_path / "wake.png"
    fig.savefig(out)
    assert out.exists()
    assert out.stat().st_size > 0


def test_save_geometry_figure_to_file(synthetic_geometry, tmp_path):
    fig, ax = visualize.plot_geometry(synthetic_geometry)
    out = tmp_path / "geo.png"
    fig.savefig(out, dpi=72)
    assert out.exists()
    assert out.stat().st_size > 0
    # Reopen the PNG to confirm it is a valid image
    import matplotlib.image as mpimg

    img = mpimg.imread(out)
    assert img.shape[0] > 0 and img.shape[1] > 0


def test_plot_wake_round_supports_tight_layout_no_warning():
    """tight_layout() is exercised on every plot; nothing should warn."""
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        s, w = _make_s_w()
        fig, ax = visualize.plot_wake_round(s, w)
        fig.canvas.draw()
