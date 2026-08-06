"""Export/import ECHO2D simulation results to/from HDF5 format.

Uses h5py for efficient binary storage of large multi-dimensional arrays
(wakes, currents, fields, particles) together with structured metadata.

HDF5 Layout
-----------
::

    /input/
        parameters       -- JSON-serialised ECHO2DParams
        geometry_file    -- geometry filename (string attribute)
    /wakes/
        mode_XX/
            s            -- longitudinal coordinate [m]
            W_raw        -- raw wake potential [m·V/nC]
            W_processed  -- processed wake [V/pC] (if available)
            hr           -- transverse mesh step [m]
            offset       -- bunch offset (lines)
            D            -- structure width [m]
            sigma        -- bunch RMS length [m]
    /currents/
        Iz              -- longitudinal current profile
        Ir              -- transverse current profile
    /monitors/
        monitor_XX/
            component    -- field component label
            time_type    -- "s" or "z"
            T            -- time / s coordinates
            Z            -- longitudinal coordinates
            R            -- transverse coordinates
            F            -- field values
            D            -- structure width
    /particles/
        data             -- particle phase-space array (N×6)
    /metadata/
        timestamp         -- ISO-8601 timestamp
        executable_path   -- path to ECHO2D binary
        executable_arch   -- architecture label
        mpi_processes     -- MPI ranks
        omp_threads       -- OpenMP threads
        elapsed_seconds   -- wall-clock duration
        hostname          -- execution hostname
        pyecho_version    -- pyecho version string
        input_hash        -- SHA-256 of input file
        output_hash       -- SHA-256 of output directory
        return_code       -- process exit code
        stdout            -- captured stdout
        stderr            -- captured stderr

Usage::

    >>> from pyecho.io.hdf5 import export_hdf5, load_hdf5
    >>> export_hdf5(result, "simulation.h5")
    >>> data = load_hdf5("simulation.h5")
    >>> modes = data["wakes"]
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import numpy as np

from pyecho._version import __version__
from pyecho.errors import DependencyError, PyEchoError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def export_hdf5(
    result_or_dir: Any,
    output_path: str | Path,
    compress: int = 4,
    include_input: bool = True,
) -> Path:
    """Export simulation results to an HDF5 file.

    Parameters
    ----------
    result_or_dir : SimulationResult or str or Path
        A :class:`~pyecho.datamodel.SimulationResult` object, or a path
        to an ECHO2D output directory.  If a path is given, the results
        are first loaded with :class:`~pyecho.parser.OutputLoader` and
        :class:`~pyecho.postprocess.PostProcessor`.
    output_path : str or Path
        Destination ``.h5`` or ``.hdf5`` file path.
    compress : int
        gzip compression level (0 = none, 9 = maximum).  Default 4
        provides a good balance between speed and size.
    include_input : bool
        If ``True``, store the input parameters under ``/input/``.

    Returns
    -------
    Path
        Absolute path to the written HDF5 file.

    Raises
    ------
    DependencyError
        If the ``h5py`` library is not installed.
    PyEchoError
        If the write fails.

    Examples
    --------
    >>> export_hdf5(result, "my_result.h5")
    >>> export_hdf5("path/to/output_dir", "my_result.h5", compress=9)
    """
    try:
        import h5py
    except ImportError as exc:
        raise DependencyError(
            "h5py is required for HDF5 export. Install it with: "
            "pip install h5py",
            dependency="h5py",
            install_hint="pip install h5py",
        ) from exc

    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Resolve input: accept SimulationResult or directory path
    result = _resolve_result(result_or_dir)

    logger.info("Exporting to HDF5: %s (compress=%d)", output_path, compress)

    with h5py.File(str(output_path), "w") as f:
        # --- /input ---
        if include_input:
            grp_input = f.create_group("input")
            if result.params is not None:
                try:
                    params_json = result.params.model_dump_json(indent=2)
                except AttributeError:
                    params_json = json.dumps(
                        _serialize_params(result.params), indent=2
                    )
                grp_input.create_dataset(
                    "parameters", data=np.void(params_json.encode("utf-8"))
                )
            grp_input.attrs["geometry_file"] = result.geometry_file or ""

        # --- /wakes ---
        grp_wakes = f.create_group("wakes")
        for mode_num, mode_result in result.modes.items():
            grp_mode = grp_wakes.create_group(f"mode_{mode_num:02d}")
            if mode_result.s_raw is not None:
                grp_mode.create_dataset(
                    "s", data=mode_result.s_raw, compression="gzip",
                    compression_opts=compress,
                )
            if mode_result.W_raw is not None:
                grp_mode.create_dataset(
                    "W_raw", data=mode_result.W_raw, compression="gzip",
                    compression_opts=compress,
                )
            grp_mode.attrs["hr"] = float(mode_result.hr)
            grp_mode.attrs["offset"] = int(mode_result.offset)
            grp_mode.attrs["D"] = float(mode_result.D)
            grp_mode.attrs["sigma"] = float(mode_result.sigma)
            grp_mode.attrs["mode_number"] = int(mode_result.mode_number)

            # Processed wake
            wp = mode_result.wake_processed
            if wp is not None and wp.W is not None:
                grp_mode.create_dataset(
                    "W_processed", data=wp.W, compression="gzip",
                    compression_opts=compress,
                )
                grp_mode.attrs["loss_factor"] = float(wp.loss_factor)
                grp_mode.attrs["rms_spread"] = float(wp.rms_spread)
                grp_mode.attrs["peak"] = float(wp.peak)

        # --- /currents ---
        if result.currents_z is not None or result.currents_r is not None:
            grp_currents = f.create_group("currents")
            if result.currents_z is not None:
                grp_currents.create_dataset(
                    "Iz", data=result.currents_z, compression="gzip",
                    compression_opts=compress,
                )
            if result.currents_r is not None:
                grp_currents.create_dataset(
                    "Ir", data=result.currents_r, compression="gzip",
                    compression_opts=compress,
                )

        # --- /monitors ---
        if result.monitors:
            grp_monitors = f.create_group("monitors")
            for i, mon in enumerate(result.monitors):
                grp_mon = grp_monitors.create_group(f"monitor_{i:02d}")
                grp_mon.attrs["component"] = mon.field_component
                grp_mon.attrs["time_type"] = mon.time_type
                grp_mon.attrs["D"] = float(mon.D)
                if mon.T is not None:
                    grp_mon.create_dataset(
                        "T", data=mon.T, compression="gzip",
                        compression_opts=compress,
                    )
                if mon.Z is not None:
                    grp_mon.create_dataset(
                        "Z", data=mon.Z, compression="gzip",
                        compression_opts=compress,
                    )
                if mon.R is not None:
                    grp_mon.create_dataset(
                        "R", data=mon.R, compression="gzip",
                        compression_opts=compress,
                    )
                if mon.F is not None:
                    grp_mon.create_dataset(
                        "F", data=mon.F, compression="gzip",
                        compression_opts=compress,
                    )

        # --- /particles ---
        if result.particles is not None:
            grp_particles = f.create_group("particles")
            grp_particles.create_dataset(
                "data", data=result.particles, compression="gzip",
                compression_opts=compress,
            )

        # --- /metadata ---
        grp_meta = f.create_group("metadata")
        meta = result.metadata
        grp_meta.attrs["timestamp"] = (
            meta.timestamp.isoformat() if meta.timestamp else ""
        )
        grp_meta.attrs["executable_path"] = meta.executable_path or ""
        grp_meta.attrs["executable_arch"] = meta.executable_arch or ""
        grp_meta.attrs["mpi_processes"] = int(meta.mpi_processes)
        grp_meta.attrs["omp_threads"] = int(meta.omp_threads)
        grp_meta.attrs["elapsed_seconds"] = float(meta.elapsed_seconds)
        grp_meta.attrs["hostname"] = meta.hostname or ""
        grp_meta.attrs["pyecho_version"] = meta.pyecho_version or ""
        grp_meta.attrs["input_hash"] = meta.input_hash or ""
        grp_meta.attrs["output_hash"] = meta.output_hash or ""
        grp_meta.attrs["return_code"] = int(meta.return_code)
        if result.stdout:
            grp_meta.create_dataset(
                "stdout", data=np.void(result.stdout.encode("utf-8"))
            )
        if result.stderr:
            grp_meta.create_dataset(
                "stderr", data=np.void(result.stderr.encode("utf-8"))
            )

    logger.info("HDF5 export complete: %s", output_path)
    return output_path


def load_hdf5(filepath: str | Path) -> dict[str, Any]:
    """Load ECHO2D simulation results from an HDF5 file.

    Parameters
    ----------
    filepath : str or Path
        Path to the ``.h5`` or ``.hdf5`` file.

    Returns
    -------
    dict
        Dictionary with keys:

        - ``input`` (dict): input parameters (if present)
        - ``wakes`` (dict): mode_number → dict with s, W_raw, W_processed, …
        - ``currents`` (dict): Iz, Ir arrays
        - ``monitors`` (list[dict]): field monitor data
        - ``particles`` (np.ndarray or None): particle phase-space
        - ``metadata`` (dict): run metadata attributes
        - ``stdout`` (str): captured stdout
        - ``stderr`` (str): captured stderr

    Raises
    ------
    DependencyError
        If the ``h5py`` library is not installed.
    PyEchoError
        If the file cannot be read.
    """
    try:
        import h5py
    except ImportError as exc:
        raise DependencyError(
            "h5py is required for HDF5 import. Install it with: "
            "pip install h5py",
            dependency="h5py",
            install_hint="pip install h5py",
        ) from exc

    filepath = Path(filepath).resolve()
    if not filepath.is_file():
        raise PyEchoError(f"HDF5 file not found: {filepath}")

    logger.info("Loading HDF5: %s", filepath)

    result: dict[str, Any] = {
        "input": {},
        "wakes": {},
        "currents": {},
        "monitors": [],
        "particles": None,
        "metadata": {},
        "stdout": "",
        "stderr": "",
    }

    with h5py.File(str(filepath), "r") as f:
        # Input
        if "input" in f:
            grp = f["input"]
            if "parameters" in grp:
                data = grp["parameters"][()]
                if isinstance(data, np.void):
                    data = data.tobytes()
                result["input"]["parameters"] = data.decode("utf-8")
            result["input"]["geometry_file"] = grp.attrs.get(
                "geometry_file", ""
            )

        # Wakes
        if "wakes" in f:
            for mode_key in f["wakes"]:
                grp = f["wakes"][mode_key]
                mode_data: dict[str, Any] = {
                    "mode_number": grp.attrs.get("mode_number", -1),
                    "hr": grp.attrs.get("hr", 0.0),
                    "offset": grp.attrs.get("offset", 0),
                    "D": grp.attrs.get("D", 0.0),
                    "sigma": grp.attrs.get("sigma", 0.0),
                    "s": _safe_read(grp, "s"),
                    "W_raw": _safe_read(grp, "W_raw"),
                    "W_processed": _safe_read(grp, "W_processed"),
                    "loss_factor": grp.attrs.get("loss_factor", None),
                    "rms_spread": grp.attrs.get("rms_spread", None),
                    "peak": grp.attrs.get("peak", None),
                }
                result["wakes"][mode_key] = mode_data

        # Currents
        if "currents" in f:
            grp = f["currents"]
            result["currents"]["Iz"] = _safe_read(grp, "Iz")
            result["currents"]["Ir"] = _safe_read(grp, "Ir")

        # Monitors
        if "monitors" in f:
            for mon_key in sorted(f["monitors"].keys()):
                grp = f["monitors"][mon_key]
                mon_data: dict[str, Any] = {
                    "component": grp.attrs.get("component", ""),
                    "time_type": grp.attrs.get("time_type", ""),
                    "D": grp.attrs.get("D", 0.0),
                    "T": _safe_read(grp, "T"),
                    "Z": _safe_read(grp, "Z"),
                    "R": _safe_read(grp, "R"),
                    "F": _safe_read(grp, "F"),
                }
                result["monitors"].append(mon_data)

        # Particles
        if "particles" in f:
            grp = f["particles"]
            result["particles"] = _safe_read(grp, "data")

        # Metadata
        if "metadata" in f:
            grp = f["metadata"]
            for attr_name in grp.attrs:
                result["metadata"][attr_name] = grp.attrs[attr_name]

            # Decode stdout/stderr datasets
            for key in ("stdout", "stderr"):
                if key in grp:
                    data = grp[key][()]
                    if isinstance(data, np.void):
                        data = data.tobytes()
                    if isinstance(data, bytes):
                        result[key] = data.decode("utf-8")
                    else:
                        result[key] = str(data)

    logger.info("HDF5 load complete: %d wakes, %d monitors",
                len(result["wakes"]), len(result["monitors"]))
    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve_result(result_or_dir: Any) -> Any:
    """Resolve a SimulationResult from a result object or directory path."""
    # If it already looks like a SimulationResult, use it directly
    if hasattr(result_or_dir, "modes") and hasattr(result_or_dir, "metadata"):
        return result_or_dir

    # If it's a WakeResult, wrap it in a minimal result
    if hasattr(result_or_dir, "loss_factor") and hasattr(result_or_dir, "s"):
        from pyecho.datamodel import SimulationResult, ModeResult, RunMetadata
        wr = result_or_dir
        result: Any = SimulationResult()
        mr = ModeResult(mode_number=0, s_raw=wr.s, W_raw=wr.W,
                       hr=0.0, offset=0, D=0.0, sigma=0.0, wake_processed=wr)
        result.modes = {0: mr}
        result.metadata = RunMetadata()
        return result

    # If it's a dict (from process_wake_dipole), try to extract
    if isinstance(result_or_dir, dict):
        from pyecho.datamodel import SimulationResult, ModeResult, RunMetadata
        result = SimulationResult()
        result.modes = {}
        for key, val in result_or_dir.items():
            if hasattr(val, "loss_factor") and hasattr(val, "s"):
                result.modes[len(result.modes)] = ModeResult(
                    mode_number=len(result.modes), s_raw=val.s, W_raw=val.W,
                    hr=0.0, offset=0, D=0.0, sigma=0.0, wake_processed=val)
        result.metadata = RunMetadata()
        return result

    # Otherwise treat as directory and load
    from pyecho.parser import OutputLoader
    from pyecho.postprocess.core import PostProcessor

    _dir = Path(result_or_dir)
    loader = OutputLoader(_dir)
    pp = PostProcessor(loader)

    # Build minimal SimulationResult-like object
    class _MinimalResult:
        pass

    result = _MinimalResult()
    result.params = None
    result.geometry_file = ""
    result.output_dir = str(_dir)

    # Load modes
    modes: dict[int, Any] = {}
    try:
        all_wakes = loader.load_all_wakes()
        for mode_num, wake_data in all_wakes.items():
            # load_all_wakes() returns tuples (s, W_raw, hr, offset, D, sigma).
            s_raw, W_raw, hr, offset, D, sigma = wake_data
            result_modes: Any = _MinimalResult()
            result_modes.mode_number = mode_num
            result_modes.s_raw = s_raw
            result_modes.W_raw = W_raw
            result_modes.hr = hr
            result_modes.offset = offset
            result_modes.D = D
            result_modes.sigma = sigma
            result_modes.wake_processed = None
            modes[mode_num] = result_modes

            # Try post-processing
            try:
                if pp.geometry_type in ("round",):
                    wp = pp.process_wake_monopole()
                    result_modes.wake_processed = wp
            except Exception:
                logger.debug("Could not post-process mode %d", mode_num)
    except Exception:
        logger.debug("Could not load wakes from %s", _dir)

    result.modes = modes
    result.currents_z = None
    result.currents_r = None
    result.particles = None
    result.monitors = []
    result.stdout = ""
    result.stderr = ""

    # Minimal metadata
    class _MinimalMeta:
        pass

    meta: Any = _MinimalMeta()
    meta.timestamp = datetime.now()
    meta.executable_path = ""
    meta.executable_arch = ""
    meta.mpi_processes = 1
    meta.omp_threads = 1
    meta.elapsed_seconds = 0.0
    meta.hostname = ""
    meta.pyecho_version = __version__
    meta.input_hash = ""
    meta.output_hash = ""
    meta.return_code = 0
    result.metadata = meta

    return result


def _safe_read(grp: Any, key: str) -> np.ndarray | None:
    """Safely read a dataset, returning None if it does not exist."""
    if key in grp:
        return cast(np.ndarray, np.asarray(grp[key][()]))
    return None


def _serialize_params(params: Any) -> dict:
    """Fallback serialization for params objects without model_dump_json."""
    if hasattr(params, "model_dump"):
        return cast(dict, params.model_dump())
    if hasattr(params, "__dict__"):
        return {
            k: v for k, v in params.__dict__.items()
            if not k.startswith("_")
        }
    return {"params": str(params)}
