"""Core data classes for ECHO2D simulation results.

Defines structured containers for wake potentials, field monitor data,
mode results, and simulation metadata. Uses dataclasses with numpy
array type annotations for seamless integration with the scientific
Python stack.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np


@dataclass
class WakeResult:
    """Post-processed longitudinal wake potential for a single mode.

    Attributes
    ----------
    s : np.ndarray
        Longitudinal coordinate along the bunch [m].  Positive *s*
        points toward the bunch tail (trailing particle sees the
        wake of leading particles).
    W : np.ndarray
        Wake potential [V/pC].
    bunch : np.ndarray
        Bunch charge-density profile evaluated on the same *s* grid.
    loss_factor : float
        Loss factor κ = −∫ λ(s)·W(s)·ds  [V/pC].
    rms_spread : float
        RMS spread of the wake around −κ  [V/pC].
    peak : float
        Peak absolute value of the wake potential  [V/pC].
    label : str
        Human-readable label (e.g. mode number, geometry tag).
    units : str
        Units string, typically ``"V/pC"``.
    """

    s: np.ndarray
    W: np.ndarray
    bunch: np.ndarray
    loss_factor: float
    rms_spread: float
    peak: float
    label: str = ""
    units: str = "V/pC"


@dataclass
class FlatWakeResult:
    """Complete wake result for recta (rectangular) geometry.

    In a rectangular structure of constant width, the longitudinal
    wake is decomposed into monopole (Wlong), quadrupole (Wquad), and
    dipole (Wdipole) components.  Optionally the full Wcc / Wss
    coupling matrices may be stored.

    .. note::

       This class uses the term ``"recta"`` to match ECHO2D's
       ``GeometryType=recta`` convention.  The CLI may display
       ``"rectangular"`` or ``"flat"`` as user-friendly aliases,
       but internally the geometry type is always ``"recta"``.

    Attributes
    ----------
    s : np.ndarray
        Longitudinal coordinate [m].
    Wlong : np.ndarray
        Monopole (longitudinal) wake  [V/pC].
    Wquad : np.ndarray
        Quadrupole wake (integrated over transverse offset)  [V/pC/mm].
    Wdipole : np.ndarray
        Dipole wake (integrated over transverse offset)  [V/pC/mm].
    loss_long : float
        Longitudinal loss factor [V/pC].
    kick_quad : float
        Quadrupole kick factor [V/pC/mm].
    kick_dipole : float
        Dipole kick factor [V/pC/mm].
    wcc : np.ndarray or None
        Wcc(*k*, *s*) coupling matrix (cos-cos component).
    wss : np.ndarray or None
        Wss(*k*, *s*) coupling matrix (sin-sin component).
    """

    s: np.ndarray
    Wlong: np.ndarray
    Wquad: np.ndarray
    Wdipole: np.ndarray
    loss_long: float
    kick_quad: float
    kick_dipole: float
    wcc: np.ndarray | None = None
    wss: np.ndarray | None = None


@dataclass
class RoundWakeResult:
    """Complete wake result for round (rotationally symmetric) geometry.

    In a rotationally symmetric structure, the wake is decomposed
    into independent azimuthal modes.  m=0 (monopole) gives the
    longitudinal wake potential; m=1 (dipole) gives the dipole
    modal coefficient and transverse kick.

    .. note::

       Uses ECHO2D's ``GeometryType=round`` convention.  The effective
       transverse step follows :math:`dy = (\\mathrm{offset} + 0.5)\\cdot h_r`
       (the +0.5 shift is essential for correctness; see ECHO manual §4.3.2).

    Attributes
    ----------
    s : np.ndarray
        Longitudinal coordinate [m].
    Wlong : np.ndarray
        Monopole (m=0) longitudinal wake potential [V/pC].
    Wdipole : np.ndarray or None
        Dipole (m=1) modal coefficient [V/pC/m²].  ``None`` if
        dipole mode was not computed.
    loss_long : float
        Longitudinal loss factor κ = −∫ λ·Wlong·ds  [V/pC].
    kick_dipole : float or None
        Dipole transverse kick factor [V/pC/m].  ``None`` if
        dipole mode was not computed.
    bunch : np.ndarray
        Bunch charge-density profile on the same *s* grid.
    peak : float
        Peak absolute value of Wlong [V/pC].
    rms_spread : float
        RMS spread of Wlong around −κ [V/pC].
    """

    s: np.ndarray
    Wlong: np.ndarray
    Wdipole: np.ndarray | None
    loss_long: float
    kick_dipole: float | None
    bunch: np.ndarray
    peak: float = 0.0
    rms_spread: float = 0.0


@dataclass
class ModeResult:
    """Raw and processed results for a single Fourier azimuthal mode.

    ECHO2D computes each azimuthal mode *m* independently.  This
    container holds the raw data read from the ``wakeL`` file and,
    after post-processing, the physical wake potential.

    Attributes
    ----------
    mode_number : int
        Azimuthal mode index (0 = monopole, 1 = dipole, …).
    s_raw : np.ndarray
        Raw *s* coordinate from the wakeL file [m].
    W_raw : np.ndarray
        Raw wake potential from the wakeL file [m·V/nC].
    hr : float
        Transverse mesh step used for the mode [m].
    offset : int
        Bunch offset in mesh lines.
    D : float
        Structure width [m] (= ``Width`` in ``input_in.txt``).
        Only meaningful for rectangular geometry (GeometryType=recta);
        zero or placeholder for round geometry.
    sigma : float
        Bunch RMS length [m].
    wake_processed : WakeResult or None
        Processed wake (populated after unit conversion & integration).
    """

    mode_number: int
    s_raw: np.ndarray
    W_raw: np.ndarray
    hr: float
    offset: int
    D: float
    sigma: float
    wake_processed: WakeResult | None = None


@dataclass
class MonitorData:
    """Field monitor data recorded during a simulation.

    ECHO2D can dump electromagnetic field components on 2-D slices
    (either *s*-time or *z*-time).  This container stores the
    resulting grid and field values.

    Attributes
    ----------
    monitor_id : int
        Sequential monitor index.
    field_component : str
        Field component label: ``"Ex"``, ``"Ey"``, ``"Ez"``,
        ``"Hx"``, ``"Hy"``, or ``"Hz"``.
    time_type : str
        Time coordinate type: ``"s"`` (co-moving) or ``"z"`` (lab).
    T : np.ndarray
        1-D array of time (or *s*) coordinates.
    Z : np.ndarray
        1-D array of longitudinal *z* coordinates.
    R : np.ndarray
        1-D array of transverse *r* (round) or *y* (flat) coordinates.
    F : np.ndarray
        Field values as a 2-D (or 3-D) array.
    D : float
        Structure width [m] (= ``Width`` in ``input_in.txt``, recta only).
    """

    monitor_id: int
    field_component: str
    time_type: str
    T: np.ndarray
    Z: np.ndarray
    R: np.ndarray
    F: np.ndarray
    D: float


@dataclass
class RunMetadata:
    """Metadata recorded for a single simulation run.

    Captures execution environment, timing, and reproducibility
    information (input / output hashes).

    Attributes
    ----------
    timestamp : datetime
        Wall-clock time when the run started.
    executable_path : str
        Filesystem path to the ECHO2D binary.
    executable_arch : str
        Architecture label (e.g. ``"MacOS_ARM_OpenMP"``).
    mpi_processes : int
        Number of MPI ranks.
    omp_threads : int
        Number of OpenMP threads.
    elapsed_seconds : float
        Wall-clock duration of the simulation.
    hostname : str
        Hostname where the simulation executed.
    pyecho_version : str
        Version of pyecho used to launch the run.
    input_hash : str
        SHA-256 hash of the input file (reproducibility).
    output_hash : str
        SHA-256 hash of the output directory (reproducibility).
    return_code : int
        Process exit code (0 = success).
    """

    timestamp: datetime = field(default_factory=datetime.now)
    executable_path: str = ""
    executable_arch: str = ""
    mpi_processes: int = 1
    omp_threads: int = 1
    elapsed_seconds: float = 0.0
    hostname: str = ""
    pyecho_version: str = "0.1.0"
    input_hash: str = ""
    output_hash: str = ""
    return_code: int = 0


@dataclass
class SimulationResult:
    """Top-level container for a complete ECHO2D simulation result.

    Bundles the input parameters, output file references, parsed
    mode / current / particle / monitor data, and run metadata into
    a single object that can be serialised (HDF5, pickle) or passed
    to post-processing pipelines.

    Attributes
    ----------
    params : Any
        :class:`ECHO2DParams` instance (lazy reference to avoid
        circular import at the type-annotation level).
    geometry_file : str
        Path to the geometry description file.
    output_dir : str
        Path to the directory containing ECHO2D output files.
    modes : dict[int, ModeResult]
        Mapping from mode number → :class:`ModeResult`.
    currents_z : np.ndarray or None
        Longitudinal current profile (if dumped).
    currents_r : np.ndarray or None
        Transverse current profile (if dumped).
    particles : np.ndarray or None
        Particle phase-space data (if dumped).
    monitors : list[MonitorData]
        Field monitor snapshots.
    metadata : RunMetadata
        Execution metadata.
    stdout : str
        Captured standard output from the ECHO2D process.
    stderr : str
        Captured standard error from the ECHO2D process.
    """

    params: Any = None
    geometry_file: str = ""
    output_dir: str = ""
    modes: dict[int, ModeResult] = field(default_factory=dict)
    currents_z: np.ndarray | None = None
    currents_r: np.ndarray | None = None
    particles: np.ndarray | None = None
    monitors: list[MonitorData] = field(default_factory=list)
    wake_monitors: dict = field(default_factory=dict)
    """WakeMonitor binary data: {(mode, index): {n, wake, mode, index}}."""
    beam_moments: np.ndarray | None = None
    """Beam moments monitor data (time × moments array)."""
    metadata: RunMetadata = field(default_factory=RunMetadata)
    stdout: str = ""
    stderr: str = ""
