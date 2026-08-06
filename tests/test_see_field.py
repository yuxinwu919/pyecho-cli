"""Tests for field snapshot extraction along the beam trajectory.

Covers :func:`pyecho.postprocess.particles.load_field_bin` (the ECHO2D
``Field_XX.bin`` binary-format reader, a port of ``A_SeeField.m``) and
:func:`pyecho.postprocess.particles.see_field` (trajectory-aligned slices
and difference maps).

Synthetic snapshots are written to ``tmp_path`` in the exact binary layout
documented in the module: a 2×C-long header (``nx``, ``ny``) followed by
six ``ny × nx`` component grids stored little-endian and column-major
(MATLAB ``fread(fid, [ny nx])`` order).
"""

from __future__ import annotations

import struct
from pathlib import Path

import numpy as np
import pytest

from pyecho.errors import PostProcessError
from pyecho.postprocess.particles import load_field_bin, see_field

_COMPONENTS = ("Ex", "Ey", "Ez", "Hx", "Hy", "Hz")


def _make_grid(nx: int, ny: int, base: float = 0.0) -> np.ndarray:
    """Return an ``ny × nx`` grid of deterministic, non-trivial values.

    ``grid[r, c] = base + r*10 + c`` so every cell is distinct, which makes
    any mis-reshaped / mis-aligned parse immediately visible.
    """
    r = np.arange(ny, dtype=np.float64)[:, None] * 10.0
    c = np.arange(nx, dtype=np.float64)[None, :]
    return base + r + c


def _write_field_bin(
    path: Path,
    nx: int,
    ny: int,
    data: dict[str, np.ndarray] | None = None,
    *,
    long64: bool = True,
) -> None:
    """Write a synthetic ``Field_XX.bin`` snapshot to ``path``.

    Header is 2×C long ints (8-byte ``long`` when ``long64`` is true,
    4-byte otherwise), followed by the six component grids, little-endian
    and column-major.  Unspecified components are written as zeros.
    """
    data = data if data is not None else {}
    header = struct.pack("<qq", nx, ny) if long64 else struct.pack("<ii", nx, ny)
    body = b"".join(
        np.asarray(data.get(name, np.zeros((ny, nx))), dtype=np.float64)
        .reshape(ny, nx)
        .flatten(order="F")
        .tobytes()
        for name in _COMPONENTS
    )
    path.write_bytes(header + body)


# ---------------------------------------------------------------------------
# load_field_bin
# ---------------------------------------------------------------------------


def test_load_field_bin_roundtrip_64bit(tmp_path: Path) -> None:
    nx, ny = 6, 4
    data = {
        name: _make_grid(nx, ny, base=idx * 100.0)
        for idx, name in enumerate(_COMPONENTS)
    }
    path = tmp_path / "Field_01.bin"
    _write_field_bin(path, nx, ny, data)

    parsed = load_field_bin(path)

    assert parsed["nx"] == nx
    assert parsed["ny"] == ny
    for name in _COMPONENTS:
        assert np.array_equal(parsed[name], data[name]), name


def test_load_field_bin_32bit_header(tmp_path: Path) -> None:
    """A Windows-produced file (4-byte C ``long`` header) is detected."""
    nx, ny = 3, 2
    data = {
        "Ex": _make_grid(nx, ny, base=5.0),
        "Ez": _make_grid(nx, ny, base=2.0),
    }
    path = tmp_path / "Field_Win.bin"
    _write_field_bin(path, nx, ny, data, long64=False)

    parsed = load_field_bin(path)

    assert parsed["nx"] == nx
    assert parsed["ny"] == ny
    assert np.array_equal(parsed["Ex"], data["Ex"])
    assert np.array_equal(parsed["Ez"], data["Ez"])
    assert np.array_equal(parsed["Hy"], np.zeros((ny, nx)))


def test_load_field_bin_column_major_reshape(tmp_path: Path) -> None:
    """Grids are reshaped column-major: row = transverse, col = longitudinal."""
    nx, ny = 3, 2
    grid = np.array([[0.0, 1.0, 2.0], [10.0, 11.0, 12.0]])
    # MATLAB fread(fid, [ny nx]) fills column by column:
    # col0=[0,10], col1=[1,11], col2=[2,12].
    ex_linear = np.array([0.0, 10.0, 1.0, 11.0, 2.0, 12.0])
    path = tmp_path / "Field_ColMajor.bin"
    path.write_bytes(
        struct.pack("<qq", nx, ny)
        + ex_linear.tobytes()           # Ex
        + b"\x00" * (5 * ny * nx * 8)   # Ey..Hz all zero
    )

    parsed = load_field_bin(path)

    assert parsed["nx"] == nx
    assert parsed["ny"] == ny
    assert np.array_equal(parsed["Ex"], grid)


def test_load_field_bin_missing_file(tmp_path: Path) -> None:
    with pytest.raises(PostProcessError, match="Cannot read"):
        load_field_bin(tmp_path / "does_not_exist.bin")


def test_load_field_bin_too_small(tmp_path: Path) -> None:
    path = tmp_path / "tiny.bin"
    path.write_bytes(b"\x01\x02\x03\x04")  # smaller than either header size
    with pytest.raises(PostProcessError, match="grid header"):
        load_field_bin(path)


def test_load_field_bin_grid_mismatch(tmp_path: Path) -> None:
    """Declared grid must be consistent with the file size."""
    path = tmp_path / "short.bin"
    # 4×4 grid needs 8 + 6*4*4*8 = 776 bytes; body is truncated to 100.
    path.write_bytes(struct.pack("<qq", 4, 4) + b"\x00" * 100)
    with pytest.raises(PostProcessError, match="grid header"):
        load_field_bin(path)


# ---------------------------------------------------------------------------
# see_field
# ---------------------------------------------------------------------------


def test_see_field_single_snapshot(tmp_path: Path) -> None:
    nx, ny = 6, 4
    data = {
        "Ex": _make_grid(nx, ny, base=1.0),
        "Hy": _make_grid(nx, ny, base=50.0),
    }
    path = tmp_path / "Field_01.bin"
    _write_field_bin(path, nx, ny, data)

    result = see_field(path, component="ex", transverse_index=3)

    assert result["nx"] == nx
    assert result["ny"] == ny
    assert result["component"] == "Ex"  # case-insensitive input is resolved
    assert result["betaz"] == pytest.approx(0.997084677679532)
    assert result["i0"] == 3            # round((1 - betaz) * 1000)
    assert result["trajectory_row"] == 3
    assert np.array_equal(result["z_index"], np.arange(1, nx + 1.0))
    assert np.array_equal(result["F1"], data["Ex"])
    assert np.array_equal(result["slice_1"], data["Ex"][2, :])  # row 3 (1-indexed)
    assert np.array_equal(result["slice_z_1"], result["z_index"] + 3)
    assert result["field"]["nx"] == nx
    assert result["field"]["ny"] == ny
    assert "difference" not in result  # single-snapshot mode


def test_see_field_trajectory_alignment(tmp_path: Path) -> None:
    nx, ny = 6, 4
    f1 = {"Ex": _make_grid(nx, ny, base=1.0)}
    f2 = {"Ex": _make_grid(nx, ny, base=100.0)}
    p1 = tmp_path / "Field_01.bin"
    p2 = tmp_path / "Field_02.bin"
    _write_field_bin(p1, nx, ny, f1)
    _write_field_bin(p2, nx, ny, f2)

    betaz = 0.99  # i0 = round((1 - 0.99) * 1000) = 10
    result = see_field(p1, p2, component="Ex", betaz=betaz, transverse_index=2)

    assert result["i0"] == 10
    assert result["trajectory_row"] == 2
    assert np.array_equal(result["slice_1"], f1["Ex"][1, :])
    assert np.array_equal(result["slice_2"], f2["Ex"][1, :])
    # First snapshot shifted into the co-moving frame; second stays put.
    assert np.array_equal(result["slice_z_1"], result["z_index"] + 10)
    assert np.array_equal(result["slice_z_2"], result["z_index"])
    assert np.array_equal(result["F2"], f2["Ex"])


def test_see_field_difference_map(tmp_path: Path) -> None:
    nx, ny = 6, 4
    f1 = {"Ex": _make_grid(nx, ny, base=1.0)}
    f2 = {"Ex": _make_grid(nx, ny, base=1.5)}
    p1 = tmp_path / "Field_01.bin"
    p2 = tmp_path / "Field_02.bin"
    _write_field_bin(p1, nx, ny, f1)
    _write_field_bin(p2, nx, ny, f2)

    result = see_field(p1, p2)

    expected = f1["Ex"] - f2["Ex"]
    assert result["difference"] is not None
    assert result["difference"].shape == (ny, nx)
    assert np.allclose(result["difference"], expected)


def test_see_field_transverse_index_clamped(tmp_path: Path) -> None:
    nx, ny = 5, 3
    data = {"Ex": _make_grid(nx, ny)}
    path = tmp_path / "Field_01.bin"
    _write_field_bin(path, nx, ny, data)

    # Below the grid: clamped to the first row.
    result_low = see_field(path, transverse_index=0)
    assert result_low["trajectory_row"] == 1
    assert np.array_equal(result_low["slice_1"], data["Ex"][0, :])

    # Above the grid: clamped to the last row.
    result_high = see_field(path, transverse_index=99)
    assert result_high["trajectory_row"] == ny
    assert np.array_equal(result_high["slice_1"], data["Ex"][ny - 1, :])


def test_see_field_unknown_component(tmp_path: Path) -> None:
    path = tmp_path / "Field_01.bin"
    _write_field_bin(path, 4, 4)
    with pytest.raises(PostProcessError, match="Unknown field component"):
        see_field(path, component="Bx")


def test_see_field_incompatible_grids(tmp_path: Path) -> None:
    nx, ny1 = 5, 4
    p1 = tmp_path / "Field_01.bin"
    p2 = tmp_path / "Field_02.bin"
    _write_field_bin(p1, nx, ny1)
    _write_field_bin(p2, 6, ny1)  # different nx

    # Different longitudinal grids: alignment is impossible -> error.
    with pytest.raises(PostProcessError, match="longitudinal grids"):
        see_field(p1, p2)

    # Same nx but different ny: slices kept, difference map omitted (None).
    p3 = tmp_path / "Field_03.bin"
    _write_field_bin(p3, nx, 6)
    result = see_field(p1, p3, transverse_index=3)
    assert result["difference"] is None
    assert result["slice_2"].shape == (nx,)
    assert np.array_equal(result["slice_2"], result["F2"][2, :])  # row 3, 1-indexed
