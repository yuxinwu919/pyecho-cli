"""Tests for the pyecho error hierarchy in ``pyecho/errors.py``.

Covers all 14 exception classes:
- message-only construction
- context keyword arguments (``**ctx``)
- file / field / value context on subclasses (Path objects coerced to str)
- inheritance chains
- ``__str__`` / ``__repr__`` output formatting
- stderr truncation in :class:`SimulationCrashedError`
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pyecho import errors as E


ALL_ERRORS = [
    E.PyEchoError,
    E.ConfigError,
    E.GeometryError,
    E.RunnerError,
    E.ParserError,
    E.PostProcessError,
    E.ExecutableNotFoundError,
    E.SimulationTimeoutError,
    E.SimulationCrashedError,
    E.ValidationError,
    E.MissingOutputError,
    E.PreprocessError,
    E.DependencyError,
    E.ProjectError,
]

RUNNER_ERRORS = [
    E.ExecutableNotFoundError,
    E.SimulationTimeoutError,
    E.SimulationCrashedError,
]

TRUNCATION_MARKER = "\n  ... (truncated)"


# ---------------------------------------------------------------------------
# Base class behavior (PyEchoError)
# ---------------------------------------------------------------------------


def test_pyecho_error_default_message_uses_class_name() -> None:
    """An empty message falls back to the class name in ``str``."""
    err = E.PyEchoError()
    assert err.message == ""
    assert err.ctx == {}
    assert str(err) == "PyEchoError"


def test_pyecho_error_message_only() -> None:
    """A message-only error stores the message and renders it verbatim."""
    err = E.PyEchoError("boom")
    assert err.message == "boom"
    assert err.ctx == {}
    assert err.args == ("boom",)
    assert str(err) == "boom"


def test_pyecho_error_context_kwargs() -> None:
    """Context kwargs are stored on ``ctx`` and rendered under the message."""
    err = E.PyEchoError("oops", foo="bar", n=1)
    assert err.ctx == {"foo": "bar", "n": 1}
    assert str(err) == "oops\n  foo: bar\n  n: 1"


def test_pyecho_error_container_context_multiline() -> None:
    """List/tuple context values render one indented item per line."""
    list_err = E.PyEchoError("m", items=["a", "b", "c"])
    assert str(list_err) == "m\n  items:\n    a\n    b\n    c"
    tuple_err = E.PyEchoError("m", items=("x", "y"))
    assert str(tuple_err) == "m\n  items:\n    x\n    y"


def test_pyecho_error_repr_format() -> None:
    """``repr`` includes the class name, message, and context dict."""
    err = E.PyEchoError("m", k="v")
    assert repr(err) == "PyEchoError('m', {'k': 'v'})"


# ---------------------------------------------------------------------------
# Inheritance chains
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("exc_cls", ALL_ERRORS)
def test_all_exception_classes_subclass_pyecho_error(exc_cls: type) -> None:
    """Every error class ultimately derives from PyEchoError and Exception."""
    assert issubclass(exc_cls, E.PyEchoError)
    assert issubclass(exc_cls, Exception)


@pytest.mark.parametrize("exc_cls", ALL_ERRORS)
def test_message_only_for_all_subclasses(exc_cls: type) -> None:
    """Every subclass supports message-only construction."""
    err = exc_cls("kaboom")
    assert err.message == "kaboom"
    assert err.ctx == {}
    assert err.args == ("kaboom",)
    assert str(err) == "kaboom"


@pytest.mark.parametrize("exc_cls", RUNNER_ERRORS)
def test_runner_errors_inherit_from_runner_error(exc_cls: type) -> None:
    """Runner-specific errors share the RunnerError base."""
    assert issubclass(exc_cls, E.RunnerError)
    assert issubclass(exc_cls, E.PyEchoError)


def test_missing_output_error_inherits_from_postprocess_error() -> None:
    """MissingOutputError is a PostProcessError."""
    assert issubclass(E.MissingOutputError, E.PostProcessError)
    assert issubclass(E.MissingOutputError, E.PyEchoError)


def test_subclass_caught_as_base_pyecho_error() -> None:
    """Catching PyEchoError (or Exception) also catches subclasses."""
    with pytest.raises(E.PyEchoError):
        raise E.ProjectError("bad project")
    caught: list[str] = []
    try:
        raise E.ConfigError("bad config")
    except Exception as exc:
        assert isinstance(exc, E.PyEchoError)
        caught.append(str(exc))
    assert caught == ["bad config"]


# ---------------------------------------------------------------------------
# Per-class typed context (file / field / value ...)
# ---------------------------------------------------------------------------


def test_config_error_context() -> None:
    """ConfigError coerces a Path config_file to str, keeps field, reprs value."""
    err = E.ConfigError(
        "bad cfg",
        config_file=Path("/a/b.txt"),
        field="energy",
        value=3.5,
    )
    assert err.ctx == {
        "config_file": "/a/b.txt",
        "field": "energy",
        "value": "3.5",
    }
    assert str(err) == (
        "bad cfg\n"
        "  config_file: /a/b.txt\n"
        "  field: energy\n"
        "  value: 3.5"
    )


def test_geometry_error_context() -> None:
    """GeometryError coerces Path geometry_file to str and keeps segment."""
    err = E.GeometryError(
        "bad geometry", geometry_file=Path("/g/geom.in"), segment=2
    )
    assert err.ctx == {"geometry_file": "/g/geom.in", "segment": 2}
    assert "segment: 2" in str(err)


def test_runner_error_context() -> None:
    """RunnerError coerces Paths and keeps the process return code."""
    err = E.RunnerError(
        "solver failed",
        work_dir=Path("/w"),
        executable=Path("/bin/echo"),
        returncode=3,
    )
    assert err.ctx == {
        "work_dir": "/w",
        "executable": "/bin/echo",
        "returncode": 3,
    }


def test_parser_error_context() -> None:
    """ParserError coerces Path file_path to str and keeps the line number."""
    err = E.ParserError("parse fail", file_path=Path("/o/out.txt"), line=7)
    assert err.ctx == {"file_path": "/o/out.txt", "line": 7}


def test_postprocess_error_context() -> None:
    """PostProcessError coerces Path data_dir to str and keeps the mode."""
    err = E.PostProcessError("post fail", data_dir=Path("/d"), mode=1)
    assert err.ctx == {"data_dir": "/d", "mode": 1}


def test_executable_not_found_error_context() -> None:
    """ExecutableNotFoundError keeps executable/platform and lists searched paths."""
    err = E.ExecutableNotFoundError(
        "no exe",
        executable="echo2d",
        platform_key="macos-arm",
        searched_paths=["/a", "/b"],
    )
    assert err.ctx == {
        "executable": "echo2d",
        "searched_paths": ["/a", "/b"],
        "platform_key": "macos-arm",
    }
    assert str(err) == (
        "no exe\n"
        "  searched_paths:\n"
        "    /a\n"
        "    /b\n"
        "  platform_key: macos-arm\n"
        "  executable: echo2d"
    )


def test_simulation_timeout_error_formatting() -> None:
    """Timeout/elapsed are rendered with units and one decimal place."""
    err = E.SimulationTimeoutError("too slow", timeout=10, elapsed=12.34)
    assert err.ctx == {"timeout": "10s", "elapsed": "12.3s"}
    assert str(err) == "too slow\n  timeout: 10s\n  elapsed: 12.3s"


# ---------------------------------------------------------------------------
# SimulationCrashedError stderr truncation
# ---------------------------------------------------------------------------


def test_simulation_crashed_short_stderr() -> None:
    """Short stderr is kept intact (stripped of surrounding whitespace)."""
    err = E.SimulationCrashedError("crashed", stderr="  some error  ")
    assert err.ctx == {"stderr": "some error"}


def test_simulation_crashed_long_stderr_truncated() -> None:
    """Long stderr is cut to 500 chars and suffixed with a truncation marker."""
    long_stderr = "line\n" * 200  # 999 chars after stripping
    err = E.SimulationCrashedError("crashed", stderr=long_stderr)
    value = err.ctx["stderr"]
    assert len(value) == 500 + len(TRUNCATION_MARKER)
    assert value.endswith(TRUNCATION_MARKER)
    assert value.startswith("line\n")
    assert "truncated" in str(err)
    # 500 / 5 chars per "line\n" unit -> exactly 100 lines kept
    assert value.count("line") == 100


def test_simulation_crashed_stderr_whitespace_stripped() -> None:
    """Surrounding whitespace does not count toward the 500-char budget."""
    body = "  \n  " + "x" * 499
    err = E.SimulationCrashedError("crashed", stderr=body)
    assert err.ctx["stderr"] == "x" * 499
    assert "truncated" not in err.ctx["stderr"]


# ---------------------------------------------------------------------------
# Remaining subclasses with typed context
# ---------------------------------------------------------------------------


def test_validation_error_context() -> None:
    """ValidationError keeps field/constraint and reprs the offending value."""
    err = E.ValidationError(
        "invalid input", field="x", value="abc", constraint="positive"
    )
    assert err.ctx == {
        "field": "x",
        "value": "'abc'",
        "constraint": "positive",
    }


def test_missing_output_error_context() -> None:
    """MissingOutputError renders each missing file on its own line."""
    err = E.MissingOutputError(
        "missing output", missing_files=["wake.dat", "bunch.dat"]
    )
    assert err.ctx == {"missing_files": ["wake.dat", "bunch.dat"]}
    assert str(err) == (
        "missing output\n  missing_files:\n    wake.dat\n    bunch.dat"
    )


def test_preprocess_error_context() -> None:
    """PreprocessError coerces Path input_file to str."""
    err = E.PreprocessError("pre fail", input_file=Path("/in/in.txt"))
    assert err.ctx == {"input_file": "/in/in.txt"}


def test_dependency_error_context() -> None:
    """DependencyError keeps the dependency name and install hint."""
    err = E.DependencyError(
        "h5py is required", dependency="h5py", install_hint="pip install h5py"
    )
    assert err.ctx == {"dependency": "h5py", "install_hint": "pip install h5py"}


def test_project_error_context() -> None:
    """ProjectError coerces both Paths to str."""
    err = E.ProjectError(
        "bad project",
        project_dir=Path("/proj"),
        manifest_file=Path("/proj/manifest.json"),
    )
    assert err.ctx == {
        "project_dir": "/proj",
        "manifest_file": "/proj/manifest.json",
    }
