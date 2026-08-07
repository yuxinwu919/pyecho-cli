"""Tests for the ECHO2D CLI structure, registration, and help output.

These tests exercise the Typer app defined in :mod:`pyecho.cli`: that it is
a real Typer instance, that all nine sub-apps are registered, that the
``--help`` output renders for the root and every sub-app, and that several
read-only commands (``system check``, ``example list``, ``project list``,
``project templates``) execute successfully via CliRunner.

All assertions use substring matching so they are resilient to Rich ANSI
escape codes and panel borders in the output.
"""

from __future__ import annotations

import re

import typer
from typer.testing import CliRunner

from pyecho.cli import app

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

runner = CliRunner()

#: All nine sub-apps that must be registered on the root app.
SUBSCRIPT_COMMANDS = (
    "project",
    "geometry",
    "config",
    "run",
    "postprocess",
    "visualize",
    "export",
    "compare",
    "system",
)


def _help_contains(subcommand: str, expected: tuple[str, ...]) -> None:
    """Invoke ``echo2d <subcommand> --help`` and assert it renders cleanly."""
    result = runner.invoke(app, [subcommand, "--help"])
    assert result.exit_code == 0, (
        f"`echo2d {subcommand} --help` failed with exit {result.exit_code}: "
        f"{result.exception}"
    )
    for token in expected:
        assert token in result.output, (
            f"expected {token!r} in `echo2d {subcommand} --help` output:\n"
            f"{result.output}"
        )


# ---------------------------------------------------------------------------
# 1-2. App structure
# ---------------------------------------------------------------------------

def test_app_is_typer() -> None:
    """The root ``echo2d`` app is a Typer instance."""
    assert isinstance(app, typer.Typer)
    assert app.info.name == "echo2d"


def test_all_nine_subapps_registered() -> None:
    """Every sub-app in SUBSCRIPT_COMMANDS is registered on the root app."""
    registered = {
        info.name for info in app.registered_groups if info.typer_instance is not None
    }
    for name in SUBSCRIPT_COMMANDS:
        assert name in registered, f"sub-app {name!r} is not registered"


# ---------------------------------------------------------------------------
# 3. Root help
# ---------------------------------------------------------------------------

def test_root_help_shows_usage() -> None:
    """``echo2d --help`` renders usage and lists all sub-commands."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0, result.exception
    assert "Usage:" in result.output
    for name in (*SUBSCRIPT_COMMANDS, "example", "workspace"):
        assert name in result.output, (
            f"expected {name!r} in root --help output:\n{result.output}"
        )


# ---------------------------------------------------------------------------
# 4-12. Per-sub-app help
# ---------------------------------------------------------------------------

def test_project_help() -> None:
    """``echo2d project --help`` lists project management commands."""
    _help_contains("project", ("init", "templates", "list", "info", "migrate"))


def test_run_help() -> None:
    """``echo2d run --help`` lists simulation commands."""
    _help_contains("run", ("new", "start", "list", "single", "batch", "sweep"))


def test_run_sweep_help() -> None:
    """``echo2d run sweep --help`` lists every sweep option."""
    result = runner.invoke(app, ["run", "sweep", "--help"])
    assert result.exit_code == 0, result.exception
    # Strip Rich ANSI colour codes — option names are split by escape
    # sequences (``-\x1b[1;36m-param``), so a raw substring match on
    # ``--param`` would be too brittle.
    clean = re.sub(r"\x1b\[[0-9;]*m", "", result.output)
    for token in (
        "--param", "--values", "--from-run",
        "--geo-param", "--geo-values",
        "--threads", "--dry-run",
    ):
        assert token in clean, (
            f"expected {token!r} in `echo2d run sweep --help` output:\n"
            f"{result.output}"
        )


def test_postprocess_help() -> None:
    """``echo2d postprocess --help`` lists post-processing commands."""
    _help_contains(
        "postprocess",
        ("wake", "impedance", "field", "particles", "report", "summary"),
    )


def test_postprocess_summary_help() -> None:
    """``echo2d postprocess summary --help`` renders and lists options."""
    result = runner.invoke(app, ["postprocess", "summary", "--help"])
    assert result.exit_code == 0, result.exception
    # Strip Rich ANSI colour codes — option names may be split by escape
    # sequences, so a raw substring match is too brittle.
    clean = re.sub(r"\x1b\[[0-9;]*m", "", result.output)
    for token in (
        "RUNS...",
        "Generate a summary table across multiple runs",
        "--project",
        "--sort",
        "Sort by: name, loss, kick",
    ):
        assert token in clean, (
            f"expected {token!r} in `echo2d postprocess summary --help` output:\n"
            f"{result.output}"
        )


def test_run_start_help_shows_with_particles() -> None:
    """``echo2d run start --help`` advertises the --with-particles option."""
    result = runner.invoke(app, ["run", "start", "--help"])
    assert result.exit_code == 0, result.exception
    clean = re.sub(r"\x1b\[[0-9;]*m", "", result.output)
    assert "--with-particles" in clean, (
        f"expected '--with-particles' in `echo2d run start --help` output:\n"
        f"{result.output}"
    )


def test_postprocess_particles_help_shows_plot_and_emittance() -> None:
    """``echo2d postprocess particles --help`` advertises --plot/--emittance."""
    result = runner.invoke(app, ["postprocess", "particles", "--help"])
    assert result.exit_code == 0, result.exception
    clean = re.sub(r"\x1b\[[0-9;]*m", "", result.output)
    for token in ("--plot", "--emittance"):
        assert token in clean, (
            f"expected {token!r} in `echo2d postprocess particles --help` "
            f"output:\n{result.output}"
        )


def test_postprocess_summary_no_matches_exits_cleanly() -> None:
    """``echo2d postprocess summary <missing>`` errors cleanly (exit 1)."""
    result = runner.invoke(
        app,
        ["postprocess", "summary", "no_such_run_xyz", "--project", "/nonexistent"],
    )
    assert result.exit_code == 1
    assert "No run directories found" in result.output


def test_geometry_help() -> None:
    """``echo2d geometry --help`` lists geometry commands."""
    _help_contains("geometry", ("create", "validate", "show", "info"))


def test_config_help() -> None:
    """``echo2d config --help`` lists configuration commands."""
    _help_contains("config", ("generate", "validate", "show", "generate-bunch"))


def test_visualize_help() -> None:
    """``echo2d visualize --help`` lists visualization commands."""
    _help_contains("visualize", ("wake", "impedance", "compare", "modes"))


def test_export_help() -> None:
    """``echo2d export --help`` lists export commands."""
    _help_contains("export", ("hdf5", "csv"))


def test_compare_help() -> None:
    """``echo2d compare --help`` lists comparison commands."""
    _help_contains("compare", ("projects", "runs"))


def test_system_help() -> None:
    """``echo2d system --help`` lists system commands."""
    _help_contains("system", ("info", "detect", "check"))


# ---------------------------------------------------------------------------
# 13-16. Read-only commands
# ---------------------------------------------------------------------------

def test_system_check_runs() -> None:
    """``echo2d system check`` verifies dependencies without crashing."""
    result = runner.invoke(app, ["system", "check"])
    assert result.exit_code == 0, result.exception
    assert "Checking Python dependencies" in result.output
    assert "NumPy" in result.output
    assert "Summary" in result.output


def test_example_list() -> None:
    """``echo2d example list`` enumerates the built-in examples."""
    result = runner.invoke(app, ["example", "list"])
    assert result.exit_code == 0, result.exception
    for ex in ("round-collimator", "flat-absorber", "pohang-dechirper", "tesla-cavity"):
        assert ex in result.output, (
            f"expected example {ex!r} in output:\n{result.output}"
        )


def test_project_list() -> None:
    """``echo2d project list`` scans the workspace without crashing."""
    result = runner.invoke(app, ["project", "list"])
    assert result.exit_code == 0, result.exception
    # No projects exist in a fresh environment; the command must still succeed
    # and render a project-related message.
    assert "project" in result.output.lower()


def test_project_templates() -> None:
    """``echo2d project templates`` lists every registered template."""
    result = runner.invoke(app, ["project", "templates"])
    assert result.exit_code == 0, result.exception
    for tpl in ("round_collimator", "flat_absorber", "tesla_cavity", "dlw"):
        assert tpl in result.output, (
            f"expected template {tpl!r} in output:\n{result.output}"
        )
