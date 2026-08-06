"""Custom exceptions for pyecho.

All exceptions carry structured context (file paths, parameter values,
etc.) to enable precise error messages and debugging.  Use the factory
methods or keyword arguments to attach context at raise time.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


class PyEchoError(Exception):
    """Base exception for pyecho.

    Parameters
    ----------
    message : str
        Human-readable error description.
    **ctx : Any
        Arbitrary context key-value pairs attached to the exception.
    """

    def __init__(self, message: str = "", **ctx: Any) -> None:
        super().__init__(message)
        self.message: str = message
        self.ctx: dict[str, Any] = ctx

    def __str__(self) -> str:
        parts = [self.message] if self.message else [self.__class__.__name__]
        for key, value in self.ctx.items():
            if isinstance(value, (list, tuple)):
                lines = "\n".join(f"    {item}" for item in value)
                parts.append(f"  {key}:\n{lines}")
            else:
                parts.append(f"  {key}: {value}")
        return "\n".join(parts)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.message!r}, {self.ctx!r})"


class ConfigError(PyEchoError):
    """Configuration / parameter validation error.

    Parameters
    ----------
    message : str
        Description of the configuration problem.
    config_file : Path or str, optional
        Path to the malformed configuration file.
    field : str, optional
        Name of the invalid field (if applicable).
    value : Any, optional
        The invalid value that caused the error.
    """

    def __init__(
        self,
        message: str = "",
        *,
        config_file: Path | str | None = None,
        field: str | None = None,
        value: Any = None,
        **ctx: Any,
    ) -> None:
        if config_file is not None:
            ctx.setdefault("config_file", str(config_file))
        if field is not None:
            ctx.setdefault("field", field)
        if value is not None:
            ctx.setdefault("value", repr(value))
        super().__init__(message, **ctx)


class GeometryError(PyEchoError):
    """Geometry parsing or validation error.

    Parameters
    ----------
    message : str
        Description of the geometry error.
    geometry_file : Path or str, optional
        Path to the geometry file.
    segment : int, optional
        Segment index that caused the error.
    """

    def __init__(
        self,
        message: str = "",
        *,
        geometry_file: Path | str | None = None,
        segment: int | None = None,
        **ctx: Any,
    ) -> None:
        if geometry_file is not None:
            ctx.setdefault("geometry_file", str(geometry_file))
        if segment is not None:
            ctx.setdefault("segment", segment)
        super().__init__(message, **ctx)


class RunnerError(PyEchoError):
    """ECHO2D executable runtime error.

    Parameters
    ----------
    message : str
        Description of the runtime failure.
    work_dir : Path or str, optional
        Working directory where the simulation was running.
    executable : Path or str, optional
        Path to the ECHO2D binary.
    returncode : int, optional
        Process exit code (if applicable).
    """

    def __init__(
        self,
        message: str = "",
        *,
        work_dir: Path | str | None = None,
        executable: Path | str | None = None,
        returncode: int | None = None,
        **ctx: Any,
    ) -> None:
        if work_dir is not None:
            ctx.setdefault("work_dir", str(work_dir))
        if executable is not None:
            ctx.setdefault("executable", str(executable))
        if returncode is not None:
            ctx.setdefault("returncode", returncode)
        super().__init__(message, **ctx)


class ParserError(PyEchoError):
    """Output file parsing error.

    Parameters
    ----------
    message : str
        Description of the parse failure.
    file_path : Path or str, optional
        Path to the file that failed to parse.
    line : int, optional
        Line number where the parse error occurred.
    """

    def __init__(
        self,
        message: str = "",
        *,
        file_path: Path | str | None = None,
        line: int | None = None,
        **ctx: Any,
    ) -> None:
        if file_path is not None:
            ctx.setdefault("file_path", str(file_path))
        if line is not None:
            ctx.setdefault("line", line)
        super().__init__(message, **ctx)


class PostProcessError(PyEchoError):
    """Post-processing error.

    Parameters
    ----------
    message : str
        Description of the post-processing failure.
    data_dir : Path or str, optional
        Directory containing the data being processed.
    mode : int, optional
        Mode number being processed (if applicable).
    """

    def __init__(
        self,
        message: str = "",
        *,
        data_dir: Path | str | None = None,
        mode: int | None = None,
        **ctx: Any,
    ) -> None:
        if data_dir is not None:
            ctx.setdefault("data_dir", str(data_dir))
        if mode is not None:
            ctx.setdefault("mode", mode)
        super().__init__(message, **ctx)


class ExecutableNotFoundError(RunnerError):
    """ECHO2D executable not found.

    Parameters
    ----------
    executable : str, optional
        Name or path of the executable that was searched for.
    searched_paths : list[str], optional
        Paths that were searched.
    platform_key : str, optional
        Detected platform-architecture key.
    """

    def __init__(
        self,
        message: str = "",
        *,
        executable: str | None = None,
        searched_paths: list[str] | None = None,
        platform_key: str | None = None,
        **ctx: Any,
    ) -> None:
        if executable is not None:
            ctx.setdefault("executable", executable)
        if searched_paths is not None:
            ctx.setdefault("searched_paths", searched_paths)
        if platform_key is not None:
            ctx.setdefault("platform_key", platform_key)
        super().__init__(message, **ctx)


class SimulationTimeoutError(RunnerError):
    """Simulation timed out.

    Parameters
    ----------
    timeout : int or float, optional
        Timeout duration that was exceeded (in seconds).
    elapsed : float, optional
        Actual elapsed time.
    """

    def __init__(
        self,
        message: str = "",
        *,
        timeout: int | float | None = None,
        elapsed: float | None = None,
        **ctx: Any,
    ) -> None:
        if timeout is not None:
            ctx.setdefault("timeout", f"{timeout}s")
        if elapsed is not None:
            ctx.setdefault("elapsed", f"{elapsed:.1f}s")
        super().__init__(message, **ctx)


class SimulationCrashedError(RunnerError):
    """ECHO2D returned non-zero exit code.

    Parameters
    ----------
    stderr : str, optional
        Captured standard error output.
    """

    def __init__(
        self,
        message: str = "",
        *,
        stderr: str | None = None,
        **ctx: Any,
    ) -> None:
        if stderr is not None:
            # Truncate long stderr for readability
            truncated = stderr.strip()[:500]
            if len(stderr.strip()) > 500:
                truncated += "\n  ... (truncated)"
            ctx.setdefault("stderr", truncated)
        super().__init__(message, **ctx)


class ValidationError(PyEchoError):
    """Input validation error — a value does not meet requirements.

    Parameters
    ----------
    field : str, optional
        Name of the field that failed validation.
    value : Any, optional
        The value that failed validation.
    constraint : str, optional
        Description of the constraint that was violated.
    """

    def __init__(
        self,
        message: str = "",
        *,
        field: str | None = None,
        value: Any = None,
        constraint: str | None = None,
        **ctx: Any,
    ) -> None:
        if field is not None:
            ctx.setdefault("field", field)
        if value is not None:
            ctx.setdefault("value", repr(value))
        if constraint is not None:
            ctx.setdefault("constraint", constraint)
        super().__init__(message, **ctx)
