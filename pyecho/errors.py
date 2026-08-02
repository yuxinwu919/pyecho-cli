"""Custom exceptions for pyecho."""


class PyEchoError(Exception):
    """Base exception for pyecho."""
    pass


class ConfigError(PyEchoError):
    """Configuration / parameter validation error."""
    pass


class GeometryError(PyEchoError):
    """Geometry parsing or validation error."""
    pass


class RunnerError(PyEchoError):
    """ECHO2D executable runtime error."""
    pass


class ParserError(PyEchoError):
    """Output file parsing error."""
    pass


class PostProcessError(PyEchoError):
    """Post-processing error."""
    pass


class ExecutableNotFoundError(RunnerError):
    """ECHO2D executable not found."""
    pass


class SimulationTimeoutError(RunnerError):
    """Simulation timed out."""
    pass


class SimulationCrashedError(RunnerError):
    """ECHO2D returned non-zero exit code."""
    pass
