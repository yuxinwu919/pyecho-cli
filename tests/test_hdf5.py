"""Tests for pyecho.io.hdf5 HDF5 export/import.

Requires the optional ``h5py`` dependency; the whole module is skipped
when it is not installed.
"""

from __future__ import annotations

import numpy as np
import pytest

h5py = pytest.importorskip("h5py")

from pyecho.config import ECHO2DParams
from pyecho.datamodel import (
    ModeResult,
    MonitorData,
    RunMetadata,
    SimulationResult,
    WakeResult,
)
from pyecho.errors import PyEchoError
from pyecho.io.hdf5 import export_hdf5, load_hdf5


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def make_result() -> SimulationResult:
    """Build a fully-populated SimulationResult for round-trip tests."""
    s = np.linspace(-0.01, 0.01, 21)
    W_raw = np.sin(50.0 * s)
    wp = WakeResult(
        s=s,
        W=W_raw * 100.0,
        bunch=np.exp(-(s**2) / (2.0 * 0.003**2)),
        loss_factor=12.5,
        rms_spread=3.25,
        peak=42.0,
    )
    mode = ModeResult(
        mode_number=0,
        s_raw=s,
        W_raw=W_raw,
        hr=0.0015,
        offset=2,
        D=0.02,
        sigma=0.003,
        wake_processed=wp,
    )
    mode1 = ModeResult(
        mode_number=1,
        s_raw=s,
        W_raw=W_raw * 2.0,
        hr=0.0015,
        offset=2,
        D=0.02,
        sigma=0.003,
        wake_processed=None,
    )
    monitor = MonitorData(
        monitor_id=0,
        field_component="Ez",
        time_type="s",
        T=np.linspace(0.0, 1e-9, 11),
        Z=np.linspace(-0.02, 0.02, 5),
        R=np.linspace(0.0, 0.01, 4),
        F=np.random.default_rng(42).normal(size=(11, 5, 4)),
        D=0.02,
    )
    metadata = RunMetadata(
        executable_path="/usr/bin/echo2d",
        executable_arch="MacOS_ARM_OpenMP",
        mpi_processes=1,
        omp_threads=4,
        elapsed_seconds=3.75,
        hostname="test-host",
        input_hash="a" * 64,
        output_hash="b" * 64,
        return_code=0,
    )
    return SimulationResult(
        params=ECHO2DParams(GeometryFile="collimator.txt"),
        geometry_file="collimator.txt",
        output_dir="/tmp/dummy_out",
        modes={0: mode, 1: mode1},
        currents_z=np.linspace(0.0, 1.0, 21),
        currents_r=np.linspace(0.0, 0.5, 21),
        particles=np.arange(30, dtype=np.float64).reshape(5, 6),
        monitors=[monitor],
        metadata=metadata,
        stdout="Simulation completed successfully\n",
        stderr="",
    )


def _group_keys(path: str) -> set[str]:
    with h5py.File(path, "r") as f:
        return set(f.keys())


# ---------------------------------------------------------------------------
# Export structure
# ---------------------------------------------------------------------------


def test_export_creates_file_with_correct_groups(tmp_path):
    """Export creates an HDF5 file with the documented top-level groups."""
    result = make_result()
    out = export_hdf5(result, tmp_path / "sim.h5")

    assert out.is_file()
    assert out.suffix == ".h5"
    groups = _group_keys(str(out))
    assert groups == {"input", "wakes", "currents", "monitors",
                      "particles", "metadata"}


def test_wake_subgroup_attrs(tmp_path):
    """Wakes are stored as mode_XX subgroups with their attribute metadata."""
    result = make_result()
    out = export_hdf5(result, tmp_path / "sim.h5")

    with h5py.File(str(out), "r") as f:
        wakes = f["wakes"]
        assert set(wakes.keys()) == {"mode_00", "mode_01"}
        mode = wakes["mode_00"]
        assert mode.attrs["mode_number"] == 0
        assert mode.attrs["hr"] == pytest.approx(0.0015)
        assert mode.attrs["offset"] == 2
        assert mode.attrs["D"] == pytest.approx(0.02)
        assert mode.attrs["sigma"] == pytest.approx(0.003)
        assert {"s", "W_raw", "W_processed"} <= set(mode.keys())
        assert mode.attrs["loss_factor"] == pytest.approx(12.5)
        # mode without a processed wake has no W_processed dataset
        assert "W_processed" not in wakes["mode_01"]


def test_export_creates_parent_directories(tmp_path):
    """Export auto-creates non-existent parent directories."""
    result = make_result()
    nested = tmp_path / "deep" / "nested" / "dirs"
    out = export_hdf5(result, nested / "sim.h5")

    assert out.is_file()
    assert nested.is_dir()
    assert out == (nested / "sim.h5").resolve()


def test_export_include_input_false(tmp_path):
    """include_input=False omits the /input group."""
    result = make_result()
    out = export_hdf5(result, tmp_path / "sim.h5", include_input=False)

    groups = _group_keys(str(out))
    assert "input" not in groups
    assert "wakes" in groups


# ---------------------------------------------------------------------------
# Round-trip import
# ---------------------------------------------------------------------------


def test_roundtrip_wakes(tmp_path):
    """Wakes survive an export/import round-trip losslessly."""
    result = make_result()
    out = export_hdf5(result, tmp_path / "sim.h5")
    data = load_hdf5(out)

    assert set(data["wakes"].keys()) == {"mode_00", "mode_01"}
    mode = data["wakes"]["mode_00"]
    np.testing.assert_allclose(mode["s"], result.modes[0].s_raw)
    np.testing.assert_allclose(mode["W_raw"], result.modes[0].W_raw)
    np.testing.assert_allclose(
        mode["W_processed"], result.modes[0].wake_processed.W
    )
    assert mode["mode_number"] == 0
    assert mode["hr"] == pytest.approx(0.0015)
    assert mode["offset"] == 2
    assert mode["D"] == pytest.approx(0.02)
    assert mode["sigma"] == pytest.approx(0.003)
    assert mode["loss_factor"] == pytest.approx(12.5)
    assert mode["rms_spread"] == pytest.approx(3.25)
    assert mode["peak"] == pytest.approx(42.0)

    # mode_01 has no processed wake
    mode1 = data["wakes"]["mode_01"]
    assert mode1["W_processed"] is None
    assert mode1["loss_factor"] is None


def test_roundtrip_currents(tmp_path):
    """Current profiles survive an export/import round-trip."""
    result = make_result()
    out = export_hdf5(result, tmp_path / "sim.h5")
    data = load_hdf5(out)

    np.testing.assert_allclose(data["currents"]["Iz"], result.currents_z)
    np.testing.assert_allclose(data["currents"]["Ir"], result.currents_r)


def test_roundtrip_monitors(tmp_path):
    """Field monitor data survives an export/import round-trip."""
    result = make_result()
    out = export_hdf5(result, tmp_path / "sim.h5")
    data = load_hdf5(out)

    assert len(data["monitors"]) == 1
    mon = data["monitors"][0]
    orig = result.monitors[0]
    assert mon["component"] == orig.field_component
    assert mon["time_type"] == orig.time_type
    assert mon["D"] == pytest.approx(orig.D)
    np.testing.assert_allclose(mon["T"], orig.T)
    np.testing.assert_allclose(mon["Z"], orig.Z)
    np.testing.assert_allclose(mon["R"], orig.R)
    np.testing.assert_allclose(mon["F"], orig.F)


def test_roundtrip_particles(tmp_path):
    """Particle phase-space data survives an export/import round-trip."""
    result = make_result()
    out = export_hdf5(result, tmp_path / "sim.h5")
    data = load_hdf5(out)

    assert data["particles"] is not None
    np.testing.assert_allclose(data["particles"], result.particles)


def test_roundtrip_metadata(tmp_path):
    """Run metadata attributes survive an export/import round-trip."""
    result = make_result()
    out = export_hdf5(result, tmp_path / "sim.h5")
    data = load_hdf5(out)

    meta = data["metadata"]
    orig = result.metadata
    assert meta["executable_path"] == orig.executable_path
    assert meta["executable_arch"] == orig.executable_arch
    assert int(meta["mpi_processes"]) == orig.mpi_processes
    assert int(meta["omp_threads"]) == orig.omp_threads
    assert float(meta["elapsed_seconds"]) == pytest.approx(orig.elapsed_seconds)
    assert meta["hostname"] == orig.hostname
    assert meta["input_hash"] == orig.input_hash
    assert meta["output_hash"] == orig.output_hash
    assert int(meta["return_code"]) == orig.return_code
    assert data["stdout"] == result.stdout
    assert data["stderr"] == result.stderr


# ---------------------------------------------------------------------------
# Error handling & directory-path input
# ---------------------------------------------------------------------------


def test_load_missing_file_raises(tmp_path):
    """Loading a non-existent HDF5 file raises PyEchoError."""
    missing = tmp_path / "does_not_exist.h5"
    with pytest.raises(PyEchoError, match="not found"):
        load_hdf5(missing)


def test_directory_path_export(tmp_path):
    """export_hdf5 accepts an ECHO2D output directory path."""
    # Build a minimal output directory with a round/ wakeL_00.txt file.
    out_dir = tmp_path / "sim_out"
    data_dir = out_dir / "round"
    data_dir.mkdir(parents=True)
    wake_lines = [
        "0.001 2",          # hr offset
        "0.02 0.003",       # D sigma
        "0.0 0.5",
        "0.001 0.4",
    ]
    (data_dir / "wakeL_00.txt").write_text(
        "\n".join(wake_lines), encoding="utf-8"
    )

    out = export_hdf5(out_dir, tmp_path / "dir_export.h5")

    assert out.is_file()
    with h5py.File(str(out), "r") as f:
        assert "wakes" in f
        assert "mode_00" in f["wakes"]
        np.testing.assert_allclose(
            f["wakes"]["mode_00"]["s"][()], np.array([0.0, 0.001])
        )
