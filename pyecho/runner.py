"""ECHO2D executable runner with progress tracking.

Provides :class:`ECHO2DRunner` for single simulations and
:class:`BatchRunner` for parameter sweeps.  Handles platform-specific
executable detection, input-file generation, process management,
progress parsing, and result aggregation.

Usage::

    >>> from pyecho.runner import ECHO2DRunner
    >>> runner = ECHO2DRunner("work_dir")
    >>> result = runner.run(params, np=4)
    >>> print(result.modes[0].wake_processed.loss_factor)
"""

from __future__ import annotations

import logging
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Generator

from pyecho.config import ECHO2DParams, save_params
from pyecho.datamodel import (
    ModeResult,
    RunMetadata,
    SimulationResult,
)
from pyecho.errors import (
    ExecutableNotFoundError,
    RunnerError,
    SimulationCrashedError,
    SimulationTimeoutError,
)
from pyecho.parser import OutputLoader

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Progress percentage pattern in ECHO2D stdout.
#  Matches lines like "Mode 0: 42%" or "progress: 75%".
_PROGRESS_PATTERN = re.compile(
    r"(?:Mode\s+\d+\s*:\s*)?(\d+(?:\.\d+)?)\s*%", re.IGNORECASE
)

#: Platform → executable search paths (relative to project root).
_PLATFORM_EXECUTABLE_MAP: dict[str, str] = {
    "Darwin_arm64": "ECHO2D_v3_5/Codes/MacOS_ARM_OpenMP/ECHO2D",
    "Darwin_x86_64": "ECHO2D_v3_5/Codes/MacOS_ARM_OpenMP/ECHO2D",
    "Linux_arm64": "ECHO2D_v3_5/Codes/Linux_ARM_OpenMP/ECHO2D",
    "Linux_x86_64": "ECHO2D_v3_5/Codes/Linux_MaxwellCluster_MPI/ECHO2D",
    "Windows_arm64": "ECHO2D_v3_5/Codes/Windows_ARM_OpenMP/ECHO2D",
    "Windows_x86_64": "ECHO2D_v3_5/Codes/Windows_Intel_OpenMP/ECHO2D",
}


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _get_platform_key() -> str:
    """Return a platform-architecture key for executable lookup."""
    system = platform.system()
    machine = platform.machine().lower()
    arch = "x86_64" if machine in ("x86_64", "amd64") else "arm64"
    return f"{system}_{arch}"


# ---------------------------------------------------------------------------
# ECHO2DRunner
# ---------------------------------------------------------------------------

class ECHO2DRunner:
    """Run the ECHO2D executable and capture simulation results.

    Parameters
    ----------
    work_dir : str or Path
        Working directory for the simulation.  Must contain (or will
        receive) an ``input_in.txt`` and geometry file.
    executable : str, optional
        Path to the ECHO2D binary.  If ``None``, auto-detected from
        the project's ``Codes/`` directory.

    Notes
    -----
    - **MPI support** is not yet implemented; the runner currently only
      sets ``OMP_NUM_THREADS`` for OpenMP parallelism.  MPI-based
      executables (e.g. ``MacOS_ARM_MPI``) can be selected via the
      *executable* parameter but will run single-process.  Full MPI
      support (``mpirun -np N``) is planned for a future release.
    - **Geometry file auto-copy**: when *params* is provided, the
      geometry file referenced by ``params.GeometryFile`` is
      automatically copied into *work_dir* if it resides elsewhere.
      This ensures ECHO2D can find the file regardless of where the
      input was generated.
    """

    def __init__(
        self,
        work_dir: str | Path,
        executable: str | None = None,
    ) -> None:
        self.work_dir = Path(work_dir).resolve()
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self._executable_path: str | None = None
        self._current_process: subprocess.Popen | None = None  # For cancellation

        if executable:
            self.executable = executable
        else:
            self.executable = self._auto_detect()

    def kill(self) -> None:
        """Kill the currently running ECHO2D subprocess, if any."""
        if self._current_process is not None:
            try:
                self._current_process.kill()
                self._current_process.wait(timeout=5)
            except Exception:
                pass
            self._current_process = None

    @property
    def executable(self) -> str:
        """Path to the ECHO2D binary."""
        if self._executable_path is None:
            self._executable_path = self._auto_detect()
        return self._executable_path

    @executable.setter
    def executable(self, value: str) -> None:
        path = Path(value)
        if not path.is_file():
            # Try resolving from project root
            project_root = self._find_project_root()
            candidate = project_root / value
            if candidate.is_file():
                path = candidate
            else:
                raise ExecutableNotFoundError(
                    f"ECHO2D executable not found: {value}"
                )
        self._executable_path = str(path.resolve())

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def _ensure_geometry_in_work_dir(
        self, params: ECHO2DParams
    ) -> ECHO2DParams:
        """Copy the geometry file into *work_dir* if it resides elsewhere.

        If ``params.GeometryFile`` points to an external file (absolute
        path or relative path outside *work_dir*), the file is copied
        into *work_dir* and ``params.GeometryFile`` is updated to the
        bare filename.  This matches the behaviour of
        :func:`pyecho.api.quick_simulate` and ensures ECHO2D can find
        the geometry file regardless of where the input was generated.

        Parameters
        ----------
        params : ECHO2DParams
            Simulation parameters (may be mutated in-place).

        Returns
        -------
        ECHOO2DParams
            The (possibly updated) params object.
        """
        geom_name = params.GeometryFile
        # Skip special markers like '-' (no geometry file)
        if not geom_name or geom_name == "-":
            return params

        geom_path = Path(geom_name)
        # Already a bare filename with no directory component → assume it
        # will be provided in work_dir; nothing to do.
        if geom_path.parent == Path("."):
            # But check if it actually exists somewhere reachable
            if not (self.work_dir / geom_path.name).exists():
                logger.debug(
                    "Geometry file '%s' not found in work_dir; "
                    "ECHO2D will look for it at runtime.",
                    geom_path.name,
                )
            return params

        # Resolve the source path
        if geom_path.is_absolute():
            source = geom_path
        else:
            # Relative path — resolve from CWD (where the user launched)
            source = Path.cwd() / geom_path

        if not source.is_file():
            logger.warning(
                "Geometry file '%s' not found at %s; skipping copy.",
                geom_name, source,
            )
            return params

        dest = self.work_dir / source.name
        if dest.resolve() == source.resolve():
            return params  # already in work_dir

        logger.info("Copying geometry file %s → %s", source, dest)
        shutil.copy2(source, dest)
        params.GeometryFile = source.name
        return params

    def run(
        self,
        params: ECHO2DParams | None = None,
        geometry_file: str | None = None,
        np: int = 1,
        timeout: int | None = None,
        show_progress: bool = True,
    ) -> SimulationResult:
        """Run an ECHO2D simulation.

        Parameters
        ----------
        params : ECHO2DParams, optional
            Simulation parameters.  If provided, an ``input_in.txt`` is
            written to *work_dir* before execution.
        geometry_file : str, optional
            Path to the geometry file.  If provided and *params* is
            given, it overrides ``params.GeometryFile``.  If *params*
            is ``None``, the existing ``input_in.txt`` in *work_dir* is
            used.
        np : int
            Number of OpenMP threads (sets ``OMP_NUM_THREADS``).
            (Note: parameter named ``np`` for historical reasons;
            the CLI exposes this as ``--threads`` / ``-j``.)
        timeout : int, optional
            Maximum wall-clock time in seconds.  ``None`` means no
            timeout.
        show_progress : bool
            If ``True``, log progress percentage parsed from stdout.

        Returns
        -------
        SimulationResult
            Complete simulation result with parsed output data.

        Raises
        ------
        SimulationTimeoutError
            If the simulation exceeds *timeout*.
        SimulationCrashedError
            If ECHO2D returns a non-zero exit code.
        """
        t_start = time.monotonic()

        # 1. Write input file if params provided
        if params is not None:
            if geometry_file:
                params = params.model_copy(update={"GeometryFile": geometry_file})
            params = self._ensure_geometry_in_work_dir(params)
            save_params(params, self.work_dir / "input_in.txt")

        # 2. Build environment
        env = os.environ.copy()
        env["OMP_NUM_THREADS"] = str(np)

        # 3. Launch process
        logger.info(
            "Running ECHO2D: %s in %s (OMP_NUM_THREADS=%d)",
            self.executable,
            self.work_dir,
            np,
        )

        try:
            self._current_process = subprocess.Popen(
                [self.executable],
                cwd=str(self.work_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                bufsize=1,
            )
        except FileNotFoundError as exc:
            raise ExecutableNotFoundError(
                f"ECHO2D executable not found: {self.executable}"
            ) from exc
        process = self._current_process

        # 4. Read stdout with progress tracking
        stdout_lines: list[str] = []
        stderr_lines: list[str] = []
        last_progress = -1

        try:
            assert process.stdout is not None
            for line in process.stdout:
                line = line.rstrip("\n")
                stdout_lines.append(line)

                if show_progress:
                    match = _PROGRESS_PATTERN.search(line)
                    if match:
                        pct = float(match.group(1))
                        if int(pct) != last_progress:
                            logger.info("Progress: %.0f%%", pct)
                            last_progress = int(pct)

            # Wait with timeout
            return_code = process.wait(timeout=timeout)

            # Collect stderr
            assert process.stderr is not None
            stderr_lines = process.stderr.read().splitlines()

        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            raise SimulationTimeoutError(
                f"ECHO2D timed out after {timeout} s"
            )

        elapsed = time.monotonic() - t_start

        # 5. Check return code
        if return_code != 0:
            stderr_text = "\n".join(stderr_lines[-50:])
            raise SimulationCrashedError(
                f"ECHO2D exited with code {return_code}\n{stderr_text}"
            )

        logger.info("ECHO2D finished in %.1f s", elapsed)

        # 6. Load results
        return self._build_result(
            params=params,
            stdout="\n".join(stdout_lines),
            stderr="\n".join(stderr_lines),
            elapsed=elapsed,
            return_code=return_code,
        )

    def run_stream(
        self,
        params: ECHO2DParams | None = None,
        geometry_file: str | None = None,
        np: int = 1,
        timeout: int | None = None,
    ) -> Generator[dict[str, Any], None, SimulationResult]:
        """Run ECHO2D and yield progress updates.

        Yields
        ------
        dict
            Progress dict with keys ``percent`` (float) and ``message`` (str).

        Returns
        -------
        SimulationResult
            Final result after completion.

        Notes
        -----
        This method is a generator that also returns a value (Python ≥ 3.3).
        The return value is accessible via ``StopIteration.value``::

            gen = runner.run_stream(params)
            for update in gen:
                print(f"{update['percent']:.1f}%")
            # After exhaustion:
            # result = gen.return_value  # or via StopIteration

        """
        t_start = time.monotonic()

        if params is not None:
            if geometry_file:
                params = params.model_copy(update={"GeometryFile": geometry_file})
            params = self._ensure_geometry_in_work_dir(params)
            save_params(params, self.work_dir / "input_in.txt")

        env = os.environ.copy()
        env["OMP_NUM_THREADS"] = str(np)

        logger.info("Running ECHO2D (stream): %s", self.executable)

        try:
            process = subprocess.Popen(
                [self.executable],
                cwd=str(self.work_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                bufsize=1,
            )
        except FileNotFoundError as exc:
            raise ExecutableNotFoundError(
                f"ECHO2D executable not found: {self.executable}"
            ) from exc

        stdout_lines: list[str] = []
        stderr_lines: list[str] = []

        try:
            assert process.stdout is not None
            for line in process.stdout:
                line = line.rstrip("\n")
                stdout_lines.append(line)

                match = _PROGRESS_PATTERN.search(line)
                if match:
                    yield {
                        "percent": float(match.group(1)),
                        "message": line.strip(),
                    }

            return_code = process.wait(timeout=timeout)
            assert process.stderr is not None
            stderr_lines = process.stderr.read().splitlines()

        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            raise SimulationTimeoutError(
                f"ECHO2D timed out after {timeout} s"
            )

        elapsed = time.monotonic() - t_start

        if return_code != 0:
            stderr_text = "\n".join(stderr_lines[-50:])
            raise SimulationCrashedError(
                f"ECHO2D exited with code {return_code}\n{stderr_text}"
            )

        return self._build_result(
            params=params,
            stdout="\n".join(stdout_lines),
            stderr="\n".join(stderr_lines),
            elapsed=elapsed,
            return_code=return_code,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _auto_detect(self) -> str:
        """Auto-detect the ECHO2D executable for the current platform.

        Returns
        -------
        str
            Absolute path to the ECHO2D binary.

        Raises
        ------
        ExecutableNotFoundError
            If no executable can be found.
        """
        project_root = self._find_project_root()
        platform_key = _get_platform_key()
        relative = _PLATFORM_EXECUTABLE_MAP.get(platform_key)

        if relative:
            candidate = project_root / relative
            if candidate.is_file():
                logger.debug("Auto-detected executable: %s", candidate)
                return str(candidate.resolve())

        # Fallback: search Codes/ directory
        codes_dir = project_root / "ECHO2D_v3_5" / "Codes"
        if codes_dir.is_dir():
            for child in codes_dir.iterdir():
                if child.is_dir():
                    exe = child / "ECHO2D"
                    if exe.is_file():
                        logger.debug("Found executable: %s", exe)
                        return str(exe.resolve())
                    # Check for .exe on Windows
                    exe_win = child / "ECHO2D.exe"
                    if exe_win.is_file():
                        logger.debug("Found executable: %s", exe_win)
                        return str(exe_win.resolve())

        # Last resort: check PATH
        which = shutil.which("ECHO2D") or shutil.which("echo2d")
        if which:
            logger.debug("Found ECHO2D in PATH: %s", which)
            return which

        raise ExecutableNotFoundError(
            "Cannot auto-detect ECHO2D executable. "
            "Please specify the path explicitly."
        )

    def _find_project_root(self) -> Path:
        """Find the project root (containing ECHO2D_v3_5/).

        Returns
        -------
        Path
        """
        # Start from this file's location and walk up
        current = Path(__file__).resolve().parent.parent
        for _ in range(6):
            if (current / "ECHO2D_v3_5").is_dir():
                return current
            if (current / "pyproject.toml").is_file():
                return current
            parent = current.parent
            if parent == current:
                break
            current = parent
        return Path.cwd()

    def _build_result(
        self,
        params: ECHO2DParams | None,
        stdout: str,
        stderr: str,
        elapsed: float,
        return_code: int,
    ) -> SimulationResult:
        """Build a SimulationResult from the output directory."""
        import socket

        # Try to load params from work_dir if not provided
        if params is None:
            input_file = self.work_dir / "input_in.txt"
            if input_file.exists():
                from pyecho.config import load_params
                try:
                    params = load_params(input_file)
                except Exception:
                    params = None

        # Load output files
        loader = OutputLoader(self.work_dir)
        modes: dict[int, ModeResult] = {}

        all_wakes = loader.load_all_wakes()
        for mode_num, (s, W, hr, offset, D, sigma) in all_wakes.items():
            modes[mode_num] = ModeResult(
                mode_number=mode_num,
                s_raw=s,
                W_raw=W,
                hr=hr,
                offset=offset,
                D=D,
                sigma=sigma,
                wake_processed=None,
            )

        # Load currents
        currents_z = None
        currents_r = None
        try:
            cz = loader.load_currents()
            if cz is not None:
                currents_z = cz[1]
        except Exception:
            pass
        try:
            cr = loader.load_currents_radial()
            if cr is not None:
                currents_r = cr[1]
        except Exception:
            pass

        # Load particles
        particles = loader.load_particles()

        # Load monitors
        monitors = []
        for m, n in loader.list_monitors():
            mon = loader.load_monitor(mode=m, monitor_id=n)
            if mon is not None:
                monitors.append(mon)

        # Build metadata
        metadata = RunMetadata(
            timestamp=datetime.now(),
            executable_path=str(self._executable_path or ""),
            executable_arch=_get_platform_key(),
            mpi_processes=1,
            omp_threads=int(os.environ.get("OMP_NUM_THREADS", 1)),
            elapsed_seconds=elapsed,
            hostname=socket.gethostname(),
            pyecho_version="0.1.0",
            return_code=return_code,
        )

        geometry_file = params.GeometryFile if params else ""

        return SimulationResult(
            params=params,
            geometry_file=geometry_file,
            output_dir=str(self.work_dir),
            modes=modes,
            currents_z=currents_z,
            currents_r=currents_r,
            particles=particles,
            monitors=monitors,
            metadata=metadata,
            stdout=stdout,
            stderr=stderr,
        )


# ---------------------------------------------------------------------------
# BatchRunner
# ---------------------------------------------------------------------------

class BatchRunner:
    """Run ECHO2D parameter sweeps over multiple configurations.

    Parameters
    ----------
    base_params : ECHO2DParams
        Baseline parameters; individual scan values override specific
        fields.
    work_root : str or Path
        Root directory for sweep output.  Each combination gets its own
        subdirectory.
    """

    def __init__(
        self,
        base_params: ECHO2DParams,
        work_root: str | Path,
    ) -> None:
        self.base_params = base_params
        self.work_root = Path(work_root).resolve()
        self.work_root.mkdir(parents=True, exist_ok=True)
        self._scans: list[tuple[str, list[Any]]] = []

    def add_scan(self, param_name: str, values: list[Any]) -> None:
        """Add a parameter to scan over.

        Parameters
        ----------
        param_name : str
            Name of the :class:`ECHO2DParams` field to vary (e.g.,
            ``"BunchSigma"``, ``"Modes"``).
        values : list
            Values to iterate over.
        """
        self._scans.append((param_name, values))

    def run_all(
        self,
        parallel: int = 1,
        executable: str | None = None,
    ) -> list[SimulationResult]:
        """Run all parameter combinations.

        Parameters
        ----------
        parallel : int
            Number of concurrent simulations (1 = sequential).
        executable : str, optional
            Path to the ECHO2D binary.

        Returns
        -------
        list[SimulationResult]
            Results in the same order as the parameter combinations.
        """
        import itertools

        if not self._scans:
            # Single run
            runner = ECHO2DRunner(self.work_root / "run_0", executable)
            return [runner.run(self.base_params)]

        param_names = [name for name, _ in self._scans]
        value_lists = [values for _, values in self._scans]

        results: list[SimulationResult] = []

        for idx, combo in enumerate(itertools.product(*value_lists)):
            run_dir = self.work_root / f"run_{idx}"
            run_params = self.base_params.model_copy()

            for name, val in zip(param_names, combo):
                setattr(run_params, name, val)

            logger.info(
                "Batch run %d/%d: %s",
                idx + 1,
                len(list(itertools.product(*value_lists))),
                {n: v for n, v in zip(param_names, combo)},
            )

            runner = ECHO2DRunner(run_dir, executable)
            result = runner.run(run_params)
            results.append(result)

        return results
