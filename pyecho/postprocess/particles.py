"""Particle data post-processing.

Replicates ECHO2D's particle analysis MATLAB scripts:
* ``AnalyseParticles.m`` — load and analyse particle phase-space data
* ``SeeBeamMoments.m`` — compute beam moments from BeamMomentsMonitor.txt
* ``ECHO_2_ASTRA.m`` — convert ECHO particle format to ASTRA format
* ``A_SeeField.m`` — extract a field snapshot along the beam trajectory
  (:func:`load_field_bin` / :func:`see_field`)

ECHO2D can output particle phase-space data in a binary format
(``particles.out``) for tracking studies.  This module provides
loading, analysis, and format conversion utilities.

Binary format (``particles.out``)
----------------------------------
* 2 doubles: Np (particle count), q0 (charge per particle [C])
* 6×Np doubles: x, y, z, px, py, pz  (coordinates and momenta)
* Np int64:    status flags (0 = active, 1 = lost)

References
----------
* ``Examples/N15_ParticleTracking/Postprocessor/AnalyseParticles.m``
* ``Examples/N15_ParticleTracking/Postprocessor/SeeBeamMoments.m``
* ``Examples/N15_ParticleTracking/Preprocessor/ECHO_2_ASTRA.m``
"""

from __future__ import annotations

import logging
import struct
from pathlib import Path
from typing import Any, cast

import numpy as np

from pyecho.errors import PostProcessError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Speed of light [m/s].
_C: float = 2.99792458e8

#: Electron rest mass [kg].
_ME: float = 9.1093837015e-31

#: Electron rest energy [eV].
_E0: float = _ME * _C ** 2 / 1.602176634e-19  # ~510998.95 eV

#: ASTRA particle record size: 13 doubles + 1 int32 = 108 bytes per particle.
_ASTRA_RECORD_BYTES: int = 108

#: ASTRA file magic bytes (first 4 bytes are int32 with the particle count).
_ASTRA_MAGIC_SIZE: int = 4


# ---------------------------------------------------------------------------
# Particle loading
# ---------------------------------------------------------------------------


def load_echo_particles(filepath: str | Path) -> dict[str, Any]:
    """Load the ECHO2D ``particles.out`` binary file.

    Replicates the reading logic in ``AnalyseParticles.m``.

    Parameters
    ----------
    filepath : str or Path
        Path to the ``particles.out`` file.

    Returns
    -------
    dict
        Keys:
        - ``Np`` (int): number of particles
        - ``q0`` (float): charge per macro-particle [C]
        - ``x, y, z`` (np.ndarray): positions [m]
        - ``px, py, pz`` (np.ndarray): canonical momenta [kg·m/s]
        - ``status`` (np.ndarray of int): particle status flags

    Raises
    ------
    PostProcessError
        If the file cannot be read or has an unexpected format.
    """
    filepath = Path(filepath)
    try:
        raw = filepath.read_bytes()
    except OSError as exc:
        raise PostProcessError(f"Cannot read {filepath}: {exc}") from exc

    if len(raw) < 16:
        raise PostProcessError(
            f"{filepath} is too small ({len(raw)} bytes) to be a valid "
            f"particles file."
        )

    # Header: Np (double), q0 (double)
    np_val = struct.unpack_from("<d", raw, 0)[0]
    q0 = struct.unpack_from("<d", raw, 8)[0]
    Np = int(np_val)

    if Np <= 0:
        raise PostProcessError(f"{filepath}: invalid particle count Np={Np}")

    expected_size = 16 + Np * 6 * 8 + Np * 8  # header + 6*Np doubles + Np int64
    if len(raw) < expected_size:
        raise PostProcessError(
            f"{filepath}: expected ≥ {expected_size} bytes for {Np} particles, "
            f"got {len(raw)}"
        )

    # Phase space: 6×Np doubles
    offset = 16
    phase = np.frombuffer(raw, dtype=np.float64, count=6 * Np, offset=offset)
    phase = phase.reshape(Np, 6, order="C")  # each row: x, y, z, px, py, pz

    # Status: Np int64
    offset += 6 * Np * 8
    status = np.frombuffer(raw, dtype=np.int64, count=Np, offset=offset)

    return {
        "Np": Np,
        "q0": q0,
        "x": phase[:, 0].copy(),
        "y": phase[:, 1].copy(),
        "z": phase[:, 2].copy(),
        "px": phase[:, 3].copy(),
        "py": phase[:, 4].copy(),
        "pz": phase[:, 5].copy(),
        "status": status.copy(),
    }


# ---------------------------------------------------------------------------
# Beam moments (SeeBeamMoments.m)
# ---------------------------------------------------------------------------


def compute_beam_moments(
    beam_monitor_file: str | Path,
    step_z: float = 0.0001,
) -> dict[str, Any]:
    """Compute beam moments from ``BeamMomentsMonitor.txt``.

    Replicates ``SeeBeamMoments.m``.

    The beam moments monitor records statistical moments of the beam
    distribution at each longitudinal step.  Typical columns include:
    z, <x>, <y>, <z>, σ_x, σ_y, σ_z, ε_x, ε_y, ε_z, etc.

    Parameters
    ----------
    beam_monitor_file : str or Path
        Path to ``BeamMomentsMonitor.txt``.
    step_z : float
        Longitudinal step size for z-coordinate reconstruction [m].

    Returns
    -------
    dict
        Keys include ``z`` (np.ndarray), ``mean_x``, ``mean_y``,
        ``mean_z``, ``sigma_x``, ``sigma_y``, ``sigma_z``,
        ``emit_x``, ``emit_y``, ``emit_z``, ``energy``, ``energy_spread``.
        Exact keys depend on the number of columns in the file.
    """
    filepath = Path(beam_monitor_file)
    try:
        data = np.loadtxt(filepath)
    except Exception as exc:
        raise PostProcessError(f"Failed to load {filepath}: {exc}") from exc

    if data.ndim == 1:
        data = data.reshape(1, -1)

    n_rows, n_cols = data.shape

    # Standard ECHO2D BeamMomentsMonitor columns (approximate):
    # 0: step index
    # 1: <z>
    # 2: σ_z
    # 3: <x>
    # 4: σ_x
    # 5: <y>
    # 6: σ_y
    # 7: ε_x (normalized emittance)
    # 8: ε_y
    # 9: ε_z
    # 10: <pz> or energy
    # 11: σ_E / E (energy spread)
    # ... (varies by ECHO2D version)

    result: dict[str, Any] = {
        "raw_data": data,
        "n_rows": n_rows,
        "n_cols": n_cols,
    }

    # Build z-coordinate (cumulative step)
    result["z"] = np.arange(n_rows, dtype=np.float64) * step_z

    # Map known columns if we have enough
    if n_cols >= 1:
        result["step"] = data[:, 0] if n_cols > 1 else np.arange(n_rows)
    if n_cols >= 2:
        result["mean_z"] = data[:, 1]
    if n_cols >= 3:
        result["sigma_z"] = data[:, 2]
    if n_cols >= 4:
        result["mean_x"] = data[:, 3]
    if n_cols >= 5:
        result["sigma_x"] = data[:, 4]
    if n_cols >= 6:
        result["mean_y"] = data[:, 5]
    if n_cols >= 7:
        result["sigma_y"] = data[:, 6]
    if n_cols >= 8:
        result["emit_x"] = data[:, 7]
    if n_cols >= 9:
        result["emit_y"] = data[:, 8]
    if n_cols >= 10:
        result["emit_z"] = data[:, 9]
    if n_cols >= 11:
        result["energy"] = data[:, 10]
    if n_cols >= 12:
        result["energy_spread"] = data[:, 11]

    return result


# ---------------------------------------------------------------------------
# ECHO → ASTRA conversion (ECHO_2_ASTRA.m)
# ---------------------------------------------------------------------------


def convert_echo_to_astra(
    echo_file: str | Path,
    astra_file: str | Path,
    total_charge: float | None = None,
    reference_energy_MeV: float = 100.0,
) -> int:
    """Convert ECHO particle format to ASTRA format.

    Replicates ``ECHO_2_ASTRA.m``.

    ASTRA binary format:
        - int32: number of particles (Np)
        - For each particle (13 doubles + 1 int32 = 108 bytes):
            x, y, z, px, py, pz  [m, eV/c]
            t, charge, status_flag, macro_charge
            + 3 spare doubles, + 1 spare int32

    ECHO → ASTRA coordinate transformations:
        - Positions: direct copy (x, y, z all in metres)
        - Momenta: px/py/pz are converted from SI [kg·m/s] to eV/c
        - Time:  t = z / c  (ultra-relativistic approximation)
        - Status: 0 → 5 (active), 1 → 1 (lost) — ASTRA convention

    Parameters
    ----------
    echo_file : str or Path
        Path to ECHO ``particles.out`` file.
    astra_file : str or Path
        Output path for ASTRA binary file (``*.astra`` or ``*.bin``).
    total_charge : float, optional
        Total bunch charge [C].  If ``None``, uses Np × q0 from the
        ECHO file.
    reference_energy_MeV : float
        Reference beam energy [MeV] for momentum normalisation.

    Returns
    -------
    int
        Number of particles written.

    Raises
    ------
    PostProcessError
        If conversion fails.
    """
    particles = load_echo_particles(echo_file)
    Np = particles["Np"]
    q0 = particles["q0"]

    if total_charge is None:
        total_charge = Np * q0

    macro_charge = total_charge / Np  # charge per macro-particle [C]

    # Reference momentum in eV/c
    E_ref_eV = reference_energy_MeV * 1e6
    p_ref_eVc = np.sqrt(E_ref_eV ** 2 - _E0 ** 2) if E_ref_eV > _E0 else E_ref_eV

    # Convert momenta from SI [kg·m/s] → eV/c
    # p[eV/c] = p[kg·m/s] * c / e
    eVc_per_SI = _C / 1.602176634e-19  # ~1.87e27

    px_eVc = particles["px"] * eVc_per_SI
    py_eVc = particles["py"] * eVc_per_SI
    pz_eVc = particles["pz"] * eVc_per_SI

    # Time-of-flight: t = z / c (ultra-relativistic)
    t = particles["z"] / _C

    # ASTRA status: 0 (active in ECHO) → 5 (active in ASTRA),
    #               1 (lost in ECHO)   → 1 (lost in ASTRA)
    status_astra = np.where(particles["status"] == 0, 5, 1).astype(np.int32)

    # Build ASTRA records
    # Each record: 13 doubles + 1 int32 = 108 bytes
    record_dtype = np.dtype([
        ("x",  "<f8"),
        ("y",  "<f8"),
        ("z",  "<f8"),
        ("px", "<f8"),
        ("py", "<f8"),
        ("pz", "<f8"),
        ("t",  "<f8"),
        ("charge", "<f8"),
        ("status", "<i4"),
        ("macro_charge", "<f8"),
        ("spare1", "<f8"),
        ("spare2", "<f8"),
        ("spare3", "<f8"),
        ("spare_int", "<i4"),
    ])

    records = np.zeros(Np, dtype=record_dtype)
    records["x"] = particles["x"]
    records["y"] = particles["y"]
    records["z"] = particles["z"]
    records["px"] = px_eVc
    records["py"] = py_eVc
    records["pz"] = pz_eVc
    records["t"] = t
    records["charge"] = q0
    records["status"] = status_astra
    records["macro_charge"] = macro_charge

    # Write ASTRA binary
    astra_file = Path(astra_file)
    astra_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(astra_file, "wb") as fh:
            # Header: int32 particle count
            fh.write(struct.pack("<i", Np))
            # Particle records
            fh.write(records.tobytes())
    except OSError as exc:
        raise PostProcessError(f"Failed to write {astra_file}: {exc}") from exc

    logger.info(
        "Converted %d particles from %s → %s (macro_charge=%.6e C)",
        Np, echo_file, astra_file, macro_charge,
    )

    return cast(int, Np)


# ---------------------------------------------------------------------------
# Beam statistics (AnalyseParticles.m)
# ---------------------------------------------------------------------------


def compute_particle_statistics(
    particles: dict[str, np.ndarray],
) -> dict[str, float]:
    """Compute beam statistics from loaded particle data.

    Replicates the analysis in ``AnalyseParticles.m``.

    Parameters
    ----------
    particles : dict
        Output of :func:`load_echo_particles`.

    Returns
    -------
    dict
        Keys: ``mean_x``, ``mean_y``, ``mean_z``, ``sigma_x``,
        ``sigma_y``, ``sigma_z``, ``mean_px``, ``mean_py``, ``mean_pz``,
        ``sigma_px``, ``sigma_py``, ``sigma_pz``, ``emit_x``,
        ``emit_y``, ``emit_z`` (all in SI units).

    Notes
    -----
    Normalised rms emittance is computed as::

        ε_x = sqrt( <x²>·<px²> − <x·px>² ) / (mₑ·c)

    where angle brackets denote the mean over active (status=0) particles.
    """
    active = particles["status"] == 0
    if not np.any(active):
        logger.warning("No active particles found; statistics will be NaN.")
        return {}

    x = particles["x"][active]
    y = particles["y"][active]
    z = particles["z"][active]
    px = particles["px"][active]
    py = particles["py"][active]
    pz = particles["pz"][active]

    def _mean_std(arr: np.ndarray) -> tuple[float, float]:
        m = float(np.mean(arr))
        s = float(np.std(arr, ddof=0))
        return m, s

    def _emit(pos: np.ndarray, mom: np.ndarray) -> float:
        """Normalised rms emittance [m·rad]."""
        pos_c = pos - np.mean(pos)
        mom_c = mom - np.mean(mom)
        ex2 = np.mean(pos_c ** 2)
        epx2 = np.mean(mom_c ** 2)
        ex_px = np.mean(pos_c * mom_c)
        emit_si = np.sqrt(max(ex2 * epx2 - ex_px ** 2, 0.0))
        return float(emit_si / (_ME * _C))

    mx, sx = _mean_std(x)
    my, sy = _mean_std(y)
    mz, sz = _mean_std(z)
    mpx, spx = _mean_std(px)
    mpy, spy = _mean_std(py)
    mpz, spz = _mean_std(pz)

    return {
        "n_active": int(np.sum(active)),
        "n_lost": int(np.sum(~active)),
        "mean_x": mx, "sigma_x": sx,
        "mean_y": my, "sigma_y": sy,
        "mean_z": mz, "sigma_z": sz,
        "mean_px": mpx, "sigma_px": spx,
        "mean_py": mpy, "sigma_py": spy,
        "mean_pz": mpz, "sigma_pz": spz,
        "emit_x": _emit(x, px),
        "emit_y": _emit(y, py),
        "emit_z": _emit(z, pz),
    }


# ---------------------------------------------------------------------------
# Field snapshot along the beam trajectory (A_SeeField.m)
# ---------------------------------------------------------------------------


def load_field_bin(filepath: str | Path) -> dict[str, Any]:
    """Load an ECHO2D raw field snapshot ``Field_XX.bin``.

    Replicates the binary reading logic in ``A_SeeField.m``.

    Binary layout (little-endian, column-major):
        * 2 × C ``long`` ints: ``nx`` (longitudinal grid points),
          ``ny`` (transverse grid points)
        * 6 × ``ny·nx`` doubles in the order Ex, Ey, Ez, Hx, Hy, Hz, each
          component stored as an ``ny × nx`` grid (row = transverse index,
          column = longitudinal index, matching MATLAB's
          ``fread(fid, [ny, nx])``).

    The C ``long`` header is 8 bytes on 64-bit platforms (Linux/macOS) and
    4 bytes on Windows; both are tried so the file loads regardless of where
    it was produced.

    Parameters
    ----------
    filepath : str or Path
        Path to the ``Field_XX.bin`` file.

    Returns
    -------
    dict
        Keys: ``nx``, ``ny`` (int), and ``Ex``, ``Ey``, ``Ez``, ``Hx``,
        ``Hy``, ``Hz`` (np.ndarray of shape ``(ny, nx)``).

    Raises
    ------
    PostProcessError
        If the file is missing, too short, or its declared grid does not
        match the file size.
    """
    filepath = Path(filepath)
    try:
        raw = filepath.read_bytes()
    except OSError as exc:
        raise PostProcessError(f"Cannot read {filepath}: {exc}") from exc

    # Try a 64-bit 'long' header first, then a 32-bit one.
    header_bytes = None
    for dt, hb in (("<qq", 16), ("<ii", 8)):
        if len(raw) < hb:
            continue
        nx, ny = struct.unpack_from(dt, raw, 0)
        nx, ny = int(nx), int(ny)
        if nx <= 0 or ny <= 0:
            continue
        comp_bytes = ny * nx * 8
        if len(raw) >= hb + 6 * comp_bytes:
            header_bytes = hb
            break

    if header_bytes is None:
        raise PostProcessError(
            f"{filepath}: cannot determine the (2×C long) grid header from "
            f"{len(raw)} bytes."
        )

    result: dict[str, Any] = {"nx": nx, "ny": ny}
    offset = header_bytes
    for name in ("Ex", "Ey", "Ez", "Hx", "Hy", "Hz"):
        comp = np.frombuffer(raw, dtype="<f8", count=ny * nx, offset=offset)
        offset += ny * nx * 8
        # MATLAB fread(fid, [ny nx]) fills column-major → order='F' reshape,
        # so result[row, col] = value at (transverse=row, longitudinal=col).
        result[name] = comp.reshape((ny, nx), order="F")

    return result


def see_field(
    field_file: str | Path,
    field_file_2: str | Path | None = None,
    component: str = "Ex",
    betaz: float = 0.997084677679532,
    transverse_index: int = 10,
) -> dict[str, Any]:
    """Extract field data along the beam trajectory from field snapshots.

    Replicates ``A_SeeField.m``.  That script loads two ``Field_XX.bin``
    snapshots (an injected field and the field after one pass), plots the
    component maps, and compares the field along the longitudinal line at a
    fixed transverse index ``i`` — the beam trajectory.  Because the
    ultra-relativistic beam moves by ``i0 = round((1 - betaz)·1000)`` grid
    cells between the snapshots, the first snapshot's line is shifted by
    ``i0`` before being overlaid with the second, aligning both to the
    co-moving beam frame.

    This function returns all the numeric data the MATLAB script plots
    (it does not import matplotlib; the caller may render them):
        * ``F1`` / ``F2``            — ``(ny, nx)`` component maps
          (MATLAB ``mesh(F1)`` / ``mesh(F2)``)
        * ``slice_1`` / ``slice_2``  — trajectory-line values
          (MATLAB ``plot(Z+i0, F1(i,:), Z, F2(i,:))``)
        * ``difference``             — ``F1 - F2`` (MATLAB ``mesh(F1-F2)``)

    Parameters
    ----------
    field_file : str or Path
        First (reference) ``Field_XX.bin`` snapshot.
    field_file_2 : str or Path, optional
        Second snapshot for comparison.  If ``None``, only the first
        snapshot is analysed.
    component : str, optional
        Field component to analyse: one of ``Ex``, ``Ey``, ``Ez``, ``Hx``,
        ``Hy``, ``Hz`` (case-insensitive).  Default ``"Ex"`` (as in the
        MATLAB script).
    betaz : float, optional
        Beam relativistic beta used for the frame shift
        ``i0 = round((1 - betaz)·1000)``.  Default matches the MATLAB value.
    transverse_index : int, optional
        1-indexed transverse row of the trajectory line (MATLAB ``i``).
        Clamped to the grid bounds.  Default 10.

    Returns
    -------
    dict
        Keys:
        - ``nx``, ``ny``: int — grid dimensions of the first snapshot
        - ``betaz``: float, ``i0``: int — frame shift in grid cells
        - ``component``: str — resolved component name (upper case)
        - ``trajectory_row``: int — 1-indexed row actually used
        - ``z_index``: np.ndarray (nx,) — ``[1 .. nx]`` (MATLAB ``Z``)
        - ``F1``: np.ndarray (ny, nx) — component map of the first snapshot
        - ``slice_1``: np.ndarray (nx,) — ``F1[row, :]``
        - ``slice_z_1``: np.ndarray (nx,) — ``z_index + i0`` (shifted)
        - ``field``: dict — full parsed first snapshot (all components)
        - If *field_file_2* is given, additionally: ``F2`` (ny2, nx2),
          ``slice_2`` (nx2,), ``slice_z_2`` (= ``z_index``, unshifted), and
          ``difference`` (``F1 - F2`` when the grids match, else ``None``).

    Raises
    ------
    PostProcessError
        If a file cannot be read, the component is unknown, or the two
        snapshots have incompatible longitudinal grids.
    """
    comp_upper = component.upper()
    _COMPONENTS = ("Ex", "Ey", "Ez", "Hx", "Hy", "Hz")
    comp = next((c for c in _COMPONENTS if c.upper() == comp_upper), None)
    if comp is None:
        raise PostProcessError(
            f"Unknown field component {component!r}; expected one of "
            "Ex, Ey, Ez, Hx, Hy, Hz."
        )

    field = load_field_bin(field_file)
    nx, ny = field["nx"], field["ny"]
    F1 = field[comp]

    i0 = int(round((1.0 - betaz) * 1000.0))

    row = int(transverse_index) - 1        # MATLAB 1-indexed → Python
    row = max(0, min(row, ny - 1))         # clamp to grid bounds
    trajectory_row = row + 1
    if trajectory_row != int(transverse_index):
        logger.warning(
            "see_field: transverse_index %d out of range [1, %d]; using %d.",
            int(transverse_index), ny, trajectory_row,
        )

    Z = np.arange(1, nx + 1, dtype=np.float64)  # MATLAB Z = [1:nx1]

    result: dict[str, Any] = {
        "nx": nx,
        "ny": ny,
        "betaz": betaz,
        "i0": i0,
        "component": comp,
        "trajectory_row": trajectory_row,
        "z_index": Z,
        "F1": F1,
        "slice_1": F1[row, :],
        "slice_z_1": Z + i0,
        "field": field,
    }

    if field_file_2 is not None:
        field2 = load_field_bin(field_file_2)
        F2 = field2[comp]
        nx2, ny2 = field2["nx"], field2["ny"]
        if nx2 != nx:
            raise PostProcessError(
                f"see_field: snapshots have different longitudinal grids "
                f"(nx={nx} vs {nx2}); cannot align trajectory lines."
            )
        row2 = max(0, min(row, ny2 - 1))
        result["F2"] = F2
        result["slice_2"] = F2[row2, :]
        result["slice_z_2"] = Z  # unshifted — MATLAB plot(Z, F2(i,:))
        if F2.shape == F1.shape:
            result["difference"] = F1 - F2
        else:
            logger.warning(
                "see_field: snapshot grids differ (%s vs %s); "
                "difference map omitted.",
                F1.shape, F2.shape,
            )
            result["difference"] = None

    return result
