"""Comparison commands for the ECHO2D CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.table import Table

from pyecho.cli import compare_app

@compare_app.command("projects")
def compare_projects(
    project_a: Annotated[str, typer.Argument(help="First project name")],
    project_b: Annotated[str, typer.Argument(help="Second project name")],
    run_a: Annotated[
        Optional[str],
        typer.Option("--run-a", help="Run ID in first project (default: latest)"),
    ] = None,
    run_b: Annotated[
        Optional[str],
        typer.Option("--run-b", help="Run ID in second project (default: latest)"),
    ] = None,
    mode: Annotated[
        int,
        typer.Option("--mode", "-m", help="Azimuthal mode to compare"),
    ] = 0,
    output: Annotated[
        Optional[str],
        typer.Option("--output", "-o", help="Save comparison plot to file"),
    ] = None,
) -> None:
    """Compare wake results between two ECHO2D projects.

    .. note::

        This command is a **placeholder** (Phase 3).  The project
        management framework (``.echo2d.yaml`` manifests, workspace
        scanning, run tracking) is in place, but the cross-project
        comparison logic has not been implemented yet.

        Planned behaviour:
        - Resolve project names via workspace (no need to type paths)
        - Auto-select latest completed run in each project
        - Compare loss factors, wake curves, and modal decompositions
        - Support both round (single-mode) and recta (assembled) geometries
        - Generate side-by-side plots and summary tables

        Workaround for now:
        Use ``echo2d compare runs <dir1> <dir2>`` with explicit paths.
    """
    from pyecho.project import _get_workspace_root, scan_workspace, list_runs
    from pyecho.api import compare_runs as _cr
    from pyecho.visualize import plot_comparison

    ws = _get_workspace_root()

    # Resolve project dirs
    def _find_latest_run(proj_name: str, run_id: str | None) -> Path | None:
        proj_dir = ws / proj_name
        if not proj_dir.is_dir():
            return None
        runs = list_runs(proj_dir)
        if not runs:
            return None
        if run_id:
            for r in runs:
                if r.id == run_id:
                    return proj_dir / "runs" / r.dir_name
        # Latest completed
        for r in reversed(runs):
            d = proj_dir / "runs" / r.dir_name
            if d.is_dir():
                return d
        return None

    dir_a = _find_latest_run(project_a, run_a)
    dir_b = _find_latest_run(project_b, run_b)

    if dir_a is None:
        console.print(f"[red]Error: No runs found for project '{project_a}'[/red]")
        raise typer.Exit(1)
    if dir_b is None:
        console.print(f"[red]Error: No runs found for project '{project_b}'[/red]")
        raise typer.Exit(1)

    console.print(f"  [dim]A: {dir_a}[/dim]")
    console.print(f"  [dim]B: {dir_b}[/dim]")

    try:
        comp = _cr([str(dir_a), str(dir_b)], labels=[project_a, project_b], mode=mode)
    except Exception as exc:
        console.print(f"[red]Error: Comparison failed: {exc}[/red]")
        raise typer.Exit(1)

    # Display loss table
    table = Table(title=f"Mode {mode} Comparison")
    table.add_column("Project", style="cyan")
    table.add_column("Loss Factor [V/pC]", style="green")
    for lbl, loss in zip(comp["labels"], comp["losses"]):
        table.add_row(lbl, f"{loss:.6f}")
    console.print(table)

    # Plot
    results = [(lbl, comp["s"], w) for lbl, w in zip(comp["labels"], comp["W_list"])]
    fig, ax = plot_comparison(results, title=f"Mode {mode} Wake Comparison: {project_a} vs {project_b}")
    if output:
        fig.savefig(output, dpi=150, bbox_inches="tight")
        console.print(f"[green]Plot saved to {output}[/green]")
    import matplotlib.pyplot as plt
    plt.show()


@compare_app.command("runs")
def compare_runs_cmd(
    dirs: Annotated[list[str], typer.Argument(help="Output directories to compare")],
    labels: Annotated[
        Optional[list[str]],
        typer.Option("--labels", "-l", help="Labels"),
    ] = None,
    mode: Annotated[
        int,
        typer.Option("--mode", "-m", help="Mode to compare"),
    ] = 0,
    output: Annotated[
        Optional[str],
        typer.Option("--output", "-o", help="Save comparison plot"),
    ] = None,
) -> None:
    """Compare wake results from multiple runs."""
    from pyecho.api import compare_runs
    from pyecho.visualize import plot_comparison

    try:
        comp = compare_runs(dirs, labels=labels, mode=mode)
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] Comparison failed: {exc}")
        raise typer.Exit(1)

    # Build result list for plotting
    results = [
        (lbl, comp["s"], w)
        for lbl, w in zip(comp["labels"], comp["W_list"])
    ]

    # Display loss table
    table = Table(title=f"Mode {mode} Comparison")
    table.add_column("Run", style="cyan")
    table.add_column("Loss Factor [V/pC]", style="green")

    for lbl, loss in zip(comp["labels"], comp["losses"]):
        table.add_row(lbl, f"{loss:.6f}")

    console.print(table)

    # Plot
    fig, ax = plot_comparison(results, title=f"Mode {mode} Wake Comparison")
    if output:
        fig.savefig(output, dpi=150, bbox_inches="tight")
        console.print(f"[green]Plot saved to {output}[/green]")

    import matplotlib.pyplot as plt
    plt.show()


# ===================================================================
# system commands
# ===================================================================
