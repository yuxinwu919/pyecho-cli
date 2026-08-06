"""Workspace viewer for the ECHO2D CLI."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.panel import Panel
from rich.table import Table

from pyecho.cli import app, console

@app.command("workspace")
def workspace_cmd(
    ctx: typer.Context,
    scan_dir: Annotated[
        Optional[str],
        typer.Option("--scan", "-s", help="Scan a custom directory instead of the default workspace"),
    ] = None,
) -> None:
    """Show workspace information and list projects."""
    from pyecho.project import _get_workspace_root, scan_workspace

    _json = ctx.obj.get("json", False)

    ws_root = Path(scan_dir).expanduser().resolve() if scan_dir else _get_workspace_root()
    projects = scan_workspace(ws_root)

    if _json:
        data = {
            "workspace": str(ws_root),
            "project_count": len(projects),
            "projects": {
                name: {
                    "runs": len(p.runs),
                    "created": p.created,
                    "template": p.template,
                    "geometry_type": p.geometry_type,
                }
                for name, p in projects.items()
            },
        }
        console.print_json(json.dumps(data, indent=2))
        return

    # Rich output
    env_source = "from ECHO2D_WORKSPACE" if os.environ.get("ECHO2D_WORKSPACE") else "default"
    console.print(
        Panel.fit(
            f"[bold]Workspace:[/bold] [cyan]{ws_root}[/cyan]  ([dim]{env_source}[/dim])\n"
            f"Projects: [bold]{len(projects)}[/bold] found\n\n"
            "Change: [dim]export ECHO2D_WORKSPACE=/your/path[/dim]",
            title="ECHO2D Workspace",
        )
    )

    if not projects:
        console.print(
            "\n[dim]No projects yet. Create one with "
            "[cyan]echo2d project init <name>[/cyan][/dim]"
        )
        return

    table = Table(title="Projects")
    table.add_column("Name", style="cyan")
    table.add_column("Type", style="yellow")
    table.add_column("Runs", justify="right")
    table.add_column("Created", style="dim")

    for name, p in sorted(projects.items()):
        gtype = "Recta" if p.geometry_type == "recta" else "Round"
        table.add_row(name, gtype, str(len(p.runs)), p.created[:10])

    console.print(table)


# ===================================================================
# project commands
# ===================================================================
# The project commands manage ECHO2D projects using the new
# .echo2d.yaml manifest format (Phase 1).  Legacy projects without
# a manifest are auto-detected and can be migrated.
