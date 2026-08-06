"""Output file parser for ECHO2D simulation results.

Parses all ECHO2D output file formats including wake potentials, current
profiles, coupling matrices, field monitors, particle data, and beam moments.

Output files reside in a geometry-type subdirectory (``round/``, ``magn/``,
or ``elec/``) within the simulation working directory.

Usage::

    >>> loader = OutputLoader("path/to/output_dir")
    >>> s, W, hr, offset, D, sigma = loader.load_wake(mode=0)
    >>> all_wakes = loader.load_all_wakes()
    >>> currents = loader.load_currents()
"""

from __future__ import annotations

import re
import struct
import logging
from pathlib import Path
from typing import TYPE_CHECKING, cast

import numpy as np

from pyecho.errors import ParserError

if TYPE_CHECKING:
    from pyecho.datamodel import MonitorData

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Recognised geometry-type subdirectory names.
_GEOMETRY_DIRS: tuple[str, ...] = ("round", "magn", "elec")

#: Pattern for wakeL files: ``wakeL_XX.txt`` where XX is a two-digit mode number.
#: Case-insensitive — ECHO2D may produce "WakeL_XX.txt" (manual) or
#: "wakeL_XX.txt" (macOS binary). Both are accepted.
_WAKE_FILE_PATTERN = re.compile(r"wakeL_(\d{2})\.txt$", re.IGNORECASE)


def find_wake_file(data_dir: Path, mode: int) -> Path | None:
    """Locate the ``wakeL_XX.txt`` file for *mode*, case-insensitively.

    ECHO2D output trees may name the file ``WakeL_XX.txt`` (manual) or
    ``wakeL_XX.txt`` (macOS binary).  A case-sensitive ``Path.exists()``
    would silently miss the capital-W variant, so the directory is scanned
    with the (case-insensitive) filename pattern instead.
    """
    if not data_dir.is_dir():
        return None
    stem = f"{mode:02d}"
    pattern = re.compile(rf"[Ww]akeL_{stem}\.txt")
    for p in data_dir.iterdir():
        if p.is_file() and pattern.fullmatch(p.name):
            return p
    return None


def list_wake_files(data_dir: Path) -> list[Path]:
    """List ``wakeL_XX.txt`` files case-insensitively, sorted by name."""
    if not data_dir.is_dir():
        return []
    return sorted(
        p
        for p in data_dir.iterdir()
        if p.is_file() and _WAKE_FILE_PATTERN.fullmatch(p.name)
    )

#: Pattern for WakeMonitor binary files: ``WakeM_00_XXXXXX.bin``.
_WAKE_MONITOR_PATTERN = re.compile(r"WakeM_(\d{2})_(\d{6})\.bin$", re.IGNORECASE)

#: Pattern for monitor files: ``Monitor_mXX_NYY.txt``.
_MONITOR_FILE_PATTERN = re.compile(r"Monitor_m(\d+)_N(\d+)\.txt$")

#: Header markers in monitor files.
# NOTE: "D" = total structure width [m] (= Width in input_in.txt, recta only).
# Round geometry uses the geometry file to define radius; Width is obsolete there.
_MONITOR_MARKERS: dict[str, str] = {
    "component": "field component",
    "time_type": "time coordinate",
    "D": "structure width",
    "kt": "time step count",
    "ht": "time step",
    "t0": "initial time",
    "kr": "radial grid size",
    "hr": "radial step",
    "r0": "initial radius",
    "kz": "longitudinal grid size (z-time)",
    "hz": "longitudinal step (z-time)",
    "z0": "initial z (z-time)",
    "ks": "longitudinal grid size (s-time)",
    "hs": "longitudinal step (s-time)",
    "s0": "initial s (s-time)",
}


# ---------------------------------------------------------------------------
# Public API — free functions
# ---------------------------------------------------------------------------

def parse_wake_file(filepath: str | Path) -> dict:
    """Parse a single ``wakeL_XX.txt`` file.

    Parameters
    ----------
    filepath : str or Path
        Path to the wake file.

    Returns
    -------
    dict
        Keys: ``hr``, ``offset``, ``D``, ``sigma``, ``s``, ``W_raw``,
        ``mode``.

    Raises
    ------
    ParserError
        If the file cannot be parsed.
    """
    filepath = Path(filepath)
    mode_match = _WAKE_FILE_PATTERN.search(filepath.name)
    mode = int(mode_match.group(1)) if mode_match else -1

    try:
        lines = filepath.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ParserError(f"Cannot read wake file {filepath}: {exc}") from exc

    # Line 1: hr, offset
    # Line 2: D, sigma
    # Lines 3+: s, W_raw
    data_lines: list[str] = []
    header_values: list[tuple[float, ...]] = []

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("%"):
            continue
        data_lines.append(stripped)

    # At least 2 header rows + 2 data rows: a single s-sample cannot define
    # a grid step and would crash downstream (e.g. ``s[1] - s[0]``).
    if len(data_lines) < 4:
        raise ParserError(
            f"Wake file {filepath} has fewer than 4 data lines "
            "(needs 2 header rows + at least 2 s/W data rows)."
        )

    # Parse header lines
    parts_1 = data_lines[0].split()
    if len(parts_1) < 2:
        raise ParserError(f"Line 1 of {filepath} has insufficient tokens.")
    try:
        hr = float(parts_1[0])
        offset = int(parts_1[1])
    except ValueError as exc:
        raise ParserError(
            f"Line 1 of {filepath} is malformed: expected 'hr offset', "
            f"got {parts_1!r}."
        ) from exc

    parts_2 = data_lines[1].split()
    if len(parts_2) < 2:
        raise ParserError(f"Line 2 of {filepath} has insufficient tokens.")
    try:
        D = float(parts_2[0])
        sigma = float(parts_2[1])
    except ValueError as exc:
        raise ParserError(
            f"Line 2 of {filepath} is malformed: expected 'D sigma', "
            f"got {parts_2!r}."
        ) from exc

    # Parse data lines
    s_vals: list[float] = []
    w_vals: list[float] = []
    for dl in data_lines[2:]:
        tokens = dl.split()
        if len(tokens) >= 2:
            try:
                s_vals.append(float(tokens[0]))
                w_vals.append(float(tokens[1]))
            except ValueError as exc:
                raise ParserError(
                    f"Data line of {filepath} is not numeric: {dl!r}"
                ) from exc

    if len(s_vals) < 2 or len(s_vals) != len(w_vals):
        raise ParserError(
            f"Wake file {filepath} contains fewer than 2 usable s/W data "
            f"rows ({len(s_vals)} parsed)."
        )

    return {
        "hr": hr,
        "offset": offset,
        "D": D,
        "sigma": sigma,
        "s": np.array(s_vals, dtype=np.float64),
        "W_raw": np.array(w_vals, dtype=np.float64),
        "mode": mode,
    }


def parse_wake_monitor_file(filepath: str | Path) -> dict:
    """Parse a ``WakeM_00_XXXXXX.bin`` binary WakeMonitor file.

    Format (from ECHO2D manual & WakeMonitor.m):
    - First value: n (double) = number of data points
    - Then n double values = wake potential values over time

    Parameters
    ----------
    filepath : str or Path
        Path to the binary WakeMonitor file.

    Returns
    -------
    dict
        Keys: ``n`` (int), ``wake`` (np.ndarray of shape (n,)),
        ``mode`` (int), ``index`` (int).

    Raises
    ------
    ParserError
        If the file cannot be read or is malformed.
    """
    filepath = Path(filepath)

    match = _WAKE_MONITOR_PATTERN.search(filepath.name)
    mode = int(match.group(1)) if match else -1
    index = int(match.group(2)) if match else -1

    try:
        raw = filepath.read_bytes()
    except OSError as exc:
        raise ParserError(f"Cannot read WakeMonitor file {filepath}: {exc}") from exc

    if len(raw) < 8:
        raise ParserError(
            f"WakeMonitor file {filepath} too small: {len(raw)} bytes"
        )

    # Read all doubles (little-endian, as produced by Fortran on x86/ARM)
    n = struct.unpack_from("<d", raw, 0)[0]
    try:
        n_int = int(n)
    except (ValueError, OverflowError) as exc:
        raise ParserError(
            f"WakeMonitor {filepath}: invalid point-count field {n!r}."
        ) from exc

    if n_int <= 0:
        raise ParserError(
            f"WakeMonitor {filepath}: point count n={n_int} is not positive."
        )

    expected_size = 8 + n_int * 8
    if len(raw) < expected_size:
        raise ParserError(
            f"WakeMonitor {filepath}: expected {expected_size} bytes "
            f"for n={n_int}, got {len(raw)}"
        )

    wake = np.frombuffer(raw, dtype=np.float64, count=n_int, offset=8)

    return {
        "n": n_int,
        "wake": wake,
        "mode": mode,
        "index": index,
    }


def parse_monitor_header(filepath: str | Path) -> dict:
    """Parse the header of a monitor file (``Monitor_mXX_NYY.txt``).

    Parameters
    ----------
    filepath : str or Path
        Path to the monitor file.

    Returns
    -------
    dict
        Keys include: ``field_component``, ``time_type``, ``D``, ``kt``,
        ``ht``, ``t0``, ``kr``, ``hr``, ``r0``, ``kz``/``ks``,
        ``hz``/``hs``, ``z0``/``s0``.

    Raises
    ------
    ParserError
        If the header cannot be parsed.
    """
    filepath = Path(filepath)
    try:
        text = filepath.read_text(encoding="utf-8")
    except OSError as exc:
        raise ParserError(f"Cannot read monitor file {filepath}: {exc}") from exc

    info: dict = {}

    # Extract field component from filename or first header line
    fname = filepath.stem  # e.g. Monitor_m1_N1
    comp_match = re.search(r"(E[x-z]|H[x-z])", filepath.name, re.IGNORECASE)
    if comp_match:
        info["field_component"] = comp_match.group(1)

    # Parse header lines marked with %
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("%"):
            continue
        # Remove leading % markers
        content = stripped.lstrip("%").strip()

        # Try to match known keys
        for key, label in _MONITOR_MARKERS.items():
            if label in content.lower() or key.lower() in content.lower():
                # The next line(s) should contain the numeric value
                continue

        # Try numeric extraction: many headers are like "% 0.123"
        pass

    # Fallback: read all non-% lines as data
    data_lines = [
        ln.strip() for ln in text.splitlines()
        if ln.strip() and not ln.strip().startswith("%")
    ]

    # The first few data lines often contain the header parameters in ECHO2D
    # We need to parse the specific format.
    # Actually, monitor files in ECHO2D have this structure:
    # % field component = Ex
    # % ...
    # Then data rows.
    # Let's parse more carefully.

    header_map: dict[str, str | float | int] = {}

    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("%"):
            continue
        s = s.lstrip("%").strip()

        # Try "key = value" format
        if "=" in s:
            key, _, val = s.partition("=")
            key = key.strip().lower().replace(" ", "_")
            val = val.strip()
            # Try numeric conversion
            try:
                if "." in val or "e" in val.lower():
                    header_map[key] = float(val)
                else:
                    header_map[key] = int(val)
            except ValueError:
                header_map[key] = val
        else:
            # Some headers are just "% value" — try to parse as known pattern
            pass

    # Map from parsed keys to canonical names
    key_map = {
        "field_component": "field_component",
        "time_coordinate": "time_type",
        "structure_width": "D",
        "number_of_time_steps": "kt",
        "time_step": "ht",
        "initial_time": "t0",
        "radial_grid_size": "kr",
        "radial_step": "hr",
        "initial_radius": "r0",
        "longitudinal_grid_size": "kz",
        "longitudinal_step": "hz",
        "initial_z": "z0",
        "longitudinal_grid_size_s": "ks",
        "longitudinal_step_s": "hs",
        "initial_s": "s0",
    }

    # Also look for "% kt = N, ht = X, ..." style
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("%") or "=" not in s:
            continue
        s = s.lstrip("%").strip()
        # Split on commas
        parts = [p.strip() for p in s.split(",")]
        for part in parts:
            if "=" in part:
                k, _, v = part.partition("=")
                k = k.strip().lower()
                v = v.strip()
                try:
                    if "." in v or "e" in v.lower():
                        header_map[k] = float(v)
                    else:
                        header_map[k] = int(v)
                except ValueError:
                    header_map[k] = v

    # Map to canonical names
    result: dict = {}
    for k, hval in header_map.items():
        canonical = key_map.get(k, k)
        result[canonical] = hval

    return result


# ---------------------------------------------------------------------------
# OutputLoader class
# ---------------------------------------------------------------------------

class OutputLoader:
    """Load all output files from an ECHO2D output directory.

    The output directory typically contains a geometry-type subdirectory
    (``round/``, ``magn/``, or ``elec/``) with the actual result files.

    Parameters
    ----------
    output_dir : str or Path
        Path to the directory containing ECHO2D output files (the parent
        of the ``round/``, ``magn/``, or ``elec/`` subdirectory).
    """

    def __init__(self, output_dir: str | Path) -> None:
        self.dir = Path(output_dir).resolve()
        if not self.dir.exists():
            raise ParserError(f"Output directory does not exist: {self.dir}")
        self._data_dir: Path | None = None
        self._geometry_type: str = ""
        self._auto_detect_geometry_type()

    # ------------------------------------------------------------------
    # Public methods — wake files
    # ------------------------------------------------------------------

    def load_wake(
        self, mode: int
    ) -> tuple[np.ndarray, np.ndarray, float, int, float, float]:
        """Load a single ``wakeL_XX.txt`` file.

        Parameters
        ----------
        mode : int
            Azimuthal mode number (0 = monopole, 1 = dipole, ...).

        Returns
        -------
        tuple
            ``(s, W_raw, hr, offset, D, sigma)`` where:
            - *s* — longitudinal coordinate [m]
            - *W_raw* — raw wake potential [m·V/nC]
            - *hr* — transverse mesh step [m]
            - *offset* — bunch offset in mesh lines
            - *D* — structure width [m]
            - *sigma* — bunch RMS length [m]

        Raises
        ------
        ParserError
            If the wake file is not found or cannot be parsed.
        """
        data_dir = self._resolve_data_dir()
        filepath = find_wake_file(data_dir, mode)
        if filepath is None:
            raise ParserError(
                f"Wake file not found: {data_dir / f'wakeL_{mode:02d}.txt'}"
            )

        parsed = parse_wake_file(filepath)
        return (
            parsed["s"],
            parsed["W_raw"],
            parsed["hr"],
            parsed["offset"],
            parsed["D"],
            parsed["sigma"],
        )

    def load_all_wakes(self) -> dict[int, tuple]:
        """Load all available wake files in the output directory.

        Returns
        -------
        dict[int, tuple]
            Mapping ``{mode: (s, W_raw, hr, offset, D, sigma)}``.
        """
        data_dir = self._resolve_data_dir()
        result: dict[int, tuple] = {}

        for fpath in list_wake_files(data_dir):
            match = _WAKE_FILE_PATTERN.search(fpath.name)
            if not match:
                continue
            mode = int(match.group(1))
            parsed = parse_wake_file(fpath)
            result[mode] = (
                parsed["s"],
                parsed["W_raw"],
                parsed["hr"],
                parsed["offset"],
                parsed["D"],
                parsed["sigma"],
            )

        if not result:
            logger.warning("No wakeL_*.txt files found in %s", data_dir)
        return result

    # ------------------------------------------------------------------
    # Public methods — WakeMonitor binary files
    # ------------------------------------------------------------------

    def load_wake_monitor(self, mode: int = 0, index: int = 0) -> dict | None:
        """Load a ``WakeM_XX_YYYYYY.bin`` binary WakeMonitor file.

        Parameters
        ----------
        mode : int
            Monitor mode number (XX in filename), default 0.
        index : int
            Monitor index (YYYYYY in filename), default 0.

        Returns
        -------
        dict or None
            Keys: ``n`` (int), ``wake`` (np.ndarray), ``mode``, ``index``.
            Returns ``None`` if file not found.

        Raises
        ------
        ParserError
            If the file cannot be parsed.
        """
        data_dir = self._resolve_data_dir()
        filename = f"WakeM_{mode:02d}_{index:06d}.bin"
        filepath = data_dir / filename

        if not filepath.exists():
            logger.debug("WakeMonitor file %s not found", filename)
            return None

        return parse_wake_monitor_file(filepath)

    def load_all_wake_monitors(self) -> dict[tuple[int, int], dict]:
        """Load all available WakeMonitor binary files.

        Returns
        -------
        dict[tuple[int, int], dict]
            Mapping ``{(mode, index): {n, wake, mode, index}}``.
        """
        data_dir = self._resolve_data_dir()
        result: dict[tuple[int, int], dict] = {}

        for fpath in sorted(data_dir.glob("WakeM_*.bin")):
            match = _WAKE_MONITOR_PATTERN.search(fpath.name)
            if not match:
                continue
            mode = int(match.group(1))
            index = int(match.group(2))
            parsed = parse_wake_monitor_file(fpath)
            result[(mode, index)] = parsed

        if not result:
            logger.debug("No WakeM_*.bin files found in %s", data_dir)
        return result

    # ------------------------------------------------------------------
    # Public methods — currents
    # ------------------------------------------------------------------

    def load_currents(self) -> tuple[np.ndarray, np.ndarray] | None:
        """Load ``Iz0.txt`` (longitudinal current profile).

        Returns
        -------
        tuple of (np.ndarray, np.ndarray) or None
            ``(s_array, current_2d_array)`` where *s_array* is the
            longitudinal coordinate [m] and *current_2d_array* has
            shape ``(n_s, n_radial)``. Returns ``None`` if the file
            does not exist.
        """
        data_dir = self._resolve_data_dir()
        filepath = data_dir / "Iz0.txt"
        if not filepath.exists():
            logger.debug("Iz0.txt not found in %s", data_dir)
            return None

        return _load_current_file(filepath)

    def load_currents_radial(self) -> tuple[np.ndarray, np.ndarray] | None:
        """Load ``Ir0.txt`` (radial current profile).

        Returns
        -------
        tuple or None
            Same format as :meth:`load_currents`.
        """
        data_dir = self._resolve_data_dir()
        filepath = data_dir / "Ir0.txt"
        if not filepath.exists():
            logger.debug("Ir0.txt not found in %s", data_dir)
            return None

        return _load_current_file(filepath)

    # ------------------------------------------------------------------
    # Public methods — Wcc / Wss coupling matrices
    # ------------------------------------------------------------------

    def load_wcc(self) -> np.ndarray | None:
        """Load ``Wcc_odd.txt`` (cos-cos coupling matrix).

        Returns
        -------
        np.ndarray or None
            Full matrix including the header row (D, s0, s1, ...).
            First column of data rows is the *k*-index.
        """
        data_dir = self._resolve_data_dir()
        filepath = data_dir / "Wcc_odd.txt"
        if not filepath.exists():
            logger.debug("Wcc_odd.txt not found in %s", data_dir)
            return None

        try:
            matrix = np.loadtxt(filepath)
        except Exception as exc:
            raise ParserError(f"Failed to parse {filepath}: {exc}") from exc

        return cast(np.ndarray, matrix)

    def load_wss(self) -> np.ndarray | None:
        """Load ``Wss_odd.txt`` (sin-sin coupling matrix).

        Returns
        -------
        np.ndarray or None
            Same format as :meth:`load_wcc`.
        """
        data_dir = self._resolve_data_dir()
        filepath = data_dir / "Wss_odd.txt"
        if not filepath.exists():
            logger.debug("Wss_odd.txt not found in %s", data_dir)
            return None

        try:
            matrix = np.loadtxt(filepath)
        except Exception as exc:
            raise ParserError(f"Failed to parse {filepath}: {exc}") from exc

        return cast(np.ndarray, matrix)

    # ------------------------------------------------------------------
    # Public methods — field monitors
    # ------------------------------------------------------------------

    def load_monitor(
        self, mode: int = 0, monitor_id: int = 1
    ) -> MonitorData | None:
        """Load ``Monitor_mXX_NYY.txt`` field monitor file.

        Parameters
        ----------
        mode : int
            Mode number (mXX in filename).
        monitor_id : int
            Monitor index (NYY in filename).

        Returns
        -------
        MonitorData or None
            Parsed monitor data, or ``None`` if file not found.
        """
        from pyecho.datamodel import MonitorData

        data_dir = self._resolve_data_dir()
        # ECHO2D produces zero-padded filenames: Monitor_m09_N01.txt
        # Try zero-padded first, then unpadded (for backward compatibility)
        filename = f"Monitor_m{mode:02d}_N{monitor_id:02d}.txt"
        filepath = data_dir / filename
        if not filepath.exists():
            # Fallback: unpadded format (legacy)
            filename_fb = f"Monitor_m{mode}_N{monitor_id}.txt"
            filepath_fb = data_dir / filename_fb
            if filepath_fb.exists():
                filepath = filepath_fb
            else:
                logger.debug("Monitor file %s (or %s) not found", filename, filename_fb)
                return None

        # Parse header and data
        header = _parse_monitor_full(filepath)
        data = _read_monitor_data(filepath)

        # Gracefully skip empty / coordinate-only monitor files.
        if data.shape[0] == 0:
            logger.warning(
                "Monitor file %s contains no data rows; skipping.",
                filepath.name,
            )
            return None

        n_rows = data.shape[0]

        # ---- Remap ECHO2D header keys to canonical names ----
        # Real files use: k_ct/h_ct/ct0, k_r/h_r/r0,
        #   s-type: k_z/h_z/z0   (static lab-frame window)
        #   z-type: k_s/h_s/s0   (moving co-moving window)
        # _parse_monitor_full stores them verbatim (k_ct, h_ct, etc.)
        kt  = header.get("k_ct", n_rows)
        ht  = header.get("h_ct", 1.0)
        t0  = header.get("ct0", 0.0)
        kr  = int(header.get("k_r", 1))
        hr  = header.get("h_r", 1.0)
        _r0 = header.get("r0", 0.0)

        # Validate the time axis against the actual number of data rows so a
        # mismatched header cannot silently truncate or mis-shape the grid.
        if kt != n_rows:
            logger.warning(
                "Monitor %s: header k_ct=%d does not match %d data rows; "
                "using %d time steps.",
                filepath.name, kt, n_rows, n_rows,
            )
            kt = n_rows

        if kr <= 0:
            logger.warning(
                "Monitor %s: invalid k_r=%d; using 1.", filepath.name, kr,
            )
            kr = 1

        # Determine time_type: s-type has k_z; z-type has k_s
        has_kz = "k_z" in header
        has_ks = "k_s" in header
        if has_kz and not has_ks:
            time_type = "s"
        elif has_ks and not has_kz:
            time_type = "z"
        elif "time_type" in header:
            time_type = header["time_type"]
        else:
            # Fallback: first header line "time=z" or "time=s"
            time_type = "z"

        # ---- Build coordinate arrays ----
        T = np.arange(kt, dtype=np.float64) * ht + t0
        R = np.arange(kr, dtype=np.float64) * hr + _r0

        # Strip the leading per-row coordinate column (ct for s-type,
        # window z-position for z-type), then reshape field grid
        mesh_pos = data[:, 0].copy()   # per-row coordinate
        F_flat = data[:, 1:]            # field values only

        # A coordinate-only file (no field columns) is not usable.
        if F_flat.shape[1] == 0:
            logger.warning(
                "Monitor file %s has no field columns (only per-row "
                "coordinates); skipping.", filepath.name,
            )
            return None

        def _reshape_field(grid_flat: np.ndarray, nz: int, label: str) -> np.ndarray:
            """Reshape (kt, nz*kr) → (kt, nz, kr), falling back to the
            flat grid with a warning when the header predicts a size that
            does not match the file.
            """
            if grid_flat.shape[1] == nz * kr:
                try:
                    return grid_flat.reshape(kt, nz, kr)
                except ValueError as exc:
                    raise ParserError(
                        f"Monitor {filepath.name}: field grid {grid_flat.shape} "
                        f"cannot be reshaped to ({kt}, {nz}, {kr}); header "
                        f"{label} dimension inconsistent with data rows."
                    ) from exc
            logger.warning(
                "Monitor %s: header predicts %d field columns "
                "(%s=%d × k_r=%d) but file has %d; returning flat grid.",
                filepath.name, nz * kr, label, nz, kr, grid_flat.shape[1],
            )
            return grid_flat

        if time_type == "s":
            # s-type: static lab-frame z-grid [z0, z1] with k_z points
            kz = int(header.get("k_z", 1))
            hz = header.get("h_z", 1.0)
            _z0 = header.get("z0", 0.0)
            if kz <= 0:
                logger.warning(
                    "Monitor %s: invalid k_z=%d; using 1.", filepath.name, kz,
                )
                kz = 1
            Z = np.arange(kz, dtype=np.float64) * hz + _z0
            F = _reshape_field(F_flat, kz, "k_z")
        else:
            # z-type: moving co-moving s-grid [s0, s1] with k_s points
            ks = int(header.get("k_s", 1))
            hs = header.get("h_s", 1.0)
            _s0 = header.get("s0", 0.0)
            if ks <= 0:
                logger.warning(
                    "Monitor %s: invalid k_s=%d; using 1.", filepath.name, ks,
                )
                ks = 1
            S = np.arange(ks, dtype=np.float64) * hs + _s0
            Z = -S  # MATLAB convention: Z = -S for z-time
            F = _reshape_field(F_flat, ks, "k_s")
            # Store mesh_pos for lab-frame reconstruction:
            # z_lab = mesh_pos[i] + Z  (MATLAB: MeshPos + Z)

        # Store mesh_pos as an attribute for downstream z-time reconstruction
        component = header.get("field_component", "Ez")
        D_val = header.get("D", header.get("width", 1.0))

        monitor = MonitorData(
            monitor_id=monitor_id,
            field_component=component,
            time_type=time_type,
            T=T,
            Z=Z,
            R=R,
            F=F,
            D=D_val,
        )
        # Attach per-row mesh position for z-time lab-frame reconstruction
        monitor._mesh_pos = mesh_pos  # type: ignore[attr-defined]
        return monitor

    def list_monitors(self) -> list[tuple[int, int]]:
        """List available monitor files.

        Returns
        -------
        list[tuple[int, int]]
            List of ``(mode, monitor_id)`` tuples.
        """
        data_dir = self._resolve_data_dir()
        monitors: list[tuple[int, int]] = []
        for fpath in sorted(data_dir.glob("Monitor_m*.txt")):
            match = _MONITOR_FILE_PATTERN.search(fpath.name)
            if match:
                monitors.append((int(match.group(1)), int(match.group(2))))
        return monitors

    # ------------------------------------------------------------------
    # Public methods — particles
    # ------------------------------------------------------------------

    def load_particles(self) -> np.ndarray | None:
        """Load ``particles.out`` binary particle file.

        Binary format (Fortran unformatted / raw):
        - First 2 doubles: Np (number of particles), q0 (charge)
        - Next 6*Np doubles: x, y, z, px, py, pz
        - Next Np 64-bit integers: status flags

        Returns
        -------
        np.ndarray or None
            Structured array with fields ``x, y, z, px, py, pz, status``,
            or ``None`` if file not found.
        """
        data_dir = self._resolve_data_dir()
        filepath = data_dir / "particles.out"
        if not filepath.exists():
            logger.debug("particles.out not found in %s", data_dir)
            return None

        try:
            raw = filepath.read_bytes()
        except OSError as exc:
            raise ParserError(f"Cannot read {filepath}: {exc}") from exc

        # Parse first two doubles
        if len(raw) < 16:
            raise ParserError(f"particles.out is too small: {len(raw)} bytes")

        np_val = struct.unpack_from("<d", raw, 0)[0]
        q0 = struct.unpack_from("<d", raw, 8)[0]
        Np = int(np_val)

        if Np <= 0:
            logger.warning("particles.out reports Np=%d", Np)
            return None

        expected_size = 16 + 6 * Np * 8 + Np * 8
        if len(raw) < expected_size:
            raise ParserError(
                f"particles.out size {len(raw)} < expected {expected_size} "
                f"for Np={Np}"
            )

        offset = 16
        coords = np.frombuffer(raw, dtype=np.float64, count=6 * Np, offset=offset)
        coords = coords.reshape(Np, 6)  # x, y, z, px, py, pz

        offset += 6 * Np * 8
        status = np.frombuffer(raw, dtype=np.int64, count=Np, offset=offset)

        # Build structured array
        dtype = np.dtype([
            ("x", np.float64),
            ("y", np.float64),
            ("z", np.float64),
            ("px", np.float64),
            ("py", np.float64),
            ("pz", np.float64),
            ("status", np.int64),
        ])
        result: np.ndarray = np.empty(Np, dtype=dtype)
        result["x"] = coords[:, 0]
        result["y"] = coords[:, 1]
        result["z"] = coords[:, 2]
        result["px"] = coords[:, 3]
        result["py"] = coords[:, 4]
        result["pz"] = coords[:, 5]
        result["status"] = status

        return result

    # ------------------------------------------------------------------
    # Public methods — beam moments
    # ------------------------------------------------------------------

    def load_beam_moments(self) -> np.ndarray | None:
        """Load ``BeamMomentsMonitor.txt``.

        Returns
        -------
        np.ndarray or None
            2-D array of beam moments (time × moments), or ``None`` if
            file not found.
        """
        data_dir = self._resolve_data_dir()
        filepath = data_dir / "BeamMomentsMonitor.txt"
        if not filepath.exists():
            logger.debug("BeamMomentsMonitor.txt not found in %s", data_dir)
            return None

        try:
            data = np.loadtxt(filepath)
        except Exception as exc:
            raise ParserError(f"Failed to parse {filepath}: {exc}") from exc

        return cast(np.ndarray, data)

    # ------------------------------------------------------------------
    # Public methods — status
    # ------------------------------------------------------------------

    def has_output(self) -> bool:
        """Check if the output directory contains any result files.

        Returns
        -------
        bool
            ``True`` if any known output files exist.
        """
        data_dir = self._resolve_data_dir()
        if data_dir is None:
            return False
        patterns = [
            "wakeL_*.txt",
            "Iz0.txt",
            "Wcc_odd.txt",
            "Wss_odd.txt",
            "Monitor_m*.txt",
            "particles.out",
            "BeamMomentsMonitor.txt",
        ]
        for pat in patterns:
            if list(data_dir.glob(pat)):
                return True
        return False

    @property
    def geometry_type(self) -> str:
        """Detected geometry subdirectory type."""
        return self._geometry_type

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _auto_detect_geometry_type(self) -> None:
        """Find and set the geometry-type data subdirectory."""
        # First check if there's a direct subdirectory with exact name
        for gtype in _GEOMETRY_DIRS:
            candidate = self.dir / gtype
            if candidate.is_dir():
                self._data_dir = candidate
                self._geometry_type = gtype
                logger.debug("Detected geometry type: %s", gtype)
                return

        # Also check if self.dir itself IS the data directory
        # (i.e., it contains wakeL files directly)
        if list_wake_files(self.dir):
            self._data_dir = self.dir
            # Try to infer from parent name (prefix match)
            parent_name = self.dir.name.lower()
            for gtype in _GEOMETRY_DIRS:
                if parent_name == gtype or parent_name.startswith(gtype):
                    self._geometry_type = gtype
                    break
            else:
                self._geometry_type = "unknown"
            return

        # Search one level deep (check subdirectories with prefix match)
        for child in sorted(self.dir.iterdir()):
            if not child.is_dir():
                continue
            child_name = child.name.lower()
            # Check exact match first, then prefix match
            for gtype in _GEOMETRY_DIRS:
                if child_name == gtype or child_name.startswith(gtype):
                    # Verify it contains wake files
                    if list_wake_files(child):
                        self._data_dir = child
                        self._geometry_type = gtype
                        logger.debug(
                            "Detected geometry type: %s (from %s)",
                            gtype, child.name,
                        )
                        return

        # If nothing found, assume data is directly in self.dir
        self._data_dir = self.dir
        self._geometry_type = "unknown"
        logger.warning(
            "Could not auto-detect geometry type in %s; "
            "assuming data files are directly in the directory.",
            self.dir,
        )

    def _resolve_data_dir(self) -> Path:
        """Return the resolved data directory, auto-detecting if necessary.

        Returns
        -------
        Path
        """
        if self._data_dir is None:
            self._auto_detect_geometry_type()
        assert self._data_dir is not None
        return self._data_dir


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_current_file(filepath: Path) -> tuple[np.ndarray, np.ndarray]:
    """Load a current-profile file (``Iz0.txt`` / ``Ir0.txt``).

    Parameters
    ----------
    filepath : Path
        Path to the current-profile file.

    Returns
    -------
    tuple of (np.ndarray, np.ndarray)
        ``(s_array, current_2d)`` where *s_array* is the longitudinal
        coordinate and *current_2d* holds the remaining columns.

    Raises
    ------
    ParserError
        If the file is unreadable, empty, or malformed.
    """
    try:
        data = np.loadtxt(filepath)
    except Exception as exc:
        raise ParserError(f"Failed to parse {filepath}: {exc}") from exc

    # Normalise scalar / 1-D input to a 2-D column array so that
    # column indexing below is always safe.
    if data.ndim == 0:
        data = data.reshape(1, 1)
    elif data.ndim == 1:
        data = data.reshape(-1, 1)

    if data.shape[0] == 0 or data.shape[1] == 0:
        raise ParserError(
            f"Current file {filepath} contains no usable data rows "
            f"(shape {data.shape})."
        )

    s_array = data[:, 0]
    current_2d = data[:, 1:]
    return s_array, current_2d


def _parse_monitor_full(filepath: Path) -> dict:
    """Parse the complete header of a monitor file.

    Parameters
    ----------
    filepath : Path
        Path to the monitor file.

    Returns
    -------
    dict
        Parsed header key-value pairs.
    """
    try:
        text = filepath.read_text(encoding="utf-8")
    except OSError as exc:
        raise ParserError(f"Cannot read {filepath}: {exc}") from exc

    header: dict = {}
    data_started = False

    for line in text.splitlines():
        s = line.strip()

        # Skip empty lines
        if not s:
            continue

        # Header lines start with %
        if s.startswith("%"):
            s_clean = s.lstrip("%").strip().lower()

            # Detect field component (including Ep = E_phi for round geometry)
            for comp in ("ep", "ex", "ey", "ez", "hx", "hy", "hz"):
                if comp in s_clean:
                    if comp == "ep":
                        header["field_component"] = "Ep"
                    else:
                        header["field_component"] = comp.capitalize()
                    break

            # Detect time type
            if "z-time" in s_clean or "z time" in s_clean:
                header["time_type"] = "z"
            elif "s-time" in s_clean or "s time" in s_clean:
                header["time_type"] = "s"

            # Parse key=value or key = value pairs
            # Real ECHO2D headers use SPACE-separated pairs:
            #   % k_ct=81 h_ct=1.000000e-03 ct0=2.100000e-02
            # Also support comma-separated (legacy manual format)
            if "=" in s_clean:
                # Split on spaces OR commas to handle both formats
                parts = []
                for segment in s_clean.split(","):
                    parts.extend(segment.strip().split())
                for part in parts:
                    if "=" in part:
                        k, _, v = part.partition("=")
                        k = k.strip()
                        v = v.strip()
                        if not k:
                            continue
                        try:
                            if "." in v or "e" in v.lower():
                                header[k] = float(v)
                            else:
                                header[k] = int(v)
                        except ValueError:
                            header[k] = v
            continue

        # Non-header, non-empty line — data has started
        if not data_started:
            data_started = True

    # Also parse from filename
    fname = filepath.stem
    for comp in ("Ep", "Ex", "Ey", "Ez", "Hx", "Hy", "Hz"):
        if f"_{comp}" in fname or f"_{comp.lower()}" in fname:
            header.setdefault("field_component", comp)
            break

    return header


def _read_monitor_data(filepath: Path) -> np.ndarray:
    """Read the numeric data portion of a monitor file.

    Skips header lines (starting with ``%``) and returns the numeric
    data as a 2-D array.

    Parameters
    ----------
    filepath : Path
        Path to the monitor file.

    Returns
    -------
    np.ndarray
    """
    try:
        data = np.loadtxt(filepath, comments="%")
    except Exception as exc:
        raise ParserError(f"Failed to parse monitor data {filepath}: {exc}") from exc

    # Normalise scalar / 1-D input to a 2-D array so column indexing is safe.
    if data.ndim == 0:
        data = data.reshape(1, 1)
    elif data.ndim == 1:
        data = data.reshape(-1, 1)

    return cast(np.ndarray, data)


# ---------------------------------------------------------------------------
# Bunch profile loading (from Iz0.txt)
# ---------------------------------------------------------------------------

def load_bunch_profile(
    output_dir: str | Path,
    offset: int,
    s_wake: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray] | tuple[None, None]:
    """Load the bunch current profile from Iz0.txt.

    Replicates the MATLAB convention::

        Iz = load('Iz0.txt');
        bunch(:,1) = Iz(:,1);               % s coordinate
        bunch(:,2) = Iz(:,offset+3) * 1e9;  % current in A, scaled to V/pC
        B = interp1(bunch(:,1), bunch(:,2), s, 'linear', 0);

    Parameters
    ----------
    output_dir : str or Path
        Directory containing ``Iz0.txt`` (e.g. ``magn/`` or ``elec/``).
    offset : int
        Bunch offset in mesh lines (from the wakeL file header).
    s_wake : np.ndarray, optional
        Wake *s*-grid to interpolate onto.  If ``None``, returns the
        raw ``(s, I)`` from the file.

    Returns
    -------
    s : np.ndarray or None
        *s*-coordinate [m] (same grid as the raw file or interpolated).
    I : np.ndarray or None
        Bunch current profile, or ``None`` if ``Iz0.txt`` is not found.
    """
    import logging
    _log = logging.getLogger(__name__)

    iz_path = Path(output_dir) / "Iz0.txt"
    if not iz_path.exists():
        _log.debug("Iz0.txt not found in %s", output_dir)
        return None, None

    try:
        iz = np.loadtxt(iz_path)
    except Exception as exc:
        raise ParserError(f"Failed to parse {iz_path}: {exc}") from exc

    # Empty or scalar (single-value) files are not usable as profiles.
    if iz.ndim == 0 or iz.size == 0:
        _log.warning("Iz0.txt is empty or malformed in %s", output_dir)
        return None, None

    s_raw = iz[:, 0]
    # MATLAB: Iz(:, offset+3)  →  0-indexed: iz[:, offset+2]
    col = offset + 2
    if col >= iz.shape[1] or col < 0:
        _log.warning(
            "Iz0.txt has %d columns but offset=%d requires column %d; "
            "clamping to a valid column.", iz.shape[1], offset, col,
        )
        col = min(max(col, 0), iz.shape[1] - 1)
    I_raw = iz[:, col] * 1e9  # A → nA → ???  Actually MATLAB uses ×1e9

    if s_wake is not None:
        # Interpolate onto the wake s-grid
        I = np.interp(s_wake, s_raw, I_raw, left=0.0, right=0.0)
        return s_wake, I
    return s_raw, I_raw
