"""Tests for :mod:`pyecho.parser`.

All tests build synthetic ECHO2D output files (wake potentials, WakeMonitor
binaries, current profiles, field monitors, particle dumps, coupling matrices,
beam moments) under ``tmp_path`` and exercise the ``OutputLoader`` / free
function API against them.
"""

from __future__ import annotations

import struct
from pathlib import Path

import numpy as np
import pytest

from pyecho.errors import ParserError
from pyecho.parser import (
    OutputLoader,
    find_wake_file,
    list_wake_files,
    load_bunch_profile,
    parse_wake_file,
)

# ---------------------------------------------------------------------------
# Synthetic file helpers
# ---------------------------------------------------------------------------

def _write_text(path: Path, text: str) -> Path:
    """Write *text* to *path*, creating parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _valid_wake_lines(hr: str = "0.001", offset: str = "3",
                      D: str = "0.02", sigma: str = "0.005") -> str:
    """Return the text of a well-formed ``wakeL_XX.txt`` file."""
    return (
        f"{hr} {offset}\n"
        f"{D} {sigma}\n"
        "0.0 1.0\n"
        "0.001 0.9\n"
        "0.002 0.8\n"
    )


def _make_wake_file(tmp_path: Path, name: str = "wakeL_00.txt",
                    subdir: str = "round") -> Path:
    """Write a standard wake file under ``tmp_path/<subdir>``."""
    return _write_text(tmp_path / subdir / name, _valid_wake_lines())


def _make_loader(tmp_path: Path, subdir: str = "round") -> OutputLoader:
    """Return an ``OutputLoader`` whose data dir contains a wake file."""
    _make_wake_file(tmp_path, subdir=subdir)
    return OutputLoader(tmp_path)


def _monitor_text(kind: str = "s", component: str = "Ez") -> str:
    """Return the text of a small field monitor file.

    ``kind="s"`` yields an s-time (static lab-frame) monitor with ``k_z``;
    ``kind="z"`` yields a z-time (co-moving) monitor with ``k_s``.
    """
    if kind == "s":
        axis = "k_z=2 h_z=5.000000e-04 z0=0.000000e+00"
    else:
        axis = "k_s=2 h_s=5.000000e-04 s0=0.000000e+00"
    return (
        f"% field component = {component}\n"
        "% k_ct=2 h_ct=1.000000e-03 ct0=0.000000e+00\n"
        f"% {axis}\n"
        "% k_r=1 h_r=1.000000e-03 r0=0.000000e+00\n"
        "0.0 1.0 2.0\n"
        "0.001 3.0 4.0\n"
    )


def _write_monitor(path: Path, kind: str = "s", component: str = "Ez") -> Path:
    """Write a small field monitor file and return its path."""
    return _write_text(path, _monitor_text(kind=kind, component=component))


def _write_wake_monitor(path: Path, values: list[float]) -> Path:
    """Write a Fortran-style WakeMonitor binary file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = struct.pack("<d", float(len(values)))
    raw += struct.pack(f"<{len(values)}d", *values)
    path.write_bytes(raw)
    return path


def _write_particles(path: Path, n_particles: int, q0: float = 1.5e-9) -> Path:
    """Write a ``particles.out`` binary file and return its path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    coords = np.arange(6 * n_particles, dtype=np.float64) + 0.5
    status: np.ndarray = np.arange(n_particles, dtype=np.int64)
    raw = struct.pack("<dd", float(n_particles), q0)
    raw += struct.pack(f"<{6 * n_particles}d", *coords)
    raw += struct.pack(f"<{n_particles}q", *status)
    path.write_bytes(raw)
    return path


# ---------------------------------------------------------------------------
# parse_wake_file
# ---------------------------------------------------------------------------

def test_parse_wake_file_valid(tmp_path: Path) -> None:
    """A well-formed wake file is parsed into the documented keys."""
    f = _make_wake_file(tmp_path)
    parsed = parse_wake_file(f)
    assert parsed["hr"] == pytest.approx(0.001)
    assert parsed["offset"] == 3
    assert parsed["D"] == pytest.approx(0.02)
    assert parsed["sigma"] == pytest.approx(0.005)
    np.testing.assert_allclose(parsed["s"], [0.0, 0.001, 0.002])
    np.testing.assert_allclose(parsed["W_raw"], [1.0, 0.9, 0.8])
    assert parsed["mode"] == 0


def test_parse_wake_file_missing(tmp_path: Path) -> None:
    """A missing file raises ParserError."""
    with pytest.raises(ParserError):
        parse_wake_file(tmp_path / "nope.txt")


def test_parse_wake_file_empty(tmp_path: Path) -> None:
    """An empty file raises ParserError."""
    f = _write_text(tmp_path / "wakeL_00.txt", "")
    with pytest.raises(ParserError):
        parse_wake_file(f)


def test_parse_wake_file_too_few_data_lines(tmp_path: Path) -> None:
    """A file with only the two header rows raises ParserError."""
    f = _write_text(tmp_path / "wakeL_00.txt", "0.001 3\n0.02 0.005\n")
    with pytest.raises(ParserError):
        parse_wake_file(f)


def test_parse_wake_file_invalid_header(tmp_path: Path) -> None:
    """A non-numeric header line raises ParserError."""
    f = _write_text(
        tmp_path / "wakeL_00.txt",
        "abc def\n0.02 0.005\n0.0 1.0\n0.001 0.9\n0.002 0.8\n",
    )
    with pytest.raises(ParserError):
        parse_wake_file(f)


def test_parse_wake_file_invalid_data(tmp_path: Path) -> None:
    """A non-numeric data line raises ParserError."""
    f = _write_text(
        tmp_path / "wakeL_00.txt",
        "0.001 3\n0.02 0.005\n0.0 one\n0.001 0.9\n0.002 0.8\n",
    )
    with pytest.raises(ParserError):
        parse_wake_file(f)


def test_parse_wake_file_skips_comments(tmp_path: Path) -> None:
    """Comment lines and blanks are ignored when parsing."""
    f = _write_text(
        tmp_path / "wakeL_00.txt",
        "% comment\n0.001 3\n\n0.02 0.005\n0.0 1.0\n0.001 0.9\n0.002 0.8\n",
    )
    parsed = parse_wake_file(f)
    assert parsed["hr"] == pytest.approx(0.001)
    assert parsed["offset"] == 3
    np.testing.assert_allclose(parsed["s"], [0.0, 0.001, 0.002])


def test_parse_wake_file_mode_detection(tmp_path: Path) -> None:
    """The mode is read from the filename, case-insensitively."""
    f_lo = _write_text(tmp_path / "wakeL_07.txt", _valid_wake_lines())
    f_hi = _write_text(tmp_path / "WakeL_03.txt", _valid_wake_lines())
    assert parse_wake_file(f_lo)["mode"] == 7
    assert parse_wake_file(f_hi)["mode"] == 3


# ---------------------------------------------------------------------------
# find_wake_file / list_wake_files
# ---------------------------------------------------------------------------

def test_find_wake_file(tmp_path: Path) -> None:
    """find_wake_file locates wakeL files case-insensitively."""
    assert find_wake_file(tmp_path, 0) is None
    _make_wake_file(tmp_path)
    found = find_wake_file(tmp_path / "round", 0)
    assert found is not None
    assert found.name == "wakeL_00.txt"
    f = _write_text(tmp_path / "round" / "WakeL_05.txt", _valid_wake_lines())
    assert find_wake_file(tmp_path / "round", 5) == f


def test_list_wake_files(tmp_path: Path) -> None:
    """list_wake_files returns sorted wake files, excluding others."""
    assert list_wake_files(tmp_path) == []
    data = tmp_path / "round"
    _write_text(data / "wakeL_00.txt", _valid_wake_lines())
    _write_text(data / "wakeL_01.txt", _valid_wake_lines())
    _write_text(data / "wakeL_02.txt", _valid_wake_lines())
    _write_text(data / "other.txt", "not a wake file\n")
    assert [p.name for p in list_wake_files(data)] == [
        "wakeL_00.txt", "wakeL_01.txt", "wakeL_02.txt",
    ]


# ---------------------------------------------------------------------------
# OutputLoader construction
# ---------------------------------------------------------------------------

def test_output_loader_missing_dir(tmp_path: Path) -> None:
    """Constructing an OutputLoader for a missing dir raises ParserError."""
    with pytest.raises(ParserError):
        OutputLoader(tmp_path / "nope")


def test_output_loader_detects_subdir(tmp_path: Path) -> None:
    """The geometry-type subdirectory is auto-detected."""
    _make_wake_file(tmp_path, subdir="round")
    loader = OutputLoader(tmp_path)
    assert loader.geometry_type == "round"
    assert loader._data_dir == (tmp_path / "round").resolve()


def test_output_loader_direct_data_dir(tmp_path: Path) -> None:
    """Data placed directly in the output dir is used as-is."""
    _write_text(tmp_path / "wakeL_00.txt", _valid_wake_lines())
    loader = OutputLoader(tmp_path)
    assert loader.geometry_type == "unknown"
    assert loader._data_dir == tmp_path.resolve()


def test_output_loader_prefix_subdir(tmp_path: Path) -> None:
    """A prefixed subdirectory (e.g. round_collimator) is matched."""
    _make_wake_file(tmp_path, subdir="round_collimator")
    loader = OutputLoader(tmp_path)
    assert loader.geometry_type == "round"
    assert loader._data_dir == (tmp_path / "round_collimator").resolve()


# ---------------------------------------------------------------------------
# load_wake / load_all_wakes
# ---------------------------------------------------------------------------

def test_load_wake_valid(tmp_path: Path) -> None:
    """load_wake returns the documented 6-tuple."""
    loader = _make_loader(tmp_path)
    s, W_raw, hr, offset, D, sigma = loader.load_wake(0)
    np.testing.assert_allclose(s, [0.0, 0.001, 0.002])
    np.testing.assert_allclose(W_raw, [1.0, 0.9, 0.8])
    assert hr == pytest.approx(0.001)
    assert offset == 3
    assert D == pytest.approx(0.02)
    assert sigma == pytest.approx(0.005)


def test_load_wake_missing(tmp_path: Path) -> None:
    """Loading a non-existent mode raises ParserError."""
    loader = _make_loader(tmp_path)
    with pytest.raises(ParserError):
        loader.load_wake(4)


def test_load_wake_case_insensitive(tmp_path: Path) -> None:
    """load_wake finds capital-W wake files."""
    _write_text(tmp_path / "round" / "WakeL_00.txt", _valid_wake_lines())
    loader = OutputLoader(tmp_path)
    s, *_ = loader.load_wake(0)
    np.testing.assert_allclose(s, [0.0, 0.001, 0.002])


def test_load_all_wakes(tmp_path: Path) -> None:
    """load_all_wakes collects every mode present."""
    _write_text(tmp_path / "round" / "wakeL_00.txt", _valid_wake_lines())
    _write_text(tmp_path / "round" / "wakeL_01.txt", _valid_wake_lines(offset="4"))
    loader = OutputLoader(tmp_path)
    wakes = loader.load_all_wakes()
    assert set(wakes) == {0, 1}
    np.testing.assert_allclose(wakes[0][0], [0.0, 0.001, 0.002])
    assert wakes[1][3] == 4


def test_load_all_wakes_empty(tmp_path: Path) -> None:
    """load_all_wakes returns {} when no wake files exist."""
    (tmp_path / "round").mkdir(parents=True)
    loader = OutputLoader(tmp_path)
    assert loader.load_all_wakes() == {}


# ---------------------------------------------------------------------------
# load_wake_monitor / load_all_wake_monitors
# ---------------------------------------------------------------------------

def test_load_wake_monitor_valid(tmp_path: Path) -> None:
    """A WakeMonitor binary is parsed into n/wake/mode/index."""
    _write_wake_monitor(
        tmp_path / "round" / "WakeM_00_000001.bin",
        [1.0, 2.0, 3.0, 4.0, 5.0],
    )
    loader = OutputLoader(tmp_path)
    parsed = loader.load_wake_monitor(mode=0, index=1)
    assert parsed is not None
    assert parsed["n"] == 5
    np.testing.assert_allclose(parsed["wake"], [1.0, 2.0, 3.0, 4.0, 5.0])
    assert parsed["mode"] == 0
    assert parsed["index"] == 1


def test_load_wake_monitor_missing(tmp_path: Path) -> None:
    """A missing WakeMonitor file returns None."""
    loader = _make_loader(tmp_path)
    assert loader.load_wake_monitor(0, 0) is None


def test_load_wake_monitor_malformed(tmp_path: Path) -> None:
    """A too-small WakeMonitor file raises ParserError."""
    (tmp_path / "round").mkdir(parents=True)
    (tmp_path / "round" / "WakeM_00_000000.bin").write_bytes(b"\x00\x00\x00")
    loader = OutputLoader(tmp_path)
    with pytest.raises(ParserError):
        loader.load_wake_monitor(0, 0)


def test_load_all_wake_monitors(tmp_path: Path) -> None:
    """load_all_wake_monitors keys by (mode, index)."""
    _write_wake_monitor(tmp_path / "round" / "WakeM_00_000000.bin", [1.0, 2.0])
    _write_wake_monitor(tmp_path / "round" / "WakeM_01_000000.bin", [3.0])
    loader = OutputLoader(tmp_path)
    parsed = loader.load_all_wake_monitors()
    assert set(parsed) == {(0, 0), (1, 0)}
    np.testing.assert_allclose(parsed[(0, 0)]["wake"], [1.0, 2.0])
    np.testing.assert_allclose(parsed[(1, 0)]["wake"], [3.0])


def test_load_all_wake_monitors_empty(tmp_path: Path) -> None:
    """load_all_wake_monitors returns {} when no binaries exist."""
    loader = _make_loader(tmp_path)
    assert loader.load_all_wake_monitors() == {}


# ---------------------------------------------------------------------------
# load_currents / load_currents_radial
# ---------------------------------------------------------------------------

def test_load_currents_valid(tmp_path: Path) -> None:
    """Iz0.txt is loaded as (s, 2-D current)."""
    _write_text(
        tmp_path / "round" / "Iz0.txt",
        "0.0 1.0 2.0\n0.1 1.1 2.1\n0.2 1.2 2.2\n",
    )
    loader = OutputLoader(tmp_path)
    s, cur = loader.load_currents()
    np.testing.assert_allclose(s, [0.0, 0.1, 0.2])
    np.testing.assert_allclose(cur, [[1.0, 2.0], [1.1, 2.1], [1.2, 2.2]])


def test_load_currents_missing(tmp_path: Path) -> None:
    """load_currents returns None when Iz0.txt is absent."""
    loader = _make_loader(tmp_path)
    assert loader.load_currents() is None


def test_load_currents_radial_valid(tmp_path: Path) -> None:
    """Ir0.txt is loaded as (s, 2-D current)."""
    _write_text(tmp_path / "round" / "Ir0.txt", "0.0 5.0\n0.1 6.0\n")
    loader = OutputLoader(tmp_path)
    s, cur = loader.load_currents_radial()
    np.testing.assert_allclose(s, [0.0, 0.1])
    np.testing.assert_allclose(cur, [[5.0], [6.0]])


def test_load_currents_radial_missing(tmp_path: Path) -> None:
    """load_currents_radial returns None when Ir0.txt is absent."""
    loader = _make_loader(tmp_path)
    assert loader.load_currents_radial() is None


# ---------------------------------------------------------------------------
# load_monitor
# ---------------------------------------------------------------------------

def test_load_monitor_s_type(tmp_path: Path) -> None:
    """An s-type monitor (k_z header) is reshaped onto the z-grid."""
    _write_monitor(tmp_path / "round" / "Monitor_m00_N01.txt", kind="s")
    loader = OutputLoader(tmp_path)
    mon = loader.load_monitor(mode=0, monitor_id=1)
    assert mon is not None
    assert mon.time_type == "s"
    assert mon.monitor_id == 1
    assert mon.field_component == "Ez"
    np.testing.assert_allclose(mon.T, [0.0, 0.001])
    np.testing.assert_allclose(mon.Z, [0.0, 5.0e-4])
    assert mon.F.shape == (2, 2, 1)
    np.testing.assert_allclose(mon.F[:, 0, 0], [1.0, 3.0])
    np.testing.assert_allclose(mon.F[:, 1, 0], [2.0, 4.0])


def test_load_monitor_z_type(tmp_path: Path) -> None:
    """A z-type monitor (k_s header) uses Z = -S."""
    _write_monitor(tmp_path / "round" / "Monitor_m00_N01.txt", kind="z")
    loader = OutputLoader(tmp_path)
    mon = loader.load_monitor(0, 1)
    assert mon is not None
    assert mon.time_type == "z"
    np.testing.assert_allclose(mon.Z, -np.array([0.0, 5.0e-4]))
    assert mon.F.shape == (2, 2, 1)


def test_load_monitor_missing(tmp_path: Path) -> None:
    """load_monitor returns None when the file is absent."""
    loader = _make_loader(tmp_path)
    assert loader.load_monitor(0, 1) is None


def test_load_monitor_legacy_unpadded(tmp_path: Path) -> None:
    """Unpadded legacy filenames (Monitor_m1_N1.txt) are found."""
    _write_monitor(tmp_path / "round" / "Monitor_m1_N1.txt", kind="s")
    loader = OutputLoader(tmp_path)
    mon = loader.load_monitor(mode=1, monitor_id=1)
    assert mon is not None
    assert mon.monitor_id == 1


def test_load_monitor_empty_data_returns_none(tmp_path: Path) -> None:
    """A monitor file with header-only content is skipped (None)."""
    _write_text(
        tmp_path / "round" / "Monitor_m00_N01.txt",
        "% k_ct=2 h_ct=1.000000e-03 ct0=0.000000e+00\n"
        "% k_z=2 h_z=5.000000e-04 z0=0.000000e+00\n",
    )
    loader = OutputLoader(tmp_path)
    assert loader.load_monitor(0, 1) is None


def test_load_monitor_field_component_detection(tmp_path: Path) -> None:
    """The field component is read from the header comment."""
    _write_monitor(tmp_path / "round" / "Monitor_m00_N01.txt", component="Ey")
    loader = OutputLoader(tmp_path)
    mon = loader.load_monitor(0, 1)
    assert mon is not None
    assert mon.field_component == "Ey"


# ---------------------------------------------------------------------------
# list_monitors
# ---------------------------------------------------------------------------

def test_list_monitors(tmp_path: Path) -> None:
    """list_monitors returns sorted (mode, monitor_id) tuples."""
    _write_text(tmp_path / "round" / "Monitor_m00_N01.txt", _monitor_text())
    _write_text(tmp_path / "round" / "Monitor_m01_N02.txt", _monitor_text())
    loader = OutputLoader(tmp_path)
    assert loader.list_monitors() == [(0, 1), (1, 2)]


# ---------------------------------------------------------------------------
# particles
# ---------------------------------------------------------------------------

def test_load_particles_structured_array(tmp_path: Path) -> None:
    """particles.out is parsed into a structured array."""
    _write_particles(tmp_path / "round" / "particles.out", n_particles=3)
    loader = OutputLoader(tmp_path)
    parts = loader.load_particles()
    assert parts is not None
    assert parts.shape == (3,)
    assert parts.dtype.names == ("x", "y", "z", "px", "py", "pz", "status")
    np.testing.assert_allclose(parts["x"], [0.5, 6.5, 12.5])
    np.testing.assert_allclose(parts["z"], [2.5, 8.5, 14.5])
    np.testing.assert_allclose(parts["pz"], [5.5, 11.5, 17.5])
    np.testing.assert_array_equal(parts["status"], [0, 1, 2])


def test_load_particles_missing(tmp_path: Path) -> None:
    """load_particles returns None when particles.out is absent."""
    loader = _make_loader(tmp_path)
    assert loader.load_particles() is None


# ---------------------------------------------------------------------------
# wcc / wss
# ---------------------------------------------------------------------------

def test_load_wcc_valid(tmp_path: Path) -> None:
    """Wcc_odd.txt is loaded as a matrix."""
    _write_text(tmp_path / "round" / "Wcc_odd.txt", "1.0 2.0\n3.0 4.0\n")
    loader = OutputLoader(tmp_path)
    m = loader.load_wcc()
    assert m is not None
    np.testing.assert_allclose(m, [[1.0, 2.0], [3.0, 4.0]])


def test_load_wcc_missing(tmp_path: Path) -> None:
    """load_wcc returns None when Wcc_odd.txt is absent."""
    loader = _make_loader(tmp_path)
    assert loader.load_wcc() is None


def test_load_wss_valid(tmp_path: Path) -> None:
    """Wss_odd.txt is loaded as a matrix."""
    _write_text(tmp_path / "round" / "Wss_odd.txt", "0.1 0.2\n0.3 0.4\n")
    loader = OutputLoader(tmp_path)
    m = loader.load_wss()
    assert m is not None
    np.testing.assert_allclose(m, [[0.1, 0.2], [0.3, 0.4]])


def test_load_wss_missing(tmp_path: Path) -> None:
    """load_wss returns None when Wss_odd.txt is absent."""
    loader = _make_loader(tmp_path)
    assert loader.load_wss() is None


# ---------------------------------------------------------------------------
# beam moments
# ---------------------------------------------------------------------------

def test_load_beam_moments(tmp_path: Path) -> None:
    """BeamMomentsMonitor.txt is loaded as a 2-D array."""
    _write_text(
        tmp_path / "round" / "BeamMomentsMonitor.txt",
        "0.0 1.0 2.0\n0.5 3.0 4.0\n",
    )
    loader = OutputLoader(tmp_path)
    m = loader.load_beam_moments()
    assert m is not None
    assert m.shape == (2, 3)
    np.testing.assert_allclose(m[0], [0.0, 1.0, 2.0])


# ---------------------------------------------------------------------------
# has_output
# ---------------------------------------------------------------------------

def test_has_output_true(tmp_path: Path) -> None:
    """has_output is True when known result files exist."""
    loader = _make_loader(tmp_path)
    assert loader.has_output() is True


def test_has_output_false(tmp_path: Path) -> None:
    """has_output is False for an empty output directory."""
    (tmp_path / "round").mkdir(parents=True)
    loader = OutputLoader(tmp_path)
    assert loader.has_output() is False


# ---------------------------------------------------------------------------
# load_bunch_profile
# ---------------------------------------------------------------------------

def test_load_bunch_profile_raw(tmp_path: Path) -> None:
    """load_bunch_profile returns the raw (s, I) profile scaled by 1e9."""
    _write_text(
        tmp_path / "round" / "Iz0.txt",
        "0.0 1.0 5.0\n0.1 1.1 6.0\n0.2 1.2 7.0\n",
    )
    s, current = load_bunch_profile(tmp_path / "round", offset=0)
    np.testing.assert_allclose(s, [0.0, 0.1, 0.2])
    np.testing.assert_allclose(current, [5.0e9, 6.0e9, 7.0e9])


def test_load_bunch_profile_missing(tmp_path: Path) -> None:
    """load_bunch_profile returns (None, None) when Iz0.txt is absent."""
    assert load_bunch_profile(tmp_path / "round", offset=0) == (None, None)


def test_load_bunch_profile_interpolated(tmp_path: Path) -> None:
    """load_bunch_profile interpolates onto the wake s-grid."""
    _write_text(
        tmp_path / "round" / "Iz0.txt",
        "0.0 1.0 5.0\n0.1 1.1 6.0\n0.2 1.2 7.0\n",
    )
    s_wake = np.array([0.05, 0.15])
    s, current = load_bunch_profile(tmp_path / "round", offset=0, s_wake=s_wake)
    np.testing.assert_allclose(s, s_wake)
    np.testing.assert_allclose(current, [5.5e9, 6.5e9])
