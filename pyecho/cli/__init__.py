"""ECHO2D command-line interface.

Comprehensive CLI built with Typer and Rich for beautiful terminal
output.  Covers project management, geometry operations, configuration,
simulation execution, post-processing, visualization, data export,
comparison analysis, testing, and system information.

Usage::

    echo2d --help
    echo2d run single --work-dir . --np 4
    echo2d postprocess wake output_dir/
    echo2d visualize wake wakeL_00.txt
"""

from __future__ import annotations

import logging

import typer
from rich.console import Console

from pyecho._version import __version__


# ---------------------------------------------------------------------------
# Lazy helpers (used in autocompletion lambdas; import deferred to avoid
# circular dependency issues at module-load time)
# ---------------------------------------------------------------------------

def _get_template_names() -> list[str]:
    """Return registered template names for CLI autocompletion."""
    from pyecho.config import ECHO2DParams
    return ECHO2DParams.list_templates()


def _get_project_names() -> list[str]:
    """Return workspace project names for CLI autocompletion."""
    try:
        from pyecho.project import _get_workspace_root, scan_workspace
        return sorted(scan_workspace(_get_workspace_root()).keys())
    except Exception:
        return []


def _get_run_ids() -> list[str]:
    """Return run directory IDs from the current project for CLI autocompletion."""
    try:
        from pathlib import Path
        cwd = Path.cwd()
        runs_dir = cwd / "runs"
        if runs_dir.is_dir():
            return sorted(
                d.name for d in runs_dir.iterdir()
                if d.is_dir() and (d / ".run.yaml").is_file()
            )
        # Walk up to find project root
        for _ in range(10):
            if (cwd / ".echo2d.yaml").is_file():
                runs_dir = cwd / "runs"
                if runs_dir.is_dir():
                    return sorted(
                        d.name for d in runs_dir.iterdir()
                        if d.is_dir() and (d / ".run.yaml").is_file()
                    )
            parent = cwd.parent
            if parent == cwd:
                break
            cwd = parent
        return []
    except Exception:
        return []

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = typer.Typer(
    rich_markup_mode="rich",
    name="echo2d",
    help="ECHO2D — accelerator wakefield / impedance solver toolkit.  "
         "Run 'echo2d <command> --help' for detailed usage.",
    invoke_without_command=True,
)

console = Console()
logger = logging.getLogger(__name__)

# Sub-apps
project_app = typer.Typer(help="Project management")
geometry_app = typer.Typer(help="Geometry operations")
config_app = typer.Typer(help="Parameter configuration")
run_app = typer.Typer(help="Simulation execution")
postprocess_app = typer.Typer(help="Post-processing")
visualize_app = typer.Typer(help="Visualization")
export_app = typer.Typer(help="Data export")
compare_app = typer.Typer(help="Compare analysis")
system_app = typer.Typer(help="System information")

app.add_typer(project_app, name="project")
app.add_typer(geometry_app, name="geometry")
app.add_typer(config_app, name="config")
app.add_typer(run_app, name="run")
app.add_typer(postprocess_app, name="postprocess")
app.add_typer(visualize_app, name="visualize")
app.add_typer(export_app, name="export")
app.add_typer(compare_app, name="compare")
app.add_typer(system_app, name="system")


# ---------------------------------------------------------------------------
# Example templates (re-exported from _examples)
# ---------------------------------------------------------------------------

from pyecho.cli._examples import (  # noqa: E402
    _EXAMPLES,
    _TEMPLATES_DIR,
    _print_example_summary,
)


# ---------------------------------------------------------------------------
# Backend dispatcher — subcommands call this to get the right plot function
# ---------------------------------------------------------------------------

def _get_plot_backend(ctx):
    """Return ``"pyqtgraph"`` or ``"matplotlib"`` from the Typer context.

    Falls back to matplotlib if pyqtgraph was requested but isn't installed.
    """
    import typer as _typer

    ctx_obj: dict = getattr(ctx, "obj", None) or {}
    backend: str = ctx_obj.get("backend", "pyqtgraph")

    if backend == "pyqtgraph":
        try:
            import pyqtgraph  # noqa: F401
        except ImportError:
            console.print(
                "[yellow]pyqtgraph not installed; falling back to matplotlib.[/yellow]\n"
                "[dim]Install with: pip install pyqtgraph PySide2[/dim]"
            )
            return "matplotlib"
    return backend


# ---------------------------------------------------------------------------
# Import command modules to register commands on sub-apps
# ---------------------------------------------------------------------------

from pyecho.cli._helpers import (  # noqa: E402, F401
    _collect_output,
    _copy_geometry_to_run,
    _detect_python_env,
    _find_exe_in_dir,
    _generate_corrugated_geometry,
    _plot_monitor_slice,
    _read_offset_from_dir,
    _resolve_input_file,
    _resolve_plot_data_dir,
    _run_auto_fix,
    _save_monitor_total,
    _save_wake_recta,
    _save_wake_round_data,
    _serialize_geo,
    _show_welcome,
    _try_update_processed_manifest,
    _write_dlw_geometry,
    _write_pipe_default,
    _write_pipe_from_segments,
)

# Import all command modules to register their commands
import pyecho.cli.main_callback  # noqa: E402, F401
import pyecho.cli.example  # noqa: E402, F401
import pyecho.cli.workspace  # noqa: E402, F401
import pyecho.cli.project  # noqa: E402, F401
import pyecho.cli.geometry  # noqa: E402, F401
import pyecho.cli.config  # noqa: E402, F401
import pyecho.cli.run  # noqa: E402, F401
import pyecho.cli.postprocess  # noqa: E402, F401
import pyecho.cli.visualize  # noqa: E402, F401
import pyecho.cli.export  # noqa: E402, F401
import pyecho.cli.compare  # noqa: E402, F401
import pyecho.cli.system  # noqa: E402, F401
