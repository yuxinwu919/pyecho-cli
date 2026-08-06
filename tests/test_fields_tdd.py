"""TDD tests for :mod:`pyecho.postprocess.fields`.

Covers point extraction (:func:`extract_field_at_point`), the high-level
monitor wrapper (:func:`process_field_monitor`), modal field synthesis
(:func:`synthesize_total_field`), and point-monitor extraction / saving
(:func:`extract_point_monitor`, :func:`save_point_monitor`).

All monitors are built synthetically with :class:`MonitorData`.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from pyecho.datamodel import MonitorData
from pyecho.errors import PostProcessError
from pyecho.postprocess.fields import (
    extract_field_at_point,
    extract_point_monitor,
    process_field_monitor,
    save_point_monitor,
    synthesize_total_field,
)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def make_monitor(
    F,
    *,
    T=None,
    Z=None,
    R=None,
    component: str = "Ez",
    time_type: str = "s",
    D: float = 0.05,
) -> MonitorData:
    """Build a synthetic MonitorData with sensible default axes."""
    F = np.asarray(F, dtype=float)
    T = T if T is not None else np.arange(F.shape[0], dtype=float)
    Z = Z if Z is not None else np.zeros(1)
    R = R if R is not None else np.zeros(1)
    return MonitorData(
        monitor_id=1,
        field_component=component,
        time_type=time_type,
        T=np.asarray(T, float),
        Z=np.asarray(Z, float),
        R=np.asarray(R, float),
        F=F,
        D=D,
    )


def _write_monitor(path: Path, data, width: float | None) -> None:
    """Write a MATLAB-style monitor file with a ``%`` header."""
    with open(path, "w", encoding="utf-8") as fh:
        if width is not None:
            fh.write(f"% Field=Ez time=z width={width:.6e}\n")
        else:
            fh.write("% Field=Ez time=z\n")
        np.savetxt(fh, np.asarray(data, dtype=float), fmt="%.8e")


# ---------------------------------------------------------------------------
# extract_field_at_point — 1-D data
# ---------------------------------------------------------------------------


def test_extract_1d_with_t_interpolates_scalar() -> None:
    """1-D monitor with t requested returns a linearly-interpolated scalar."""
    F = np.array([0.0, 1.0, 2.0, 3.0])
    mon = make_monitor(F, T=np.array([0.0, 1.0, 2.0, 3.0]))
    out = extract_field_at_point(mon, t=1.5)
    assert isinstance(out, float)
    assert out == pytest.approx(1.5)


def test_extract_1d_without_t_returns_raw() -> None:
    """1-D monitor with no coordinates returns the raw trace unchanged."""
    F = np.array([0.0, 1.0, 2.0, 3.0])
    mon = make_monitor(F, T=np.array([0.0, 1.0, 2.0, 3.0]))
    out = extract_field_at_point(mon)
    np.testing.assert_array_equal(out, F)


def test_extract_1d_out_of_bounds_returns_zero() -> None:
    """1-D monitor with t outside the time grid returns 0.0."""
    F = np.array([0.0, 1.0, 2.0, 3.0])
    mon = make_monitor(F, T=np.array([0.0, 1.0, 2.0, 3.0]))
    assert extract_field_at_point(mon, t=10.0) == pytest.approx(0.0)


def test_extract_1d_exact_grid_match() -> None:
    """1-D monitor at an exact grid time returns the grid value."""
    F = np.array([0.0, 1.0, 2.0, 3.0])
    mon = make_monitor(F, T=np.array([0.0, 1.0, 2.0, 3.0]))
    assert extract_field_at_point(mon, t=2.0) == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# extract_field_at_point — 2-D data (space axis = R)
# ---------------------------------------------------------------------------


def test_extract_2d_r_t_and_r_scalar() -> None:
    """2-D R-axis monitor with t and r returns a scalar (bilinear interp)."""
    F = np.array(
        [[0.0, 1.0, 2.0], [3.0, 4.0, 5.0], [6.0, 7.0, 8.0], [9.0, 10.0, 11.0]]
    )
    mon = make_monitor(F, T=np.array([0.0, 1.0, 2.0, 3.0]),
                       R=np.array([0.0, 0.5, 1.0]))
    out = extract_field_at_point(mon, t=1.5, r=0.25)
    assert isinstance(out, float)
    assert out == pytest.approx(5.0)


def test_extract_2d_r_r_only_time_trace() -> None:
    """2-D R-axis monitor with r only returns a 1-D time trace."""
    F = np.array(
        [[0.0, 1.0, 2.0], [3.0, 4.0, 5.0], [6.0, 7.0, 8.0], [9.0, 10.0, 11.0]]
    )
    mon = make_monitor(F, T=np.array([0.0, 1.0, 2.0, 3.0]),
                       R=np.array([0.0, 0.5, 1.0]))
    out = extract_field_at_point(mon, r=0.25)
    assert isinstance(out, np.ndarray)
    assert out.shape == (4,)
    np.testing.assert_allclose(out, [0.5, 3.5, 6.5, 9.5])


def test_extract_2d_r_t_only_uses_median() -> None:
    """2-D R-axis monitor with t only samples at the median R."""
    F = np.array(
        [[0.0, 1.0, 2.0], [3.0, 4.0, 5.0], [6.0, 7.0, 8.0], [9.0, 10.0, 11.0]]
    )
    mon = make_monitor(F, T=np.array([0.0, 1.0, 2.0, 3.0]),
                       R=np.array([0.0, 0.5, 1.0]))
    # median(R) == 0.5; interp(1.5, 0.5) == 5.5
    assert extract_field_at_point(mon, t=1.5) == pytest.approx(5.5)


def test_extract_2d_r_no_coords_returns_slice() -> None:
    """2-D R-axis monitor with no coordinates returns the raw slice."""
    F = np.array(
        [[0.0, 1.0, 2.0], [3.0, 4.0, 5.0], [6.0, 7.0, 8.0], [9.0, 10.0, 11.0]]
    )
    mon = make_monitor(F, T=np.array([0.0, 1.0, 2.0, 3.0]),
                       R=np.array([0.0, 0.5, 1.0]))
    np.testing.assert_array_equal(extract_field_at_point(mon), F)


def test_extract_2d_out_of_bounds_t_zero() -> None:
    """2-D monitor with t outside the grid returns 0.0."""
    F = np.array(
        [[0.0, 1.0, 2.0], [3.0, 4.0, 5.0], [6.0, 7.0, 8.0], [9.0, 10.0, 11.0]]
    )
    mon = make_monitor(F, T=np.array([0.0, 1.0, 2.0, 3.0]),
                       R=np.array([0.0, 0.5, 1.0]))
    assert extract_field_at_point(mon, t=100.0, r=0.5) == pytest.approx(0.0)


def test_extract_2d_exact_grid_match() -> None:
    """2-D monitor at an exact (t, r) grid point returns the grid value."""
    F = np.array(
        [[0.0, 1.0, 2.0], [3.0, 4.0, 5.0], [6.0, 7.0, 8.0], [9.0, 10.0, 11.0]]
    )
    mon = make_monitor(F, T=np.array([0.0, 1.0, 2.0, 3.0]),
                       R=np.array([0.0, 0.5, 1.0]))
    assert extract_field_at_point(mon, t=1.0, r=0.5) == pytest.approx(4.0)


# ---------------------------------------------------------------------------
# extract_field_at_point — 2-D data (space axis = Z)
# ---------------------------------------------------------------------------


def test_extract_2d_z_t_and_z_scalar() -> None:
    """2-D Z-axis monitor with t and z returns a scalar."""
    F = np.array(
        [[0.0, 1.0, 2.0], [3.0, 4.0, 5.0], [6.0, 7.0, 8.0], [9.0, 10.0, 11.0]]
    )
    mon = make_monitor(F, T=np.array([0.0, 1.0, 2.0, 3.0]),
                       Z=np.array([0.0, 0.5, 1.0]))
    assert extract_field_at_point(mon, t=1.5, z=0.25) == pytest.approx(5.0)


def test_extract_2d_z_z_only_time_trace() -> None:
    """2-D Z-axis monitor with z only returns a 1-D time trace."""
    F = np.array(
        [[0.0, 1.0, 2.0], [3.0, 4.0, 5.0], [6.0, 7.0, 8.0], [9.0, 10.0, 11.0]]
    )
    mon = make_monitor(F, T=np.array([0.0, 1.0, 2.0, 3.0]),
                       Z=np.array([0.0, 0.5, 1.0]))
    out = extract_field_at_point(mon, z=0.25)
    assert out.shape == (4,)
    np.testing.assert_allclose(out, [0.5, 3.5, 6.5, 9.5])


# ---------------------------------------------------------------------------
# extract_field_at_point — 3-D data
# ---------------------------------------------------------------------------


def test_extract_3d_full_point_scalar() -> None:
    """3-D monitor with (t, z, r) returns a scalar value."""
    F = np.arange(18.0).reshape(3, 3, 2)
    mon = make_monitor(F, T=np.array([0.0, 1.0, 2.0]),
                       Z=np.array([0.0, 0.5, 1.0]),
                       R=np.array([0.0, 0.5]))
    out = extract_field_at_point(mon, t=1.0, z=0.5, r=0.0)
    assert isinstance(out, float)
    assert out == pytest.approx(8.0)


def test_extract_3d_fixed_z_r_trace_over_time() -> None:
    """3-D monitor with fixed (z, r) returns a 1-D trace over time."""
    F = np.arange(18.0).reshape(3, 3, 2)
    mon = make_monitor(F, T=np.array([0.0, 1.0, 2.0]),
                       Z=np.array([0.0, 0.5, 1.0]),
                       R=np.array([0.0, 0.5]))
    out = extract_field_at_point(mon, z=0.5, r=0.0)
    assert out.shape == (3,)
    np.testing.assert_allclose(out, [2.0, 8.0, 14.0])


def test_extract_3d_z_only_median_r_slice() -> None:
    """3-D monitor with z only returns the (t, z) slice at median r."""
    F = np.arange(18.0).reshape(3, 3, 2)
    mon = make_monitor(F, T=np.array([0.0, 1.0, 2.0]),
                       Z=np.array([0.0, 0.5, 1.0]),
                       R=np.array([0.0, 0.5]))
    out = extract_field_at_point(mon, z=0.5)
    assert out.shape == (3, 3)
    np.testing.assert_array_equal(out, F[:, :, 0])


def test_extract_3d_out_of_bounds_zero() -> None:
    """3-D monitor with t outside the grid returns 0.0."""
    F = np.arange(18.0).reshape(3, 3, 2)
    mon = make_monitor(F, T=np.array([0.0, 1.0, 2.0]),
                       Z=np.array([0.0, 0.5, 1.0]),
                       R=np.array([0.0, 0.5]))
    assert extract_field_at_point(mon, t=100.0, z=0.0, r=0.0) == pytest.approx(0.0)


def test_extract_3d_exact_grid_match() -> None:
    """3-D monitor at an exact (t, z, r) grid point returns the grid value."""
    F = np.arange(18.0).reshape(3, 3, 2)
    mon = make_monitor(F, T=np.array([0.0, 1.0, 2.0]),
                       Z=np.array([0.0, 0.5, 1.0]),
                       R=np.array([0.0, 0.5]))
    assert extract_field_at_point(mon, t=1.0, z=0.5, r=0.5) == pytest.approx(9.0)


# ---------------------------------------------------------------------------
# process_field_monitor
# ---------------------------------------------------------------------------


def test_process_field_monitor_s_type_full_coords() -> None:
    """s-type monitor with no fixed points exposes T/Z/R coords and raw field."""
    F = np.arange(18.0).reshape(3, 3, 2)
    mon = make_monitor(F, T=np.array([0.0, 1.0, 2.0]),
                       Z=np.array([0.0, 0.5, 1.0]),
                       R=np.array([0.0, 0.5]), time_type="s")
    out = process_field_monitor(mon)
    assert out["component"] == "Ez"
    assert out["point"] == {"t": None, "z": None, "r": None}
    assert len(out["coords"]) == 3
    np.testing.assert_array_equal(out["coords"][0], mon.T)
    np.testing.assert_array_equal(out["coords"][1], mon.Z)
    np.testing.assert_array_equal(out["coords"][2], mon.R)
    np.testing.assert_array_equal(out["field"], F)


def test_process_field_monitor_z_type_full_coords() -> None:
    """z-type monitor behaves identically to s-type for full extraction."""
    F = np.arange(18.0).reshape(3, 3, 2)
    mon = make_monitor(F, T=np.array([0.0, 1.0, 2.0]),
                       Z=np.array([0.0, 0.5, 1.0]),
                       R=np.array([0.0, 0.5]), time_type="z")
    out = process_field_monitor(mon)
    assert out["component"] == "Ez"
    assert out["point"] == {"t": None, "z": None, "r": None}
    assert len(out["coords"]) == 3
    np.testing.assert_array_equal(out["field"], F)


def test_process_field_monitor_fixed_point_scalar_field() -> None:
    """Fixed (t, r) returns a wrapped scalar and excludes fixed axes."""
    F = np.array(
        [[0.0, 1.0, 2.0], [3.0, 4.0, 5.0], [6.0, 7.0, 8.0], [9.0, 10.0, 11.0]]
    )
    mon = make_monitor(F, T=np.array([0.0, 1.0, 2.0, 3.0]),
                       Z=np.array([0.0, 1.0]), R=np.array([0.0, 0.5, 1.0]))
    out = process_field_monitor(mon, point_t=1.0, point_r=0.5)
    np.testing.assert_allclose(out["field"], [4.0])
    assert out["point"] == {"t": 1.0, "z": None, "r": 0.5}
    # Only the free (unfixed, len > 1) Z axis remains in coords.
    assert len(out["coords"]) == 1
    np.testing.assert_array_equal(out["coords"][0], mon.Z)


def test_process_field_monitor_all_singleton_axes() -> None:
    """Singleton axes are excluded from coords (all fixed by default)."""
    F = np.zeros((1, 1, 1))
    mon = make_monitor(F, T=np.array([0.0]), Z=np.array([0.0]),
                       R=np.array([0.0]))
    out = process_field_monitor(mon)
    assert out["coords"] == []
    assert out["point"] == {"t": None, "z": None, "r": None}


def test_process_field_monitor_singleton_t_excluded() -> None:
    """A singleton time axis is excluded while longer Z/R axes are kept."""
    F = np.zeros((1, 3, 2))
    mon = make_monitor(F, T=np.array([0.0]), Z=np.array([0.0, 0.5, 1.0]),
                       R=np.array([0.0, 0.5]))
    out = process_field_monitor(mon)
    assert len(out["coords"]) == 2
    np.testing.assert_array_equal(out["coords"][0], mon.Z)
    np.testing.assert_array_equal(out["coords"][1], mon.R)
    assert out["component"] == "Ez"


# ---------------------------------------------------------------------------
# synthesize_total_field
# ---------------------------------------------------------------------------


def test_synth_single_mode_weight_formula() -> None:
    """Single-mode synthesis reproduces the MATLAB weight formula."""
    D = 0.05
    x0 = 0.0
    x = 0.001
    data = np.array([[0.0, 1.0], [0.1, 2.0], [0.2, 3.0]])
    path = Path("/tmp")
    p = path / "monitor_single.txt"
    _write_monitor(p, data, width=D)

    result = synthesize_total_field([p], x0=x0, x=x, n_modes=1, D=D)

    k_m = np.pi / D  # m = 1
    weight = np.sin(k_m * (x0 + 0.5 * D)) * np.sin(k_m * (x + 0.5 * D))
    expected = data[:, 1:] * weight * (2.0 / D)
    np.testing.assert_allclose(result, expected)


def test_synth_leading_coordinate_column_excluded() -> None:
    """The leading coordinate column is excluded from the field data."""
    D = 0.05
    data = np.array([[0.0, 1.0, 2.0], [0.1, 3.0, 4.0], [0.2, 5.0, 6.0]])
    p = Path("/tmp") / "monitor_multi_col.txt"
    _write_monitor(p, data, width=D)

    result = synthesize_total_field([p], x0=0.0, x=0.0, n_modes=1, D=D)

    assert result.shape == (3, 2)
    k_m = np.pi / D
    weight = np.sin(k_m * 0.5 * D) * np.sin(k_m * 0.5 * D)
    np.testing.assert_allclose(result, data[:, 1:] * weight * (2.0 / D))


def test_synth_multimode_accumulation() -> None:
    """Multiple odd modes accumulate as a weighted sum."""
    D = 0.05
    x0 = 0.0
    x = 0.001
    data1 = np.array([[0.0, 1.0], [0.1, 2.0], [0.2, 3.0]])
    data3 = np.array([[0.0, 10.0], [0.1, 20.0], [0.2, 30.0]])
    p1 = Path("/tmp") / "monitor_m1.txt"
    p3 = Path("/tmp") / "monitor_m3.txt"
    _write_monitor(p1, data1, width=D)
    _write_monitor(p3, data3, width=D)

    result = synthesize_total_field([p1, p3], x0=x0, x=x, n_modes=2, D=D)

    F1 = data1[:, 1:]
    F3 = data3[:, 1:]
    w1 = np.sin(np.pi / D * (x0 + 0.5 * D)) * np.sin(np.pi / D * (x + 0.5 * D))
    w3 = np.sin(3.0 * np.pi / D * (x0 + 0.5 * D)) * np.sin(
        3.0 * np.pi / D * (x + 0.5 * D)
    )
    expected = (F1 * w1 + F3 * w3) * (2.0 / D)
    np.testing.assert_allclose(result, expected)


def test_synth_auto_detect_width_from_header() -> None:
    """Width D is auto-detected from the first file header when not given."""
    D = 0.05
    data = np.array([[0.0, 1.0], [0.1, 2.0], [0.2, 3.0]])
    p = Path("/tmp") / "monitor_autodetect.txt"
    _write_monitor(p, data, width=D)

    result = synthesize_total_field([p], x0=0.0, x=0.0, n_modes=1, D=None)
    explicit = synthesize_total_field([p], x0=0.0, x=0.0, n_modes=1, D=D)

    np.testing.assert_allclose(result, explicit)


def test_synth_explicit_width_parameter() -> None:
    """Explicit D is used even when the header carries no width token."""
    data = np.array([[0.0, 1.0], [0.1, 2.0], [0.2, 3.0]])
    p = Path("/tmp") / "monitor_nowidth.txt"
    _write_monitor(p, data, width=None)  # header without width=

    D = 0.04
    result = synthesize_total_field([p], x0=0.0, x=0.0, n_modes=1, D=D)

    k_m = np.pi / D
    weight = np.sin(k_m * 0.5 * D) * np.sin(k_m * 0.5 * D)
    np.testing.assert_allclose(result, data[:, 1:] * weight * (2.0 / D))


def test_synth_empty_list_raises() -> None:
    """An empty monitor-file list raises PostProcessError."""
    with pytest.raises(PostProcessError):
        synthesize_total_field([], x0=0.0, x=0.0, n_modes=1, D=0.05)


def test_synth_no_valid_data_raises() -> None:
    """Missing files are skipped, raising PostProcessError if nothing loads."""
    missing = Path("/tmp") / "does_not_exist.txt"
    with pytest.raises(PostProcessError):
        synthesize_total_field([missing], x0=0.0, x=0.0, n_modes=1, D=0.05)


def test_synth_width_undetectable_raises() -> None:
    """If D is None and the header has no width token, PostProcessError."""
    p = Path("/tmp") / "monitor_undetectable.txt"
    _write_monitor(p, np.array([[0.0, 1.0], [0.1, 2.0]]), width=None)
    with pytest.raises(PostProcessError, match="width"):
        synthesize_total_field([p], x0=0.0, x=0.0, n_modes=1, D=None)


def test_synth_shape_mismatch_raises() -> None:
    """Mismatched modal field shapes raise PostProcessError."""
    data1 = np.array([[0.0, 1.0], [0.1, 2.0], [0.2, 3.0]])      # 1 field col
    data2 = np.array([[0.0, 1.0, 2.0], [0.1, 3.0, 4.0], [0.2, 5.0, 6.0]])  # 2 cols
    p1 = Path("/tmp") / "monitor_shape_a.txt"
    p2 = Path("/tmp") / "monitor_shape_b.txt"
    _write_monitor(p1, data1, width=0.05)
    _write_monitor(p2, data2, width=0.05)

    with pytest.raises(PostProcessError, match="mismatch"):
        synthesize_total_field([p1, p2], x0=0.0, x=0.0, n_modes=2, D=0.05)


def test_synth_n_modes_limits_mode_count() -> None:
    """n_modes limits how many modes contribute to the total field."""
    D = 0.05
    files = []
    for idx, scale in enumerate((1.0, 2.0, 3.0)):
        p = Path("/tmp") / f"monitor_limit_m{2 * idx + 1}.txt"
        _write_monitor(p, np.array([[0.0, scale], [0.1, 2.0 * scale]]), width=D)
        files.append(p)

    limited = synthesize_total_field(files, x0=0.0, x=0.0, n_modes=2, D=D)
    first_two = synthesize_total_field(files[:2], x0=0.0, x=0.0, n_modes=2, D=D)

    np.testing.assert_allclose(limited, first_two)


# ---------------------------------------------------------------------------
# extract_point_monitor
# ---------------------------------------------------------------------------


def test_extract_point_monitor_recta_basic_trace() -> None:
    """Returns (T, trace) with a 1-D interpolated, negated trace."""
    F = np.arange(18.0).reshape(3, 3, 2)
    mon = make_monitor(F, T=np.array([0.0, 1.0, 2.0]),
                       Z=np.array([0.0, 0.5, 1.0]),
                       R=np.array([0.0, 0.5]))
    T, trace = extract_point_monitor(mon, z=0.25, r=0.25, geometry="recta")
    np.testing.assert_array_equal(T, mon.T)
    # F[i, :, :] = [[6i, 6i+1], [6i+2, 6i+3], [6i+4, 6i+5]]
    # interp(0.25, 0.25) = 6i + 1.5, then negated by MATLAB convention.
    np.testing.assert_allclose(trace, [-1.5, -7.5, -13.5])


def test_extract_point_monitor_exact_grid_value() -> None:
    """Exact grid point returns the negated stored field value."""
    F = np.arange(18.0).reshape(3, 3, 2)
    mon = make_monitor(F, T=np.array([0.0, 1.0, 2.0]),
                       Z=np.array([0.0, 0.5, 1.0]),
                       R=np.array([0.0, 0.5]))
    T, trace = extract_point_monitor(mon, z=0.5, r=0.0, geometry="recta")
    np.testing.assert_array_equal(T, mon.T)
    # F[i, 1, 0] = 6i + 2
    np.testing.assert_allclose(trace, [-2.0, -8.0, -14.0])


def test_extract_point_monitor_out_of_bounds_zero() -> None:
    """Coordinates outside the grid interpolate to 0.0."""
    F = np.arange(18.0).reshape(3, 3, 2)
    mon = make_monitor(F, T=np.array([0.0, 1.0, 2.0]),
                       Z=np.array([0.0, 0.5, 1.0]),
                       R=np.array([0.0, 0.5]))
    T, trace = extract_point_monitor(mon, z=5.0, r=0.25, geometry="recta")
    np.testing.assert_array_equal(T, mon.T)
    np.testing.assert_allclose(trace, [0.0, 0.0, 0.0])


def test_extract_point_monitor_z_type_mesh_pos_shift() -> None:
    """z-type monitors reconstruct the lab frame with the mesh position."""
    F = np.arange(18.0).reshape(3, 3, 2)
    mon = make_monitor(F, T=np.array([0.0, 1.0, 2.0]),
                       Z=np.array([0.0, 0.5, 1.0]),
                       R=np.array([0.0, 0.5]), time_type="z")
    mon._mesh_pos = np.array([1.0, 1.0, 1.0])

    T, trace = extract_point_monitor(mon, z=1.25, r=0.25, geometry="recta")
    np.testing.assert_array_equal(T, mon.T)
    # z_lab = 1.0 + Z, so z=1.25 in the lab frame is 0.25 locally.
    np.testing.assert_allclose(trace, [-1.5, -7.5, -13.5])


def test_extract_point_monitor_s_type_zero_mesh_pos() -> None:
    """s-type monitors default to a zero mesh position (static window)."""
    F = np.arange(18.0).reshape(3, 3, 2)
    mon = make_monitor(F, T=np.array([0.0, 1.0, 2.0]),
                       Z=np.array([0.0, 0.5, 1.0]),
                       R=np.array([0.0, 0.5]), time_type="s")
    assert not hasattr(mon, "_mesh_pos")

    T, trace = extract_point_monitor(mon, z=0.25, r=0.25, geometry="recta")
    np.testing.assert_array_equal(T, mon.T)
    np.testing.assert_allclose(trace, [-1.5, -7.5, -13.5])


def test_extract_point_monitor_non3d_raises_valueerror() -> None:
    """Non-3-D monitor data raises ValueError."""
    F = np.array(
        [[0.0, 1.0, 2.0], [3.0, 4.0, 5.0], [6.0, 7.0, 8.0], [9.0, 10.0, 11.0]]
    )
    mon = make_monitor(F, T=np.array([0.0, 1.0, 2.0, 3.0]),
                       R=np.array([0.0, 0.5, 1.0]))
    with pytest.raises(ValueError, match="3-D"):
        extract_point_monitor(mon, z=0.5, r=0.25, geometry="recta")


def test_extract_point_monitor_round_ep_divides_by_r() -> None:
    """Round-geometry Ep is stored as Ep*r and divided back by r."""
    F = np.arange(18.0).reshape(3, 3, 2)
    mon = make_monitor(F, T=np.array([0.0, 1.0, 2.0]),
                       Z=np.array([0.0, 0.5, 1.0]),
                       R=np.array([0.0, 0.5]), component="Ep")
    T, trace = extract_point_monitor(mon, z=0.25, r=0.25, geometry="round")
    np.testing.assert_array_equal(T, mon.T)
    # raw interp = -(6i+1.5), then divided by r=0.25.
    np.testing.assert_allclose(trace, [-6.0, -30.0, -54.0])


def test_extract_point_monitor_round_ep_r_zero_no_division() -> None:
    """At r=0 the Ep division is skipped, leaving the raw interpolant."""
    F = np.arange(18.0).reshape(3, 3, 2)
    mon = make_monitor(F, T=np.array([0.0, 1.0, 2.0]),
                       Z=np.array([0.0, 0.5, 1.0]),
                       R=np.array([0.0, 0.5]), component="Ep")
    T, trace = extract_point_monitor(mon, z=0.25, r=0.0, geometry="round")
    np.testing.assert_array_equal(T, mon.T)
    # interp(0.25, 0.0) = 6i+1 (no /r because |r| <= 1e-30).
    np.testing.assert_allclose(trace, [-1.0, -7.0, -13.0])


# ---------------------------------------------------------------------------
# save_point_monitor
# ---------------------------------------------------------------------------


def test_save_point_monitor_creates_file() -> None:
    """save_point_monitor writes a file to the requested path."""
    T = np.array([0.0, 1.0, 2.0])
    trace = np.array([1.5, 2.5, 3.5])
    out = Path("/tmp") / "pm_basic.txt"
    save_point_monitor(out, T, trace, component="Ez", geometry="recta")
    assert out.is_file()


def test_save_point_monitor_creates_nested_dirs() -> None:
    """Missing parent directories are created automatically."""
    T = np.array([0.0, 1.0])
    trace = np.array([1.5, 2.5])
    out = Path("/tmp") / "nested" / "deep" / "pm.txt"
    save_point_monitor(out, T, trace, component="Ez", geometry="recta")
    assert out.is_file()
    assert out.parent.is_dir()


def test_save_point_monitor_header_format() -> None:
    """The file begins with MATLAB-compatible '%' header lines."""
    T = np.array([0.0, 1.0])
    trace = np.array([1.5, 2.5])
    out = Path("/tmp") / "pm_header.txt"
    save_point_monitor(out, T, trace, component="Ez", geometry="recta")
    lines = out.read_text(encoding="utf-8").splitlines()
    assert lines[0].startswith("% PointMonitor: Ez")
    assert lines[1].startswith("% ct [m]")


def test_save_point_monitor_data_roundtrip() -> None:
    """The saved data reloads to the original (T, trace) columns."""
    T = np.array([0.0, 1.0, 2.0])
    trace = np.array([1.5, 2.5, 3.5])
    out = Path("/tmp") / "pm_roundtrip.txt"
    save_point_monitor(out, T, trace, component="Ez", geometry="recta")
    loaded = np.loadtxt(out, comments="%")
    np.testing.assert_allclose(loaded[:, 0], T)
    np.testing.assert_allclose(loaded[:, 1], trace)


def test_save_point_monitor_two_column_layout() -> None:
    """The output is strictly two ASCII columns of coordinates + field."""
    T = np.array([0.0, 0.1, 0.2, 0.3])
    trace = np.array([1.0, 2.0, 3.0, 4.0])
    out = Path("/tmp") / "pm_two_col.txt"
    save_point_monitor(out, T, trace, component="Ez", geometry="recta")
    loaded = np.loadtxt(out, comments="%")
    assert loaded.ndim == 2
    assert loaded.shape == (4, 2)
    np.testing.assert_allclose(loaded, np.column_stack([T, trace]))
