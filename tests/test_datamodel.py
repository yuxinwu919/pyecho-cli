"""Tests for the core data classes in ``pyecho/datamodel.py``.

Covers:
- ``WakeResult`` construction and attribute values
- ``RectaWakeResult`` construction, loss/kick factors, and coupling matrices
- ``MonitorData`` construction and the T/Z/R/F axis attributes
- ``ModeResult`` / ``SimulationResult`` / ``RunMetadata`` basic construction
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pytest

from pyecho.datamodel import (
    ModeResult,
    MonitorData,
    RectaWakeResult,
    RunMetadata,
    SimulationResult,
    WakeResult,
)


# ---------------------------------------------------------------------------
# WakeResult
# ---------------------------------------------------------------------------


def test_wake_result_construction_and_attributes() -> None:
    """All required attributes are stored; optional ones use documented defaults."""
    s = np.linspace(0.0, 1.0, 101)
    W = np.sin(s) * 1.0e6
    bunch = np.exp(-((s - 0.5) ** 2) / (2 * 0.1**2))

    result = WakeResult(
        s=s,
        W=W,
        bunch=bunch,
        loss_factor=-1.234e6,
        rms_spread=5.678e4,
        peak=1.0e6,
        label="mode-0",
        units="V/pC",
    )

    assert result.s is s
    assert result.W is W
    assert result.bunch is bunch
    assert result.loss_factor == pytest.approx(-1.234e6)
    assert result.rms_spread == pytest.approx(5.678e4)
    assert result.peak == pytest.approx(1.0e6)
    assert result.label == "mode-0"
    assert result.units == "V/pC"


def test_wake_result_default_label_and_units() -> None:
    """Empty label and the standard ``V/pC`` unit are the defaults."""
    s = np.array([0.0, 0.1])
    result = WakeResult(
        s=s,
        W=np.array([0.0, 1.0]),
        bunch=np.array([1.0, 1.0]),
        loss_factor=0.0,
        rms_spread=0.0,
        peak=1.0,
    )
    assert result.label == ""
    assert result.units == "V/pC"


# ---------------------------------------------------------------------------
# RectaWakeResult
# ---------------------------------------------------------------------------


def test_recta_wake_result_construction() -> None:
    """RectaWakeResult stores all decomposition arrays and scalars."""
    s = np.linspace(0.0, 0.2, 50)
    wlong = np.sin(s)
    wquad = np.cos(s)
    wdipole = s**2

    result = RectaWakeResult(
        s=s,
        Wlong=wlong,
        Wquad=wquad,
        Wdipole=wdipole,
        loss_long=-9.87e5,
        kick_quad=3.21e4,
        kick_dipole=1.11e4,
    )

    assert result.s is s
    assert result.Wlong is wlong
    assert result.Wquad is wquad
    assert result.Wdipole is wdipole
    assert result.loss_long == pytest.approx(-9.87e5)
    assert result.kick_quad == pytest.approx(3.21e4)
    assert result.kick_dipole == pytest.approx(1.11e4)


def test_recta_wake_result_coupling_matrices_default_none() -> None:
    """wcc/wss default to None and can be populated explicitly."""
    result = RectaWakeResult(
        s=np.array([0.0]),
        Wlong=np.array([0.0]),
        Wquad=np.array([0.0]),
        Wdipole=np.array([0.0]),
        loss_long=0.0,
        kick_quad=0.0,
        kick_dipole=0.0,
    )
    assert result.wcc is None
    assert result.wss is None

    wcc = np.zeros((3, 10))
    wss = np.ones((3, 10))
    result.wcc = wcc
    result.wss = wss
    assert result.wcc is wcc
    assert result.wss is wss


# ---------------------------------------------------------------------------
# MonitorData
# ---------------------------------------------------------------------------


def test_monitor_data_construction() -> None:
    """MonitorData stores monitor id, field component, time type, and axes."""
    T = np.linspace(0.0, 2.0e-12, 100)
    Z = np.linspace(0.0, 0.5, 100)
    R = np.linspace(0.0, 0.01, 20)
    F = np.zeros((20, 100))

    mon = MonitorData(
        monitor_id=2,
        field_component="Ez",
        time_type="s",
        T=T,
        Z=Z,
        R=R,
        F=F,
        D=0.03,
    )

    assert mon.monitor_id == 2
    assert mon.field_component == "Ez"
    assert mon.time_type == "s"
    assert mon.T is T
    assert mon.Z is Z
    assert mon.R is R
    assert mon.F is F
    assert mon.D == pytest.approx(0.03)


def test_monitor_data_axis_shapes() -> None:
    """T/Z/R are 1-D axis arrays; F matches the axis dimensions."""
    T = np.linspace(0.0, 1.0, 64)
    Z = np.linspace(0.0, 1.0, 64)
    R = np.linspace(0.0, 0.01, 8)
    F = np.arange(8 * 64, dtype=float).reshape(8, 64)

    mon = MonitorData(
        monitor_id=0,
        field_component="Hx",
        time_type="z",
        T=T,
        Z=Z,
        R=R,
        F=F,
        D=0.0,
    )

    assert mon.T.ndim == 1 and mon.T.shape == (64,)
    assert mon.Z.ndim == 1 and mon.Z.shape == (64,)
    assert mon.R.ndim == 1 and mon.R.shape == (8,)
    assert mon.F.shape == (8, 64)
    assert mon.F.shape == (mon.R.size, mon.T.size)


# ---------------------------------------------------------------------------
# ModeResult
# ---------------------------------------------------------------------------


def test_mode_result_construction() -> None:
    """ModeResult stores raw mode data; wake_processed defaults to None."""
    s_raw = np.array([0.0, 0.1, 0.2])
    W_raw = np.array([1.0, 2.0, 3.0])

    mode = ModeResult(
        mode_number=1,
        s_raw=s_raw,
        W_raw=W_raw,
        hr=5.0e-4,
        offset=2,
        D=0.03,
        sigma=1.0e-3,
    )

    assert mode.mode_number == 1
    assert mode.s_raw is s_raw
    assert mode.W_raw is W_raw
    assert mode.hr == pytest.approx(5.0e-4)
    assert mode.offset == 2
    assert mode.D == pytest.approx(0.03)
    assert mode.sigma == pytest.approx(1.0e-3)
    assert mode.wake_processed is None


def test_mode_result_with_processed_wake() -> None:
    """A post-processed WakeResult can be attached to a ModeResult."""
    wake = WakeResult(
        s=np.array([0.0, 0.1]),
        W=np.array([0.0, 5.0]),
        bunch=np.array([1.0, 1.0]),
        loss_factor=-2.5,
        rms_spread=0.5,
        peak=5.0,
    )
    mode = ModeResult(
        mode_number=0,
        s_raw=np.array([0.0, 0.1]),
        W_raw=np.array([0.0, 5.0]),
        hr=1.0e-3,
        offset=0,
        D=0.0,
        sigma=1.0e-3,
        wake_processed=wake,
    )
    assert mode.wake_processed is wake
    assert mode.wake_processed.peak == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# SimulationResult / RunMetadata
# ---------------------------------------------------------------------------


def test_simulation_result_defaults() -> None:
    """Empty SimulationResult gets empty containers and auto-built metadata."""
    result = SimulationResult()
    assert result.params is None
    assert result.geometry_file == ""
    assert result.output_dir == ""
    assert result.modes == {}
    assert result.currents_z is None
    assert result.currents_r is None
    assert result.particles is None
    assert result.monitors == []
    assert result.wake_monitors == {}
    assert result.beam_moments is None
    assert isinstance(result.metadata, RunMetadata)
    assert result.stdout == ""
    assert result.stderr == ""


def test_simulation_result_bundles_modes_and_monitors() -> None:
    """Populated modes/monitors/metadata are carried through the container."""
    wake = WakeResult(
        s=np.array([0.0, 0.1]),
        W=np.array([0.0, 4.0]),
        bunch=np.array([1.0, 1.0]),
        loss_factor=-2.0,
        rms_spread=0.0,
        peak=4.0,
    )
    mode = ModeResult(
        mode_number=0,
        s_raw=np.array([0.0, 0.1]),
        W_raw=np.array([0.0, 4.0]),
        hr=1.0e-3,
        offset=0,
        D=0.03,
        sigma=1.0e-3,
        wake_processed=wake,
    )
    mon = MonitorData(
        monitor_id=1,
        field_component="Ey",
        time_type="z",
        T=np.zeros(4),
        Z=np.zeros(4),
        R=np.zeros(2),
        F=np.zeros((2, 4)),
        D=0.03,
    )
    meta = RunMetadata(hostname="hpc-node", return_code=0)

    result = SimulationResult(
        params="dummy",
        geometry_file="/g/geom.in",
        output_dir="/o",
        modes={0: mode},
        monitors=[mon],
        metadata=meta,
        stdout="progress 100%",
    )

    assert result.params == "dummy"
    assert result.geometry_file == "/g/geom.in"
    assert result.modes[0] is mode
    assert result.monitors[0] is mon
    assert result.metadata is meta
    assert result.stdout == "progress 100%"


def test_run_metadata_defaults() -> None:
    """RunMetadata auto-fills timestamp and pyecho version with sane defaults."""
    meta = RunMetadata()
    assert isinstance(meta.timestamp, datetime)
    assert meta.executable_path == ""
    assert meta.executable_arch == ""
    assert meta.mpi_processes == 1
    assert meta.omp_threads == 1
    assert meta.elapsed_seconds == pytest.approx(0.0)
    assert meta.hostname == ""
    assert isinstance(meta.pyecho_version, str) and meta.pyecho_version
    assert meta.input_hash == ""
    assert meta.output_hash == ""
    assert meta.return_code == 0


def test_run_metadata_custom_values() -> None:
    """All RunMetadata fields accept explicit values."""
    ts = datetime(2026, 8, 7, 12, 0, 0)
    meta = RunMetadata(
        timestamp=ts,
        executable_path="/opt/echo2d/bin/echo2d",
        executable_arch="MacOS_ARM_OpenMP",
        mpi_processes=4,
        omp_threads=8,
        elapsed_seconds=123.45,
        hostname="login-01",
        pyecho_version="0.3.0",
        input_hash="a" * 64,
        output_hash="b" * 64,
        return_code=1,
    )
    assert meta.timestamp is ts
    assert meta.executable_path == "/opt/echo2d/bin/echo2d"
    assert meta.executable_arch == "MacOS_ARM_OpenMP"
    assert meta.mpi_processes == 4
    assert meta.omp_threads == 8
    assert meta.elapsed_seconds == pytest.approx(123.45)
    assert meta.hostname == "login-01"
    assert meta.pyecho_version == "0.3.0"
    assert meta.input_hash == "a" * 64
    assert meta.output_hash == "b" * 64
    assert meta.return_code == 1
