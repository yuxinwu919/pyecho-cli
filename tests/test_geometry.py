"""Tests for :mod:`pyecho.geometry`.

Exercises the ``RoundGeometry`` / ``RectaGeometry`` builders (pipe, step,
taper, save), the ``load_geometry`` parser, and error handling.  All file
I/O runs under ``tmp_path``.
"""

from __future__ import annotations

import pytest

from pyecho.errors import GeometryError
from pyecho.geometry import RectaGeometry, RoundGeometry, load_geometry


# ---------------------------------------------------------------------------
# RoundGeometry builders
# ---------------------------------------------------------------------------

def test_round_pipe_creates_segment() -> None:
    """A single ``pipe`` produces one horizontal segment and registers it."""
    geo = RoundGeometry()
    result = geo.pipe(radius=1.0, length=10.0)

    assert result is geo  # chainable
    assert len(geo.segments) == 1
    seg = geo.segments[0]
    assert seg["z1"] == 0.0
    assert seg["r1"] == 1.0
    assert seg["z2"] == 10.0
    assert seg["r2"] == 1.0
    assert seg["d"] == RoundGeometry.COUNTERCLOCKWISE
    assert seg["k"] == 0.0
    assert geo.materials[0]["segments"] == [0]


def test_round_pipe_continues_z_and_chains() -> None:
    """Pipes chain end-to-end and an explicit ``z_start`` is honoured."""
    geo = RoundGeometry()
    geo.pipe(1.0, 10.0).pipe(2.0, 5.0)

    assert len(geo.segments) == 2
    assert geo.segments[1]["z1"] == 10.0
    assert geo.segments[1]["z2"] == 15.0
    assert geo.segments[1]["r1"] == 2.0
    assert geo.segments[1]["r2"] == 2.0

    explicit = RoundGeometry().pipe(1.0, 2.0, z_start=7.0)
    assert explicit.segments[0]["z1"] == 7.0
    assert explicit.segments[0]["z2"] == 9.0


def test_round_step_with_radius_change() -> None:
    """A step to a new radius inserts a vertical wall then a horizontal pipe."""
    geo = RoundGeometry()
    geo.pipe(1.0, 10.0).step(2.0, 5.0)

    assert len(geo.segments) == 3
    wall = geo.segments[1]
    assert wall["z1"] == 10.0
    assert wall["z2"] == 10.0
    assert wall["r1"] == 1.0
    assert wall["r2"] == 2.0

    pipe2 = geo.segments[2]
    assert pipe2["z1"] == 10.0
    assert pipe2["z2"] == 15.0
    assert pipe2["r1"] == 2.0
    assert pipe2["r2"] == 2.0
    assert geo.materials[0]["segments"] == [0, 1, 2]


def test_round_step_same_radius_no_wall() -> None:
    """Stepping to the same radius adds only the horizontal segment."""
    geo = RoundGeometry()
    geo.pipe(1.0, 10.0).step(1.0, 5.0)

    assert len(geo.segments) == 2
    assert geo.segments[1]["z1"] == 10.0
    assert geo.segments[1]["z2"] == 15.0
    assert geo.segments[1]["r1"] == 1.0
    assert geo.segments[1]["r2"] == 1.0


def test_round_taper_creates_segment() -> None:
    """A taper is a single diagonal segment using the given radii."""
    geo = RoundGeometry()
    geo.pipe(1.0, 10.0).taper(r_start=1.0, r_end=2.0, length=5.0)

    assert len(geo.segments) == 2
    seg = geo.segments[1]
    assert seg["z1"] == 10.0
    assert seg["z2"] == 15.0
    assert seg["r1"] == 1.0
    assert seg["r2"] == 2.0
    assert geo._current_radius == 2.0


def test_round_save_and_load_roundtrip(tmp_path) -> None:
    """A saved round geometry reloads with identical segment data."""
    geo = RoundGeometry()
    geo.pipe(1.0, 10.0).step(2.0, 5.0).taper(2.0, 3.0, 4.0)
    dest = tmp_path / "round" / "pipe.txt"
    geo.save(dest)

    assert dest.exists()
    parsed = load_geometry(dest)
    assert len(parsed["materials"]) == 1
    mat = parsed["materials"][0]
    assert mat["epsilon"] == 1
    assert mat["mu"] == 1
    assert mat["sigma"] == 0
    assert mat["segments"] == list(range(len(geo.segments)))
    assert len(parsed["segments"]) == len(geo.segments)

    for built, loaded in zip(geo.segments, parsed["segments"]):
        assert loaded["z1"] == built["z1"]
        assert loaded["r1"] == built["r1"]
        assert loaded["z2"] == built["z2"]
        assert loaded["r2"] == built["r2"]
        assert loaded["d"] == built["d"]
        assert loaded["k"] == built["k"]
        # Ellipse bounding-box columns are always written as zeros
        assert loaded["z3"] == 0.0
        assert loaded["z4"] == 0.0
        assert loaded["r3"] == 0.0
        assert loaded["r4"] == 0.0


# ---------------------------------------------------------------------------
# RectaGeometry builders
# ---------------------------------------------------------------------------

def test_recta_pipe_creates_segment() -> None:
    """A single rectangular ``pipe`` records the half-gap as y."""
    geo = RectaGeometry()
    geo.pipe(half_gap=0.5, length=10.0)

    assert len(geo.segments) == 1
    seg = geo.segments[0]
    assert seg["z1"] == 0.0
    assert seg["y1"] == 0.5
    assert seg["z2"] == 10.0
    assert seg["y2"] == 0.5
    assert seg["d"] == RectaGeometry.COUNTERCLOCKWISE
    assert seg["k"] == 0.0
    assert geo.materials[0]["segments"] == [0]


def test_recta_step_with_radius_change() -> None:
    """A rectangular step to a new half-gap adds a vertical wall + pipe."""
    geo = RectaGeometry()
    geo.pipe(0.5, 10.0).step(1.0, 5.0)

    assert len(geo.segments) == 3
    wall = geo.segments[1]
    assert wall["z1"] == 10.0
    assert wall["z2"] == 10.0
    assert wall["y1"] == 0.5
    assert wall["y2"] == 1.0

    pipe2 = geo.segments[2]
    assert pipe2["z1"] == 10.0
    assert pipe2["z2"] == 15.0
    assert pipe2["y1"] == 1.0
    assert pipe2["y2"] == 1.0


def test_recta_taper_creates_segment() -> None:
    """A rectangular taper is a single diagonal segment in y."""
    geo = RectaGeometry()
    geo.pipe(0.5, 10.0).taper(y_start=0.5, y_end=1.5, length=4.0)

    assert len(geo.segments) == 2
    seg = geo.segments[1]
    assert seg["z1"] == 10.0
    assert seg["z2"] == 14.0
    assert seg["y1"] == 0.5
    assert seg["y2"] == 1.5
    assert geo._current_y == 1.5


def test_recta_save_and_load_roundtrip(tmp_path) -> None:
    """A saved flat geometry reloads; y-coordinates land in r1/r2."""
    geo = RectaGeometry()
    geo.pipe(0.5, 10.0).step(1.0, 5.0).taper(1.0, 2.0, 3.0)
    dest = tmp_path / "flat" / "geo.txt"
    geo.save(dest)

    assert dest.exists()
    parsed = load_geometry(dest)
    assert len(parsed["segments"]) == len(geo.segments)
    for built, loaded in zip(geo.segments, parsed["segments"]):
        assert loaded["z1"] == built["z1"]
        assert loaded["r1"] == built["y1"]
        assert loaded["z2"] == built["z2"]
        assert loaded["r2"] == built["y2"]


# ---------------------------------------------------------------------------
# save() edge cases
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("builder", "message"),
    [
        (RoundGeometry, "Cannot save empty geometry"),
        (RectaGeometry, "Cannot save empty flat geometry"),
    ],
)
def test_save_empty_raises(tmp_path, builder, message) -> None:
    """Saving a builder with no segments raises and writes nothing."""
    dest = tmp_path / "empty.txt"
    with pytest.raises(GeometryError, match=message):
        builder().save(dest)
    assert not dest.exists()


def test_save_creates_parent_directories(tmp_path) -> None:
    """save() creates missing parent directories automatically."""
    geo = RoundGeometry().pipe(1.0, 2.0)
    dest = tmp_path / "a" / "b" / "nested.txt"
    geo.save(dest)

    assert dest.exists()
    text = dest.read_text(encoding="utf-8")
    assert text.startswith("% Number of materials")


# ---------------------------------------------------------------------------
# load_geometry
# ---------------------------------------------------------------------------

def test_load_geometry_auto_detect_round(tmp_path) -> None:
    """Round geometry files parse regardless of header comment wording."""
    path = tmp_path / "round.txt"
    path.write_text(
        "% Number of materials\n"
        "1\n"
        "% Number of elements in material with conductive walls, "
        "permittivity, mu, conductivity\n"
        "2 1 1 0\n"
        "0.0 1.0 5.0 1.0 0 0 0 0 1 0.0\n"
        "5.0 1.0 5.0 2.0 0 0 0 0 1 0.0\n",
        encoding="utf-8",
    )

    parsed = load_geometry(path)
    assert len(parsed["segments"]) == 2
    assert parsed["segments"][0]["r1"] == 1.0
    assert parsed["segments"][0]["r2"] == 1.0
    assert parsed["segments"][1]["r1"] == 1.0
    assert parsed["segments"][1]["r2"] == 2.0
    assert parsed["materials"][0]["segments"] == [0, 1]


def test_load_geometry_auto_detect_flat(tmp_path) -> None:
    """Flat geometry files use the same 10-column layout and parse the same."""
    path = tmp_path / "flat.txt"
    path.write_text(
        "% flat geometry (y-coordinates)\n"
        "1\n"
        "2 2 3 0.5\n"
        "0.0 0.5 4.0 0.5 0 0 0 0 1 0.0\n"
        "4.0 0.5 4.0 1.0 0 0 0 0 1 0.0\n",
        encoding="utf-8",
    )

    parsed = load_geometry(path)
    mat = parsed["materials"][0]
    assert mat["epsilon"] == 2
    assert mat["mu"] == 3
    assert mat["sigma"] == 0.5
    # The y-coordinate is stored in the parser's r columns
    assert parsed["segments"][0]["r1"] == 0.5
    assert parsed["segments"][0]["r2"] == 0.5
    assert parsed["segments"][1]["r1"] == 0.5
    assert parsed["segments"][1]["r2"] == 1.0


def test_load_geometry_missing_file_raises(tmp_path) -> None:
    """A nonexistent geometry file raises GeometryError."""
    with pytest.raises(GeometryError, match="not found"):
        load_geometry(tmp_path / "nope.txt")


def test_load_geometry_invalid_segment_raises(tmp_path) -> None:
    """A segment line with fewer than 10 columns raises GeometryError."""
    path = tmp_path / "bad.txt"
    path.write_text(
        "1\n"
        "1 1 1 0\n"
        "0.0 1.0\n",
        encoding="utf-8",
    )
    with pytest.raises(GeometryError, match="10 columns"):
        load_geometry(path)


def test_load_geometry_empty_file_raises(tmp_path) -> None:
    """A file with only comments/blank lines raises GeometryError."""
    path = tmp_path / "empty.txt"
    path.write_text(
        "% nothing here\n"
        "\n"
        "% still nothing\n",
        encoding="utf-8",
    )
    with pytest.raises(GeometryError, match="Empty geometry"):
        load_geometry(path)
