"""Project management commands for the ECHO2D CLI."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from pyecho.cli import project_app, console
from pyecho.cli._helpers import (
    _copy_geometry_to_run,
    _resolve_input_file,
    _run_auto_fix,
    _show_welcome,
)
from pyecho.cli._examples import _EXAMPLES, _TEMPLATES_DIR

# ---------------------------------------------------------------------------
# Project commands
# ---------------------------------------------------------------------------

@project_app.command("init")
def project_init(
    name: Annotated[str, typer.Argument(help="Project name")],
    template: Annotated[
        str,
        typer.Option(
            "--template", "-t",
            help="Project template (use 'empty' for a blank project)",
            autocompletion=lambda: ["empty"] + _get_template_names(),
        ),
    ] = "round_collimator",
    here: Annotated[
        bool,
        typer.Option(
            "--here",
            help="Create project in the current directory instead of the workspace",
        ),
    ] = False,
    directory: Annotated[
        Optional[str],
        typer.Option("--dir", "-d", help="Custom target directory (overrides workspace)"),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Overwrite existing directory"),
    ] = False,
) -> None:
    """Create a new ECHO2D project with standard structure.

    By default, projects are created in the workspace
    By default, creates the project in the current working directory.
    Use ECHO2D_WORKSPACE env var or --dir to specify a different location.
    directory, or --dir for a custom location.
    """
    from pyecho.project import (
        init_project as _init_project,
        _get_workspace_root,
    )

    # Resolve geometry type from template
    gt = "recta" if "flat" in template or "dechirper" in template or template == "dlw" else "round"

    # Determine target
    if here:
        workspace_root = Path.cwd()
    elif directory:
        workspace_root = Path(directory).resolve()
    else:
        workspace_root = _get_workspace_root()

    try:
        manifest = _init_project(
            name=name,
            template=template if template != "empty" else "",
            geometry_type=gt,
            workspace=workspace_root,
        )
    except FileExistsError:
        if force:
            # Re-create by removing existing
            import shutil
            target = workspace_root / name
            shutil.rmtree(target, ignore_errors=True)
            manifest = _init_project(
                name=name, template=template if template != "empty" else "",
                geometry_type=gt, workspace=workspace_root,
            )
        else:
            console.print(
                f"[bold red]Error:[/bold red] Project '{name}' already exists. "
                "Use --force to overwrite."
            )
            raise typer.Exit(1)

    project_dir = workspace_root / name

    # Display result
    console.print(
        Panel.fit(
            f"[bold green]✓[/bold green] Project '[cyan]{name}[/cyan]' created\n"
            f"  Location:  [dim]{project_dir}[/dim]\n"
            f"  Template:  {template}\n"
            f"  Type:      {gt}\n"
            f"  First run: runs/{manifest.runs[0].dir_name}/",
            title="Project Initialized",
        )
    )

    # Show project tree
    run_dir = manifest.runs[0].dir_name
    tree = Tree(f"[bold]{name}/[/bold]")
    tree.add("[cyan].echo2d.yaml[/cyan]")
    runs_node = tree.add("runs/")
    run_node = runs_node.add(f"[bold]{run_dir}/[/bold]")
    run_node.add("[cyan].run.yaml[/cyan]")
    run_node.add("input_in.txt")
    if gt == "recta":
        run_node.add("magn/")
        run_node.add("elec/")
    else:
        run_node.add("round/")
    proc_node = run_node.add("processed/")
    proc_node.add("wake/")
    proc_node.add("field/")
    proc_node.add("particles/")
    console.print(tree)

    console.print(
        "\n[dim]Next:  cd {0}  &&  edit runs/{1}/input_in.txt  &&  "
        "echo2d run start[/dim]".format(project_dir, run_dir)
    )


@project_app.command("templates")
def project_templates() -> None:
    """List available project templates."""
    from pyecho.config import ECHO2DParams

    templates = ECHO2DParams.list_templates()

    table = Table(title="Available Templates")
    table.add_column("Name", style="cyan")
    table.add_column("Type", style="yellow")
    table.add_column("Description", style="green")

    descriptions = {
        "round_collimator": "Rotationally symmetric collimator (round)",
        "flat_absorber": "Rectangular photon absorber (recta)",
        "tesla_cavity": "TESLA 9-cell superconducting cavity",
        "dlw": "Dielectric lined waveguide (DLW)",
    }

    for t in templates:
        gtype = "Recta" if "flat" in t or t == "dlw" else "Round"
        table.add_row(t, gtype, descriptions.get(t, "—"))

    console.print(table)


@project_app.command("examples")
def project_examples() -> None:
    """List available example projects."""
    from pyecho.config import ECHO2DParams

    templates = ECHO2DParams.list_templates()

    table = Table(title="Available Examples")
    table.add_column("Name", style="cyan")
    table.add_column("Type", style="yellow")
    table.add_column("Description", style="green")

    for t in templates:
        if "flat" in t:
            gtype = "Rectangular"
            desc = "Rectangular geometry example"
        else:
            gtype = "Round"
            desc = "Rotationally symmetric geometry example"
        table.add_row(t, gtype, desc)

    console.print(table)


@project_app.command("list")
def project_list(
    ctx: typer.Context,
    all_projects: Annotated[
        bool,
        typer.Option("--all", "-a", help="Scan all directories (not just workspace)"),
    ] = False,
) -> None:
    """List ECHO2D projects.

    By default, scans the current directory for projects.
    Use --all to scan the current directory for legacy projects as well.
    """
    from pyecho.project import scan_workspace, is_legacy_project, _get_workspace_root

    _json = ctx.obj.get("json", False)

    # Collect new-format projects from workspace
    projects = scan_workspace()

    # Optionally scan current directory for legacy projects
    legacy: list[Path] = []
    if all_projects:
        for d in Path.cwd().iterdir():
            if d.is_dir() and is_legacy_project(d):
                legacy.append(d)

    if _json:
        data = {
            "new_format": {name: {"runs": len(p.runs)} for name, p in projects.items()},
            "legacy": [str(d) for d in legacy],
        }
        console.print_json(json.dumps(data, indent=2))
        return

    if not projects and not legacy:
        console.print(
            "[yellow]No projects found.[/yellow] "
            "Create one with [cyan]echo2d project init <name>[/cyan]"
        )
        return

    table = Table(title="Projects")
    table.add_column("Name", style="cyan")
    table.add_column("Runs", justify="right")
    table.add_column("Created", style="dim")
    table.add_column("Status")

    for name, p in sorted(projects.items()):
        table.add_row(name, str(len(p.runs)), p.created[:10], "[green]✓[/green]")

    for d in sorted(legacy, key=lambda x: x.name):
        table.add_row(f"{d.name}", "—", "—", "[yellow]legacy[/yellow]")

    console.print(table)

    if legacy:
        console.print(
            "\n[dim]Legacy projects can be migrated with "
            "[cyan]echo2d project migrate <name>[/cyan][/dim]"
        )


@project_app.command("info")
def project_info(
    ctx: typer.Context,
    project_dir: Annotated[
        str,
        typer.Option("--dir", "-d", help="Project directory (default: current)"),
    ] = ".",
) -> None:
    """Show detailed project information."""
    from pyecho.project import (
        load_project, is_legacy_project, is_echo2d_project, list_runs,
    )

    _json = ctx.obj.get("json", False)
    pdir = Path(project_dir).resolve()

    if is_echo2d_project(pdir):
        manifest = load_project(pdir)
        runs = list_runs(pdir)
    elif is_legacy_project(pdir):
        manifest = None
        runs = []
    else:
        console.print(
            f"[bold red]Error:[/bold red] No ECHO2D project found at {pdir}"
        )
        raise typer.Exit(1)

    if _json:
        if manifest:
            console.print_json(manifest.model_dump_json(indent=2))
        else:
            console.print_json(json.dumps({
                "name": pdir.name, "type": "legacy", "path": str(pdir),
            }, indent=2))
        return

    # Rich output
    if manifest:
        console.print(
            Panel.fit(
                f"[bold]{manifest.name}[/bold]\n"
                f"  Created:    {manifest.created[:19]}\n"
                f"  Template:   {manifest.template or 'custom'}\n"
                f"  Geometry:   {manifest.geometry_type}\n"
                f"  Runs:       {len(manifest.runs)} total\n"
                f"  Version:    pyecho {manifest.pyecho_version}",
                title="Project Info",
            )
        )
    else:
        console.print(
            Panel.fit(
                f"[bold]{pdir.name}[/bold] [yellow](legacy)[/yellow]\n"
                f"  Path: [dim]{pdir}[/dim]\n\n"
                "Migrate with: [cyan]echo2d project migrate .[/cyan]",
                title="Project Info",
            )
        )
        return

    # List runs
    if runs:
        console.print("\n[bold]Runs:[/bold]")
        run_table = Table()
        run_table.add_column("ID", style="cyan")
        run_table.add_column("Name")
        run_table.add_column("Status")
        run_table.add_column("Symmetries")
        for r in runs:
            syms = ", ".join(sr.symmetry for sr in r.sub_runs)
            status_icon = {
                "completed": "[green]✓[/green]",
                "running": "[yellow]⠇[/yellow]",
                "failed": "[red]✗[/red]",
            }.get(r.status, "[dim]○[/dim]")
            run_table.add_row(r.id, r.name or "—", status_icon, syms)
        console.print(run_table)


@project_app.command("path")
def project_path(
    name: Annotated[str, typer.Argument(help="Project name")],
) -> None:
    """Print the absolute path to a project (useful for 'cd')."""
    from pyecho.project import _get_workspace_root

    ws = _get_workspace_root()
    proj_dir = ws / name
    if not proj_dir.is_dir():
        console.print(f"[bold red]Error:[/bold red] Project '{name}' not found in workspace.")
        raise typer.Exit(1)
    # Print raw path so `cd $(echo2d project path myproj)` works
    console.print(str(proj_dir))


@project_app.command("migrate")
def project_migrate(
    directory: Annotated[
        str,
        typer.Argument(help="Path to legacy project directory"),
    ] = ".",
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview changes without applying"),
    ] = False,
) -> None:
    """Migrate a legacy project to the new project structure.

    Legacy projects are directories with input_in.txt but no
    .echo2d.yaml manifest.  Migration creates the manifest and
    moves existing output into runs/001_legacy/.
    """
    from pyecho.project import migrate_project as _migrate, is_legacy_project

    d = Path(directory).resolve()
    if not is_legacy_project(d):
        console.print(
            f"[yellow]Warning:[/yellow] {d} is not a legacy project "
            "(already migrated or not an ECHO2D project)."
        )
        raise typer.Exit(1)

    if dry_run:
        manifest = _migrate(d, dry_run=True)
        console.print(
            Panel.fit(
                f"[bold]Dry run — would migrate '{d.name}'[/bold]\n\n"
                f"  Detect: [cyan]{manifest.geometry_type}[/cyan] geometry\n"
                f"  Create: .echo2d.yaml\n"
                f"  Move:   output → runs/001_legacy/\n"
                f"  Status: [dim]no changes made[/dim]",
                title="Migration Preview",
            )
        )
        return

    try:
        manifest = _migrate(d)
        console.print(
            Panel.fit(
                f"[bold green]✓[/bold green] Migrated '[cyan]{d.name}[/cyan]'\n\n"
                f"  Created:  .echo2d.yaml\n"
                f"  Geometry: {manifest.geometry_type}\n"
                f"  Output:   → runs/001_legacy/",
                title="Migration Complete",
            )
        )
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] Migration failed: {exc}")
        raise typer.Exit(1)


# ===================================================================
# geometry commands
# ===================================================================
