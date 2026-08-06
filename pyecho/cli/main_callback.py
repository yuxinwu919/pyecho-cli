"""Root callback and welcome screen for the ECHO2D CLI."""

from __future__ import annotations

import logging
import sys

from typing import Annotated

import typer
from rich.table import Table
from rich.tree import Tree

from pyecho._version import __version__
from pyecho.cli import app, console, _show_welcome, _get_template_names

# ---------------------------------------------------------------------------
# Global callback
# ---------------------------------------------------------------------------

@app.callback()
def main_callback(
    ctx: typer.Context,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Verbose output (DEBUG level logging)"),
    ] = False,
    version: Annotated[
        bool,
        typer.Option("--version", help="Show version and exit"),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            help="Machine-readable JSON output (disables Rich formatting)",
        ),
    ] = False,
) -> None:
    """ECHO2D — accelerator wakefield / impedance solver toolkit.

    Based on the ECHO2D solver by Igor Zagorodnov (DESY).
    Official site: https://echo4d.de

    \b
    [bold]Quick start (new workflow):[/bold]
      echo2d project init myproj -t round_collimator
      echo2d run start --threads 4
      echo2d postprocess wake . --plot

    \b
    [bold]Manage projects:[/bold]
      echo2d workspace                    # show workspace & projects
      echo2d project list                 # list all projects
      echo2d project info                 # project details & run history

    \b
    [bold]Manage runs:[/bold]
      echo2d run new --name "fine_mesh"   # create a new run
      echo2d run list                     # list runs in project
      echo2d run start                    # execute latest run

    \b
    [bold]Run built-in examples:[/bold]
      echo2d example list                 # see what's available
      echo2d example round-collimator     # run N1 with one command

    \b
    [bold]Explore your system:[/bold]
      echo2d system check                 # verify installation
      echo2d system detect                # find ECHO2D executables
      echo2d system info                  # version & platform info

    \b
    [bold]Understand your data:[/bold]
      echo2d visualize wake wakeL_00.txt --bunch Iz0.txt
      echo2d visualize compare run1/wakeL_00.txt run2/wakeL_00.txt
      echo2d export csv output_dir/ -o results/

    \b
    [bold]Need help?[/bold]
      echo2d <command> --help             # detailed help for any command
    """
    if version:
        console.print(f"[bold]echo2d[/bold] version [cyan]{__version__}[/cyan]")
        console.print(f"Python [cyan]{sys.version}[/cyan]")
        raise typer.Exit()

    # When invoked without subcommand, show welcome / portal screen.
    # Future: this will also list echo2d-tui once available.
    if ctx.invoked_subcommand is None:
        _show_welcome()
        raise typer.Exit()

    # Configure logging: WARNING+ → stderr by default; DEBUG with --verbose.
    # Use a StreamHandler writing to stderr so log output does not
    # interfere with stdout pipelines (e.g. ``echo2d ... | ...``).
    _root_logger = logging.getLogger("pyecho")
    _root_logger.setLevel(logging.DEBUG if verbose else logging.WARNING)
    if not _root_logger.handlers:
        _handler = logging.StreamHandler(sys.stderr)
        _handler.setFormatter(
            logging.Formatter(
                "[%(levelname)-5s] %(name)s: %(message)s"
            )
        )
        _root_logger.addHandler(_handler)
        _root_logger.propagate = False

    if verbose:
        console.print("[dim]Verbose mode enabled (DEBUG logging to stderr)[/dim]")

    # Store in context for subcommands.  Subcommands that support
    # structured output read ctx.obj["json"] to decide between Rich
    # rendering and plain JSON on stdout.
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["json"] = json_output


# ===================================================================
# workspace command
# ===================================================================
# NOTE(tui): Workspace management (multi-workspace switching, visual
# project browser, etc.) will be implemented in echo2d-tui.  The CLI
# workspace command is intentionally minimal — read-only info display.
# The workspace root is controlled via the ECHO2D_WORKSPACE env var.
