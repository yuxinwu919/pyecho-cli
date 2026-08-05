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

import json
import logging
import os
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich.syntax import Syntax
from rich.tree import Tree

from pyecho._version import __version__


# ---------------------------------------------------------------------------
# Lazy helpers (used in autocompletion lambdas; import deferred to avoid
# circular dependency issues at module-load time)
# ---------------------------------------------------------------------------

def _get_template_names() -> list[str]:
    """Return registered template names for CLI autocompletion."""
    from pyecho.config import ECHO2DParams
    return ECHO2DParams.list_templates()

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
# Example templates
# ---------------------------------------------------------------------------

_TEMPLATES_DIR = Path(__file__).parent / "templates"

_EXAMPLES: dict[str, dict] = {
    "round-collimator": {
        "description": (
            "Round resistive-wall collimator (N1/N2/N3). "
            "Pipe-step-pipe structure with conductive walls. "
            "Single run with monopole + dipole modes."
        ),
        "geometry": "round_collimator.txt",
        "params": {
            "units": "cm",
            "geometry_type": "round",
            "width": 0.0,
            "symmetry": "magn",
            "bunch_sigma": 0.001,
            "offset": -1,
            "modes": "0 1",
            "mesh_length": 52,
            "step_y": 0.0002,
            "step_z": 0.0002,
            "adjust_mesh": 1,
        },
    },
    "flat-absorber": {
        "description": (
            "Flat photon absorber (N4/N5). "
            "Rectangular step-in/step-out structure. "
            "Runs both magn + elec symmetries automatically."
        ),
        "geometry": "flat_absorber.txt",
        "params": {
            "units": "cm",
            "geometry_type": "recta",
            "width": 0.07,
            "symmetry": "magn",
            "bunch_sigma": 0.004,
            "offset": 0,
            "modes": "1 3 5 7 9 11 13 15",
            "mesh_length": 104,
            "step_y": 0.0008,
            "step_z": 0.0008,
            "adjust_mesh": 0,
        },
    },
    "pohang-dechirper": {
        "description": (
            "Pohang dechirper (N6). "
            "Rectangular corrugated waveguide, 15 odd modes. "
            "Ref: Phys. Rev. STAB 18, 104401 (2015)."
        ),
        "geometry": "pohang_dechirper.txt",
        "params": {
            "units": "cm",
            "geometry_type": "recta",
            "width": 0.05,
            "symmetry": "magn",
            "bunch_sigma": 0.0005,
            "offset": -1,
            "modes": "1 3 5 7 9 11 13 15 17 19 21 23 25 27 29",
            "mesh_length": 200,
            "step_y": 0.0001,
            "step_z": 0.0001,
            "adjust_mesh": 0,
        },
    },
    "tesla-cavity": {
        "description": (
            "9-cell TESLA superconducting cavity (N10). "
            "Elliptical geometry, 40 segments. "
            "Offset=173 for dipole excitation."
        ),
        "geometry": "tesla_cavity.txt",
        "params": {
            "units": "cm",
            "geometry_type": "round",
            "width": 0.0,
            "symmetry": "magn",
            "bunch_sigma": 0.001,
            "offset": 173,
            "modes": "0 1",
            "mesh_length": 52,
            "step_y": 0.00019943,
            "step_z": 0.0002,
            "adjust_mesh": 0,
        },
    },
}


def _print_example_summary(
    out_dir: Path,
    name: str,
    ex: dict,
    result: object = None,
    overrides: dict | None = None,
) -> None:
    """Print a result-summary panel after an example finishes."""
    p = ex["params"].copy()
    if overrides:
        p.update(overrides)

    lines = [
        f"Example:      [bold cyan]{name}[/bold cyan]",
        f"Output dir:   [cyan]{out_dir}[/cyan]",
        f"Geometry:     [cyan]{ex['geometry']}[/cyan]",
        f"Symmetry:     [cyan]{p['symmetry']}[/cyan]",
        f"Bunch sigma:  [cyan]{p['bunch_sigma']} m[/cyan]",
        f"Modes:        [cyan]{p['modes']}[/cyan]",
    ]

    if result is not None:
        from pyecho.datamodel import FlatWakeResult, WakeResult

        if isinstance(result, FlatWakeResult):
            lines.append("")
            lines.append(
                f"  Longitudinal loss: [cyan]{result.loss_long:.6f} V/pC[/cyan]"
            )
            lines.append(
                f"  Quadrupole kick:   [cyan]{result.kick_quad:.6f} V/pC/mm[/cyan]"
            )
            lines.append(
                f"  Dipole kick:       [cyan]{result.kick_dipole:.6f} V/pC/mm[/cyan]"
            )
        elif hasattr(result, "loss_long"):  # RoundWakeResult
            lines.append("")
            lines.append(
                f"  Loss_long:  [cyan]{result.loss_long:.6f} V/pC[/cyan]"
            )
            lines.append(
                f"  Peak:       [cyan]{result.peak:.4f} V/pC[/cyan]"
            )
            if result.Wdipole is not None and result.kick_dipole is not None:
                lines.append(
                    f"  Kick_dipole: [cyan]{result.kick_dipole:.4f} V/pC/m[/cyan]"
                )

    console.print(
        Panel.fit("\n".join(lines), title="Example Complete")
    )


# ---------------------------------------------------------------------------
# Example command
# ---------------------------------------------------------------------------

@app.command("example")
def example_cmd(
    name: Annotated[
        str,
        typer.Argument(
            help="Example name (leave empty to list)",
            autocompletion=lambda: ["list", "ls"] + list(_EXAMPLES.keys()),
        ),
    ] = "",
    output: Annotated[
        Optional[str],
        typer.Option("--output", "-o", help="Output directory"),
    ] = None,
    no_run: Annotated[
        bool,
        typer.Option("--no-run", help="Generate files only, skip simulation"),
    ] = False,
    no_plot: Annotated[
        bool,
        typer.Option("--no-plot", help="Skip wake plots"),
    ] = False,
    preview: Annotated[
        bool,
        typer.Option("--preview", help="Preview steps without executing"),
    ] = False,
    threads: Annotated[
        int,
        typer.Option("--threads", "-j", help="Number of OpenMP threads"),
    ] = 1,
    bunch_sigma: Annotated[
        Optional[float],
        typer.Option("--bunch-sigma", help="Override bunch sigma [m]"),
    ] = None,
    modes: Annotated[
        Optional[str],
        typer.Option(
            "--modes",
            help="Override modes (space-separated, e.g. '0 1')",
        ),
    ] = None,
    symmetry: Annotated[
        Optional[str],
        typer.Option(
            "--symmetry", "-s",
            help="Override symmetry condition: magn, elec",
        ),
    ] = None,
    _np_alias: Annotated[
        Optional[int],
        typer.Option("--np", hidden=True),
    ] = None,
) -> None:
    """Create and run a ready-to-use ECHO2D example.

    \b
    Available examples:
      round-collimator   Round resistive-wall collimator (N1/N2/N3)
      flat-absorber      Flat photon absorber (N4/N5)
      pohang-dechirper   Pohang dechirper (N6)
      tesla-cavity       9-cell TESLA superconducting cavity (N10)

    \b
    Quick start:
      echo2d example list                    # list available examples
      echo2d example                         # same as above
      echo2d example round-collimator        # run with defaults
      echo2d example flat-absorber -o mydemo # custom output dir
      echo2d example tesla-cavity --no-run   # only generate files
    """
    # Merge deprecated --np alias
    if _np_alias is not None:
        threads = _np_alias

    # ── No name → list examples (also accept "list" / "ls" as aliases) ──
    if not name or name in ("list", "ls"):
        table = Table(title="Available Examples")
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Description")
        for ex_name, ex_info in _EXAMPLES.items():
            table.add_row(ex_name, ex_info["description"])
        console.print(table)
        console.print(
            "\n[dim]Run 'echo2d example <name>' to create and run.[/dim]"
        )
        return

    # ── Look up ──
    ex = _EXAMPLES.get(name)
    if ex is None:
        console.print(f"[bold red]Error:[/bold red] Unknown example '{name}'.")
        console.print(f"Available: {', '.join(_EXAMPLES)}")
        raise typer.Exit(1)

    # ── Resolve overrides ──
    p = ex["params"].copy()
    if bunch_sigma is not None:
        p["bunch_sigma"] = bunch_sigma
    if modes is not None:
        p["modes"] = modes
    if symmetry is not None:
        p["symmetry"] = symmetry

    out_dir = Path(output or f"{name}_example")

    # ── Preview ──
    steps = [
        f"Create project [cyan]{out_dir}[/cyan] with .echo2d.yaml",
        f"Create run [cyan]runs/001_{name.replace('-', '_')}/[/cyan]",
        f"Copy geometry [cyan]{ex['geometry']}[/cyan]",
        f"Generate [cyan]input_in.txt[/cyan]",
        f"Run ECHO2D solver ({threads} thread(s))",
        f"Postprocess wake data",
    ]
    if preview:
        lines = "\n".join(
            f"  [bold]Step {i+1}[/bold]  {s}" for i, s in enumerate(steps)
        )
        console.print(Panel.fit(lines, title=f"Example: {name}"))
        return

    # ── Execute ──
    from pyecho.project import (
        ProjectManifest, RunManifest, SubRunInfo,
        save_project, save_run_meta,
    )

    run_name = name.replace("-", "_")
    run_dir = out_dir / "runs" / f"001_{run_name}"

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # Step 1: create project structure
        task = progress.add_task("Creating project structure...", total=None)
        out_dir.mkdir(parents=True, exist_ok=True)
        run_dir.mkdir(parents=True, exist_ok=True)

        gt = p["geometry_type"]
        if gt == "recta":
            sub_runs = [
                SubRunInfo(symmetry="magn", output_dir="magn/"),
                SubRunInfo(symmetry="elec", output_dir="elec/"),
            ]
        else:
            sub_runs = [SubRunInfo(symmetry="magn", output_dir="round/")]

        # Only pre-create processed/ subdirs — ECHO2D creates round/magn/elec
        # automatically.  Pre-creating them causes the parser to shadow the
        # actual output when both magn/ and elec/ exist beforehand.
        for sub in ("wake", "field", "particles"):
            (run_dir / "processed" / sub).mkdir(parents=True, exist_ok=True)

        run_manifest = RunManifest(
            id="001", name=run_name, geometry_type=gt,
            sub_runs=sub_runs, status="pending",
        )
        save_run_meta(run_manifest, run_dir)
        proj_manifest = ProjectManifest(
            name=out_dir.name, template="", geometry_type=gt,
            runs=[run_manifest],
        )
        save_project(proj_manifest, out_dir)

        progress.update(
            task, completed=True,
            description=f"[green]✓[/green] Project [cyan]{out_dir.name}[/cyan]"
        )

        # Step 2: copy geometry
        task = progress.add_task("Copying geometry file...", total=None)
        geo_src = _TEMPLATES_DIR / ex["geometry"]
        if not geo_src.exists():
            console.print(
                f"[red]Template not found: {geo_src}[/red]"
            )
            raise typer.Exit(1)
        geo_dst = run_dir / ex["geometry"]
        geo_dst.write_bytes(geo_src.read_bytes())
        progress.update(
            task, completed=True,
            description="[green]✓[/green] Geometry copied"
        )

        # Step 3: generate input_in.txt
        task = progress.add_task("Generating input_in.txt...", total=None)
        from pyecho.config import ECHO2DParams, save_params
        params = ECHO2DParams(
            GeometryFile=ex["geometry"],
            Units=p["units"],
            GeometryType=p["geometry_type"],
            Width=p["width"],
            SymmetryCondition=p["symmetry"],
            BunchSigma=p["bunch_sigma"],
            Offset=p["offset"],
            Modes=p["modes"],
            MeshLength=p["mesh_length"],
            StepY=p["step_y"],
            StepZ=p["step_z"],
            AdjustMesh=bool(p["adjust_mesh"]),
        )
        save_params(params, run_dir / "input_in.txt")
        progress.update(
            task, completed=True,
            description="[green]✓[/green] input_in.txt generated"
        )

        if no_run:
            progress.stop()
            console.print()
            console.print(
                f"[bold green]✓[/bold green] Project ready in "
                f"[cyan]{out_dir}[/cyan]"
            )
            console.print(
                f"  Run: [dim]cd {out_dir} && "
                f"echo2d run start --threads {threads}[/dim]"
            )
            return

        # Step 4: run ECHO2D (once per symmetry)
        from pyecho.runner import ECHO2DRunner
        from pyecho.project import update_run_status as _upd

        runner = ECHO2DRunner(work_dir=str(run_dir))
        total_elapsed = 0.0
        all_ok = True
        for sr in sub_runs:
            sym = sr.symmetry
            task = progress.add_task(
                f"Running ECHO2D ({sym})...",
                total=None,
            )
            # Update SymmetryCondition in input_in.txt
            input_file = run_dir / "input_in.txt"
            original = input_file.read_text(encoding="utf-8")
            updated = re.sub(
                r"SymmetryCondition=\w+",
                f"SymmetryCondition={sym}",
                original,
            )
            input_file.write_text(updated, encoding="utf-8")

            try:
                sim_result = runner.run(np=threads, show_progress=False)
                t_elapsed = sim_result.metadata.elapsed_seconds
                total_elapsed += t_elapsed

                # Move output files to symmetry subdirectory
                out_subdir = run_dir / sr.output_dir.strip("/")
                out_subdir.mkdir(parents=True, exist_ok=True)
                _collect_output(runner.work_dir, out_subdir, sym)

                _upd(run_dir, sym, "completed", t_elapsed)
                progress.update(
                    task, completed=True,
                    description=f"[green]✓[/green] {sym} done ([dim]{t_elapsed:.1f}s[/dim])",
                )
            except Exception as exc:
                _upd(run_dir, sym, "failed", 0)
                progress.update(
                    task, completed=True,
                    description=f"[red]✗[/red] {sym} failed: {exc}",
                )
                console.print(f"  [red]Error ({sym}): {exc}[/red]")
                all_ok = False
                break
            finally:
                # Restore original input_in.txt
                input_file.write_text(original, encoding="utf-8")

        if not all_ok:
            raise typer.Exit(1)

        # Step 5: postprocess
        task = progress.add_task("Postprocessing wake data...", total=None)
        try:
            from pyecho.api import quick_postprocess
            from pyecho.datamodel import FlatWakeResult, RoundWakeResult

            result = quick_postprocess(str(run_dir), geometry=p["geometry_type"])
            progress.update(
                task, completed=True,
                description="[green]✓[/green] Postprocessing done",
            )
        except Exception as exc:
            progress.update(
                task, completed=True,
                description="[yellow]⚠[/yellow] Postprocess warning",
            )
            # Print the full warning outside the progress bar to avoid truncation
            console.print(f"  [yellow]⚠ Warning:[/yellow] {exc}")
            result = None

    # ── Summary ──
    console.print()
    _print_example_summary(out_dir, name, ex, result, p)

    # ── Plot (if requested) ──
    if not no_plot and result is not None:
        console.print("[dim]Launching plot...[/dim]")
        try:
            import matplotlib.pyplot as plt
            wake_out = run_dir / "processed" / "wake"
            wake_out.mkdir(parents=True, exist_ok=True)

            if isinstance(result, FlatWakeResult):
                from pyecho.visualize import plot_flat_wake
                data_dir = _resolve_plot_data_dir(str(run_dir))
                offset = _read_offset_from_dir(data_dir)
                from pyecho.parser import load_bunch_profile
                _, bunch = load_bunch_profile(data_dir, offset, result.s)
                fig, axes = plot_flat_wake(result, bunch=bunch)
                save_path = wake_out / "wake_plot.png"
                fig.savefig(str(save_path), dpi=150, bbox_inches="tight")
                console.print(f"  [dim]Plot saved to {save_path}[/dim]")
                plt.show()
            else:
                from pyecho.visualize import plot_round_wake
                fig, axes = plot_round_wake(result)
                save_path = wake_out / "wake_plot.png"
                fig.savefig(str(save_path), dpi=150, bbox_inches="tight")
                console.print(f"  [dim]Plot saved to {save_path}[/dim]")
                plt.show()
        except Exception as exc:
            console.print(f"[yellow]Warning:[/yellow] Plot error: {exc}")


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
    (~/echo2d_projects/).  Use --here to create in the current
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
        "flat_absorber": "Rectangular photon absorber (flat)",
        "tesla_cavity": "TESLA 9-cell superconducting cavity",
        "dlw": "Dielectric lined waveguide (DLW)",
    }

    for t in templates:
        gtype = "Flat" if "flat" in t or t == "dlw" else "Round"
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
            desc = "Flat/rectangular geometry example"
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

    By default, scans the workspace (~/echo2d_projects/).
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

@geometry_app.command("create")
def geometry_create(
    name: Annotated[str, typer.Argument(help="Geometry name")],
    structure: Annotated[
        str,
        typer.Option(
            "--structure", "-s",
            help="Structure type: pipe, dlw, corrugated",
            autocompletion=lambda: ["pipe", "dlw", "corrugated"],
        ),
    ] = "pipe",
    from_segments: Annotated[
        Optional[str],
        typer.Option("--segments", help="Custom segment specification"),
    ] = None,
    output: Annotated[
        Optional[str],
        typer.Option("--output", "-o", help="Output file path"),
    ] = None,
    # ── pipe parameters ──
    radius: Annotated[
        float,
        typer.Option(
            "--radius", "-r",
            help="Pipe radius / half-gap [cm] (outer section)",
        ),
    ] = 2.0,
    inner_radius: Annotated[
        float,
        typer.Option(
            "--inner-radius", "-i",
            help="Inner radius / half-gap [cm] (narrow section)",
        ),
    ] = 1.0,
    section_length: Annotated[
        float,
        typer.Option(
            "--section-length", "-l",
            help="Length of each section [cm]",
        ),
    ] = 5.0,
    # ── dlw parameters ──
    half_gap: Annotated[
        float,
        typer.Option("--half-gap", help="DLW half-gap a [mm] (vacuum region)"),
    ] = 5.0,
    thickness: Annotated[
        float,
        typer.Option("--thickness", help="DLW dielectric thickness d [mm]"),
    ] = 2.0,
    length: Annotated[
        float,
        typer.Option("--length", help="Structure length L [mm]"),
    ] = 80.0,
    epsilon_r: Annotated[
        float,
        typer.Option("--epsilon", help="Dielectric relative permittivity εᵣ"),
    ] = 5.6,
    # ── corrugated parameters ──
    gap: Annotated[
        float,
        typer.Option("--gap", help="Corrugated half-gap a [mm]"),
    ] = 5.0,
    depth: Annotated[
        float,
        typer.Option("--depth", help="Corrugation depth h [mm]"),
    ] = 2.0,
    corr_gap: Annotated[
        float,
        typer.Option("--corr-gap", help="Corrugation gap g [mm] (narrow region)"),
    ] = 3.0,
    period: Annotated[
        float,
        typer.Option("--period", help="Corrugation period p [mm]"),
    ] = 5.0,
    num_periods: Annotated[
        int,
        typer.Option("--periods", help="Number of corrugation periods"),
    ] = 10,
) -> None:
    """Create an ECHO2D geometry file.

    The geometry file format is universal (z, r/y coordinates).
    Whether it's interpreted as round or rectangular is controlled
    by ``GeometryType`` in ``input_in.txt``, not by this file.

    \b
    Structure types:
      pipe       — simple pipe-step-pipe (default)
      dlw        — dielectric-lined waveguide
      corrugated — corrugated (dechirper) waveguide, periodic
    """
    out_path = Path(output or f"{name}.txt")

    if structure in ("dlw",):
        _write_dlw_geometry(
            out_path, half_gap=half_gap, thickness=thickness,
            length=length, epsilon_r=epsilon_r,
        )
        console.print(
            f"[bold green]✓[/bold green] DLW geometry saved to "
            f"[cyan]{out_path}[/cyan]"
        )
        console.print(
            f"   a={half_gap} mm  d={thickness} mm  "
            f"L={length} mm  εᵣ={epsilon_r}"
        )
        return

    if structure in ("corrugated",):
        _generate_corrugated_geometry(
            out_path, gap=gap, depth=depth, corr_gap=corr_gap,
            period=period, num_periods=num_periods,
        )
        console.print(
            f"[bold green]✓[/bold green] Corrugated geometry saved to "
            f"[cyan]{out_path}[/cyan]"
        )
        console.print(
            f"   a={gap} mm  h={depth} mm  g={corr_gap} mm  "
            f"p={period} mm  N={num_periods}"
        )
        return

    # Default: pipe-step-pipe (works for both round and recta)
    if from_segments:
        _write_pipe_from_segments(out_path, from_segments)
        console.print(
            f"[bold green]✓[/bold green] Geometry saved to "
            f"[cyan]{out_path}[/cyan]"
        )
        console.print(f"   Custom segments: {from_segments}")
    else:
        _write_pipe_default(out_path, radius, inner_radius, section_length)
        console.print(
            f"[bold green]✓[/bold green] Geometry saved to "
            f"[cyan]{out_path}[/cyan]"
        )
        console.print(
            f"   outer={radius} cm → inner={inner_radius} cm → "
            f"outer={radius} cm,  each section {section_length} cm"
        )


@geometry_app.command("validate")
def geometry_validate(
    geometry_file: Annotated[str, typer.Argument(help="Geometry file path")],
    config: Annotated[
        Optional[str],
        typer.Option("--config", "-c", help="input_in.txt for cross-checking Units/GeometryType"),
    ] = None,
) -> None:
    """Validate a geometry file.

    The geometry file contains raw (z, r) coordinates.  Units are
    specified in ``input_in.txt`` (not in the geometry file itself).
    Use ``--config`` to cross-check geometry type and units.
    """
    from pyecho.geometry import load_geometry

    try:
        geo = load_geometry(geometry_file)
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] Validation failed: {exc}")
        raise typer.Exit(1)

    n_seg = len(geo.get("segments", []))
    n_mat = len(geo.get("materials", []))

    lines = [
        f"[bold green]✓[/bold green] Geometry is valid.",
        f"  Materials: {n_mat}",
        f"  Segments:  {n_seg}",
    ]

    if config:
        from pyecho.config import load_params
        try:
            params = load_params(config)
            lines.append("")
            lines.append(f"  [dim]Config Units:       {params.Units}[/dim]")
            lines.append(f"  [dim]Config GeometryType: {params.GeometryType}[/dim]")
        except Exception as exc:
            lines.append(f"  [yellow]Warning:[/yellow] Could not read config: {exc}")

    console.print(Panel.fit("\n".join(lines), title="Validation Result"))


@geometry_app.command("show")
def geometry_show(
    geometry_file: Annotated[str, typer.Argument(help="Geometry file path")],
    units: Annotated[
        str,
        typer.Option("--units", "-u", help="Display units: cm, mm, m"),
    ] = "cm",
    output: Annotated[
        Optional[str],
        typer.Option("--output", "-o", help="Save plot to file"),
    ] = None,
    no_show: Annotated[
        bool,
        typer.Option("--no-show", help="Do not display plot window"),
    ] = False,
) -> None:
    """Visualize geometry."""
    from pyecho.visualize import plot_geometry

    try:
        fig, ax = plot_geometry(geometry_file, units=units)
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] Failed to plot geometry: {exc}")
        raise typer.Exit(1)

    if output:
        fig.savefig(output, dpi=150, bbox_inches="tight")
        console.print(f"[green]Plot saved to {output}[/green]")

    if not no_show:
        import matplotlib.pyplot as plt
        plt.show()


@geometry_app.command("info")
def geometry_info(
    ctx: typer.Context,
    geometry_file: Annotated[str, typer.Argument(help="Geometry file path")],
) -> None:
    """Show geometry information."""
    # Support global --json flag for machine-readable output
    _json = ctx.obj.get("json", False)

    from pyecho.geometry import load_geometry

    try:
        geo = load_geometry(geometry_file)
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] Failed to load geometry: {exc}")
        raise typer.Exit(1)

    if _json:
        console.print_json(json.dumps(_serialize_geo(geo), indent=2))
        return

    console.print(Panel.fit(f"[bold]Geometry: {Path(geometry_file).name}[/bold]"))

    for i, mat in enumerate(geo.get("materials", [])):
        console.print(f"\n[bold cyan]Material {i + 1}[/bold cyan]")
        console.print(f"  ε = {mat['epsilon']}, μ = {mat['mu']}, σ = {mat['sigma']}")
        console.print(f"  Segments: {len(mat.get('segments', []))}")

        for j, seg_idx in enumerate(mat.get("segments", [])[:5]):
            seg = geo["segments"][seg_idx]
            console.print(
                f"    [{j}] z: {seg['z1']:.3f} → {seg['z2']:.3f}, "
                f"r: {seg['r1']:.3f} → {seg['r2']:.3f}"
            )
        if len(mat.get("segments", [])) > 5:
            console.print(f"    ... and {len(mat['segments']) - 5} more")


# ===================================================================
# config commands
# ===================================================================

@config_app.command("generate")
def config_generate(
    template: Annotated[
        str,
        typer.Option(
            "--template", "-t", help="Template name",
            autocompletion=lambda: _get_template_names(),
        ),
    ] = "round_collimator",
    output: Annotated[
        str,
        typer.Option("--output", "-o", help="Output file"),
    ] = "input_in.txt",
    geometry_file: Annotated[
        Optional[str],
        typer.Option("--geometry", "-g", help="Geometry file name"),
    ] = None,
    sigma: Annotated[
        Optional[float],
        typer.Option("--sigma", "-s", help="Bunch RMS length [m]"),
    ] = None,
    modes: Annotated[
        Optional[str],
        typer.Option("--modes", "-m", help="Modes (space-separated)"),
    ] = None,
    step_y: Annotated[
        Optional[float],
        typer.Option("--step-y", help="Transverse mesh step [m]"),
    ] = None,
    step_z: Annotated[
        Optional[float],
        typer.Option("--step-z", help="Longitudinal mesh step [m]"),
    ] = None,
) -> None:
    """Generate input_in.txt from a template."""
    from pyecho.config import ECHO2DParams, save_params

    overrides: dict = {}
    if geometry_file is not None:
        overrides["GeometryFile"] = geometry_file
    if sigma is not None:
        overrides["BunchSigma"] = sigma
    if modes is not None:
        overrides["Modes"] = [int(m) for m in modes.split()]
    if step_y is not None:
        overrides["StepY"] = step_y
    if step_z is not None:
        overrides["StepZ"] = step_z

    try:
        params = ECHO2DParams.from_template(template, **overrides)
    except ValueError as exc:
        console.print(f"[red]Error: {exc}[/red]")
        console.print(f"[dim]Available templates: {ECHO2DParams.list_templates()}[/dim]")
        raise typer.Exit(1)

    save_params(params, output)

    console.print(f"[bold green]✓[/bold green] Configuration saved to [cyan]{output}[/cyan]")

    # Show preview
    syntax = Syntax(params.to_input_file(), "ini", theme="monokai", line_numbers=False)
    console.print(Panel(syntax, title="Preview"))


@config_app.command("validate")
def config_validate(
    input_file: Annotated[
        Optional[str],
        typer.Argument(help="Input file path (auto-detected in project context)"),
    ] = None,
) -> None:
    """Validate input_in.txt.

    If no file is specified, searches for input_in.txt in:
    1. Current directory
    2. Nearest runs/*/ directory (project context)
    """
    from pyecho.config import load_params
    from pyecho.project import find_project_root as _find_proj

    # Auto-detect input_in.txt
    target = _resolve_input_file(input_file)
    if target is None:
        console.print(
            "[bold red]Error:[/bold red] No input_in.txt found.\n"
            "Specify the file path, or run from a project directory.\n"
            "Generate one with: [cyan]echo2d config generate[/cyan]"
        )
        raise typer.Exit(1)

    try:
        params = load_params(target)
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] Validation failed: {exc}")
        raise typer.Exit(1)

    console.print(
        Panel.fit(
            f"[bold green]✓[/bold green] Configuration is valid.\n"
            f"  File:     [dim]{target}[/dim]\n"
            f"  Geometry: {params.GeometryFile} ({params.GeometryType})\n"
            f"  Bunch σ:  {params.BunchSigma} m\n"
            f"  Modes:    {params.Modes}\n"
            f"  Mesh:     h_y={params.StepY}, h_z={params.StepZ}",
            title="Validation Result",
        )
    )


@config_app.command("show")
def config_show(
    ctx: typer.Context,
    input_file: Annotated[
        Optional[str],
        typer.Argument(help="Input file path (auto-detected in project context)"),
    ] = None,
) -> None:
    """Display configuration."""
    # Support global --json flag for machine-readable output
    _json = ctx.obj.get("json", False)

    from pyecho.config import load_params

    target = _resolve_input_file(input_file)
    if target is None:
        console.print(
            "[bold red]Error:[/bold red] No input_in.txt found.\n"
            "Specify the file path, or run from a project directory."
        )
        raise typer.Exit(1)

    try:
        params = load_params(target)
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] Failed to parse {target}: {exc}")
        raise typer.Exit(1)

    if _json:
        console.print_json(params.model_dump_json(indent=2))
        return

    table = Table(title=f"Configuration: {target}")
    table.add_column("Parameter", style="cyan")
    table.add_column("Value", style="green")

    for field_name in params.model_fields:
        val = getattr(params, field_name)
        if isinstance(val, list):
            val = " ".join(str(x) for x in val)
        table.add_row(field_name, str(val))

    console.print(table)


# ===================================================================
# run commands
# ===================================================================
# Phase 2: run new / start / list / info integrate with the project
# management framework.  run single is kept for backward compatibility
# with legacy (flat-directory) workflows.

@run_app.command("new")
def run_new(
    name: Annotated[
        Optional[str],
        typer.Option("--name", "-n", help="Human-readable label for this run"),
    ] = None,
    from_run: Annotated[
        Optional[str],
        typer.Option("--from", "-f", help="Copy configuration from run ID (default: latest)"),
    ] = None,
    template: Annotated[
        Optional[str],
        typer.Option(
            "--template", "-t", help="Create fresh from template (overrides --from)",
            autocompletion=lambda: _get_template_names(),
        ),
    ] = None,
    project: Annotated[
        Optional[str],
        typer.Option("--project", "-p", help="Project name (auto-detected if in a project directory)"),
    ] = None,
) -> None:
    """Create a new simulation run in a project.

    Copies input_in.txt and geometry from the latest run (or --from).
    Use --template to start fresh from a template.
    """
    from pyecho.project import (
        find_project_root, create_new_run, _get_workspace_root,
    )

    # Find project
    proj_dir: Path | None = None
    if project:
        proj_dir = _get_workspace_root() / project
        if not proj_dir.is_dir():
            console.print(f"[bold red]Error:[/bold red] Project '{project}' not found.")
            raise typer.Exit(1)
    else:
        proj_dir = find_project_root()
        if proj_dir is None:
            console.print(
                "[bold red]Error:[/bold red] Not inside an ECHO2D project. "
                "Use --project to specify one."
            )
            raise typer.Exit(1)

    try:
        run = create_new_run(
            proj_dir,
            name=name or "",
            from_run=from_run,
            template=template or "",
        )
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(1)

    run_dir = proj_dir / "runs" / run.dir_name
    console.print(
        Panel.fit(
            f"[bold green]✓[/bold green] Run [cyan]{run.dir_name}[/cyan] created\n"
            f"  Project:  [dim]{proj_dir.name}[/dim]\n"
            f"  Type:     {run.geometry_type}\n"
            f"  Sub-runs: {', '.join(sr.symmetry for sr in run.sub_runs)}\n\n"
            f"  [dim]cd {run_dir}  &&  echo2d run start[/dim]",
            title="New Run",
        )
    )


@run_app.command("start")
def run_start(
    run_id: Annotated[
        Optional[str],
        typer.Argument(help="Run ID to execute (default: latest in current project)"),
    ] = None,
    symmetry: Annotated[
        Optional[str],
        typer.Option("--symmetry", "-s", help="Run only this symmetry: magn or elec"),
    ] = None,
    threads: Annotated[
        int,
        typer.Option("--threads", "-j", help="Number of OpenMP threads"),
    ] = 1,
    timeout: Annotated[
        Optional[int],
        typer.Option("--timeout", "-t", help="Timeout in seconds"),
    ] = None,
    executable: Annotated[
        Optional[str],
        typer.Option("--exe", "-e", help="ECHO2D executable path"),
    ] = None,
) -> None:
    """Start an ECHO2D simulation for a run.

    For round geometry, runs once with magn symmetry.
    For recta geometry, runs magn then elec automatically.
    Use --symmetry to run only one of them.
    """
    from pyecho.project import (
        find_project_root, load_run_meta, update_run_status, _get_workspace_root,
    )
    from pyecho.runner import ECHO2DRunner

    # Find project and run
    proj_dir = find_project_root()
    if proj_dir is None:
        console.print("[bold red]Error:[/bold red] Not inside an ECHO2D project.")
        raise typer.Exit(1)

    runs_dir = proj_dir / "runs"
    if run_id:
        target_dir = None
        for child in sorted(runs_dir.iterdir()):
            if child.is_dir() and child.name.startswith(run_id):
                target_dir = child
                break
        if target_dir is None:
            console.print(f"[bold red]Error:[/bold red] Run '{run_id}' not found.")
            raise typer.Exit(1)
    else:
        dirs = sorted(
            [d for d in runs_dir.iterdir() if d.is_dir() and (d / ".run.yaml").is_file()],
            key=lambda x: x.name, reverse=True,
        )
        if not dirs:
            console.print("[bold red]Error:[/bold red] No runs found. Create one with 'echo2d run new'.")
            raise typer.Exit(1)
        target_dir = dirs[0]

    meta = load_run_meta(target_dir)

    # Filter sub-runs if --symmetry specified
    to_run = meta.sub_runs
    if symmetry:
        to_run = [sr for sr in to_run if sr.symmetry == symmetry]
        if not to_run:
            console.print(f"[bold red]Error:[/bold red] Symmetry '{symmetry}' not in run configuration.")
            raise typer.Exit(1)

    console.print(
        Panel.fit(
            f"[bold]Starting run [cyan]{meta.dir_name}[/cyan][/bold]\n"
            f"  Project:  [dim]{proj_dir.name}[/dim]\n"
            f"  Type:     {meta.geometry_type}\n"
            f"  Steps:    {', '.join(sr.symmetry for sr in to_run)}\n"
            f"  Threads:  {threads}",
            title="Simulation",
        )
    )

    # Execute each sub-run
    overall_ok = True
    for sr in to_run:
        sym = sr.symmetry
        out_subdir = target_dir / sr.output_dir.strip("/")
        out_subdir.mkdir(parents=True, exist_ok=True)

        console.print(f"\n[bold]▶ Running {sym}…[/bold]")

        # Set SymmetryCondition in input_in.txt for this sub-run
        input_file = target_dir / "input_in.txt"
        if not input_file.is_file():
            console.print(f"[bold red]Error:[/bold red] No input_in.txt in {target_dir}")
            raise typer.Exit(1)

        # Read and update symmetry
        original = input_file.read_text(encoding="utf-8")
        if f"SymmetryCondition={sym}" not in original:
            import re
            updated = re.sub(
                r"SymmetryCondition=\w+",
                f"SymmetryCondition={sym}",
                original,
            )
            input_file.write_text(updated, encoding="utf-8")

        # Verify geometry file is present in the run directory
        from pyecho.config import load_params as _load_params
        try:
            params = _load_params(input_file)
            geom_name = params.GeometryFile
            if geom_name and geom_name != "-":
                geom_in_run = target_dir / geom_name
                if not geom_in_run.is_file():
                    # Try to find it: templates dir, project root, or adjacent to input
                    _copied = _copy_geometry_to_run(target_dir, geom_name, proj_dir)
                    if not _copied:
                        console.print(
                            f"[bold red]Error:[/bold red] Geometry file "
                            f"'{geom_name}' not found in {target_dir}.\n"
                            f"Place the geometry file in the run directory "
                            f"or use [cyan]echo2d config generate[/cyan] "
                            f"to recreate input_in.txt."
                        )
                        raise typer.Exit(1)
        except Exception:
            pass  # If we can't parse params, let ECHO2D report the error

        # Run ECHO2D
        t_start = time.time()
        try:
            runner = ECHO2DRunner(target_dir, executable)

            # Use run_stream with Rich progress bar (same as run single)
            gen = runner.run_stream(params=None, np=threads, timeout=timeout)
            result = None
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]ECHO2D {task.fields[sym]}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>5.0f}%"),
                TimeElapsedColumn(),
                console=console,
            ) as pbar:
                task = pbar.add_task(
                    "Simulating...", total=100, sym=sym,
                )
                while True:
                    try:
                        update = next(gen)
                        pct = min(float(update.get("percent", 0)), 100)
                        pbar.update(
                            task, completed=pct,
                            description="",
                        )
                    except StopIteration as exc:
                        result = exc.value
                        break
                pbar.update(task, completed=100)

            elapsed = time.time() - t_start

            # Collect output files produced in work_dir into subdirectory
            _collect_output(runner.work_dir, out_subdir, sym)

            update_run_status(target_dir, sym, "completed", elapsed)
            console.print(f"  [green]✓ {sym} completed in {elapsed:.1f}s[/green]")
        except Exception as exc:
            update_run_status(target_dir, sym, "failed", time.time() - t_start)
            console.print(f"  [red]✗ {sym} failed: {exc}[/red]")
            overall_ok = False
            break
        finally:
            # Restore original input
            input_file.write_text(original, encoding="utf-8")

    if overall_ok:
        console.print(f"\n[bold green]✓ Run {meta.dir_name} completed.[/bold green]")
        console.print(
            f"[dim]Next: echo2d postprocess wake {target_dir}/[/dim]"
        )
    else:
        console.print(f"\n[bold red]✗ Run {meta.dir_name} failed.[/bold red]")
        raise typer.Exit(1)


@run_app.command("list")
def run_list(
    ctx: typer.Context,
    project: Annotated[
        Optional[str],
        typer.Option("--project", "-p", help="Project name (auto-detected if in a project directory)"),
    ] = None,
) -> None:
    """List all runs in a project."""
    from pyecho.project import find_project_root, list_runs as _list_runs, _get_workspace_root

    _json = ctx.obj.get("json", False)

    proj_dir: Path | None = None
    if project:
        proj_dir = _get_workspace_root() / project
    else:
        proj_dir = find_project_root()

    if proj_dir is None or not proj_dir.is_dir():
        console.print("[bold red]Error:[/bold red] No project found.")
        raise typer.Exit(1)

    runs = _list_runs(proj_dir)

    if _json:
        console.print_json(json.dumps(
            [r.model_dump(mode="json") for r in runs], indent=2, default=str
        ))
        return

    if not runs:
        console.print("[yellow]No runs yet.[/yellow] Create one with [cyan]echo2d run new[/cyan]")
        return

    table = Table(title=f"Runs — {proj_dir.name}")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Status")
    table.add_column("Type")
    table.add_column("Symmetries")
    table.add_column("Duration", justify="right")

    for r in runs:
        syms = ", ".join(sr.symmetry for sr in r.sub_runs)
        status_icon = {
            "completed": "[green]✓[/green]",
            "running": "[yellow]⠇[/yellow]",
            "failed": "[red]✗[/red]",
        }.get(r.status, "[dim]○[/dim]")
        dur = f"{r.total_duration_s:.0f}s" if r.total_duration_s > 0 else "—"
        table.add_row(r.id, r.name or "—", status_icon, r.geometry_type, syms, dur)

    console.print(table)


@run_app.command("info")
def run_info(
    ctx: typer.Context,
    run_id: Annotated[str, typer.Argument(help="Run ID (e.g. 001)")],
    project: Annotated[
        Optional[str],
        typer.Option("--project", "-p", help="Project name"),
    ] = None,
) -> None:
    """Show detailed information about a specific run."""
    from pyecho.project import find_project_root, load_run_meta, _get_workspace_root

    _json = ctx.obj.get("json", False)

    proj_dir: Path | None = None
    if project:
        proj_dir = _get_workspace_root() / project
    else:
        proj_dir = find_project_root()

    if proj_dir is None:
        console.print("[bold red]Error:[/bold red] No project found.")
        raise typer.Exit(1)

    runs_dir = proj_dir / "runs"
    target_dir = None
    for child in runs_dir.iterdir():
        if child.is_dir() and child.name.startswith(run_id):
            target_dir = child
            break

    if target_dir is None:
        console.print(f"[bold red]Error:[/bold red] Run '{run_id}' not found.")
        raise typer.Exit(1)

    meta = load_run_meta(target_dir)

    if _json:
        console.print_json(meta.model_dump_json(indent=2))
        return

    console.print(
        Panel.fit(
            f"[bold]{meta.dir_name}[/bold]\n"
            f"  ID:        {meta.id}\n"
            f"  Name:      {meta.name or '—'}\n"
            f"  Created:   {meta.created[:19]}\n"
            f"  Geometry:  {meta.geometry_type}\n"
            f"  Status:    {meta.status}",
            title="Run Info",
        )
    )

    if meta.sub_runs:
        console.print("\n[bold]Sub-runs:[/bold]")
        sr_table = Table()
        sr_table.add_column("Symmetry", style="cyan")
        sr_table.add_column("Status")
        sr_table.add_column("Duration", justify="right")
        sr_table.add_column("Output", style="dim")
        for sr in meta.sub_runs:
            status_icon = {
                "completed": "[green]✓[/green]",
                "failed": "[red]✗[/red]",
                "running": "[yellow]⠇[/yellow]",
            }.get(sr.status, "[dim]○[/dim]")
            dur = f"{sr.duration_s:.1f}s" if sr.duration_s > 0 else "—"
            sr_table.add_row(sr.symmetry, status_icon, dur, sr.output_dir)
        console.print(sr_table)

    input_file = target_dir / "input_in.txt"
    if input_file.is_file():
        console.print(f"\n[dim]Input: {input_file}[/dim]")


@run_app.command("single")
def run_single(
    work_dir: Annotated[
        str,
        typer.Option("--work-dir", "-d", help="Working directory"),
    ] = ".",
    config: Annotated[
        Optional[str],
        typer.Option("--config", "-c", help="Input file path"),
    ] = None,
    np: Annotated[
        int,
        typer.Option("--threads", "-j",
                     help="Number of OpenMP threads. "
                          "(Alias --np kept for backward compatibility.)"),
    ] = 1,
    _np_alias: Annotated[
        Optional[int],
        typer.Option("--np", hidden=True,
                     help="Backward-compatible alias for --threads."),
    ] = None,
    timeout: Annotated[
        Optional[int],
        typer.Option("--timeout", "-t", help="Timeout in seconds"),
    ] = None,
    executable: Annotated[
        Optional[str],
        typer.Option("--exe", "-e", help="ECHO2D executable path"),
    ] = None,
    no_progress: Annotated[
        bool,
        typer.Option("--no-progress", help="Hide progress output"),
    ] = False,
    preview: Annotated[
        bool,
        typer.Option("--preview", help="Show what would be executed"),
    ] = False,
) -> None:
    """Run a single ECHO2D simulation (legacy mode).

    For new projects, prefer [cyan]echo2d run new[/cyan] and
    [cyan]echo2d run start[/cyan].

    .. note::

       This command is kept for backward compatibility with pre-Phase-2
       flat-directory workflows and ad-hoc simulations.  It works with
       any directory that contains an ``input_in.txt`` file, without
       requiring a ``.echo2d.yaml`` project manifest.  When used inside
       a project, consider ``echo2d run start`` instead — it
       automatically handles symmetries and updates run metadata.

       Do NOT add new features to this command.  New functionality
       should go into ``run new`` / ``run start`` / ``run list``.
    """
    # NOTE(legacy): This function is frozen — do not enhance.
    # All new run-management features go through the Phase 2 commands
    # (run new / start / list / info) which integrate with the project
    # manifest system.  This command exists solely so that users with
    # existing flat-directory workflows are not broken.
    from pyecho.runner import ECHO2DRunner
    from pyecho.config import load_params

    wdir = Path(work_dir).resolve()
    params = None
    if config:
        params = load_params(config)
    elif (wdir / "input_in.txt").exists():
        params = load_params(wdir / "input_in.txt")
    else:
        console.print(
            "[bold red]Error:[/bold red] No input_in.txt found and no --config specified.\n"
            "Generate one with: [cyan]echo2d config generate[/cyan]"
        )
        raise typer.Exit(1)

    if preview:
        console.print(Panel.fit(
            f"Working dir: [cyan]{wdir}[/cyan]\n"
            f"Executable:  [cyan]{executable or 'auto-detect'}[/cyan]\n"
            f"Threads:     [cyan]{np}[/cyan]\n"
            f"Config:      [cyan]{config or 'input_in.txt'}[/cyan]",
            title="Preview",
        ))
        return

    if _np_alias is not None:
        np = _np_alias

    try:
        runner = ECHO2DRunner(wdir, executable)
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] Failed to initialize runner: {exc}")
        raise typer.Exit(1)

    console.print(
        Panel.fit(
            f"[bold]Running ECHO2D[/bold]\n"
            f"  Directory:  [cyan]{wdir}[/cyan]\n"
            f"  Executable: [cyan]{runner.executable}[/cyan]\n"
            f"  Threads:    [cyan]{np}[/cyan]",
            title="Simulation",
        )
    )

    try:
        if no_progress:
            result = runner.run(params=params, np=np, timeout=timeout,
                                show_progress=False)
        else:
            gen = runner.run_stream(params=params, np=np, timeout=timeout)
            result = None
            from rich.progress import Progress as RichProgress, BarColumn, \
                TextColumn as RichTextCol, TimeElapsedColumn
            with RichProgress(
                RichTextCol("[bold blue]ECHO2D"),
                BarColumn(),
                RichTextCol("[progress.percentage]{task.percentage:>5.0f}%"),
                TimeElapsedColumn(),
                console=console,
            ) as pbar:
                task = pbar.add_task("Simulating...", total=100)
                while True:
                    try:
                        update = next(gen)
                        pct = min(float(update.get("percent", 0)), 100)
                        pbar.update(task, completed=pct,
                                    description=update.get("message", "")[:40])
                    except StopIteration as exc:
                        result = exc.value
                        break
                pbar.update(task, completed=100, description="Simulation complete")
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] Simulation failed: {exc}")
        raise typer.Exit(1)

    console.print(
        Panel.fit(
            f"[bold green]✓ Simulation completed[/bold green]\n"
            f"  Elapsed:    [cyan]{result.metadata.elapsed_seconds:.1f} s[/cyan]\n"
            f"  Modes:      [cyan]{list(result.modes.keys())}[/cyan]\n"
            f"  Output:     [cyan]{result.output_dir}[/cyan]",
            title="Result",
        )
    )


@run_app.command("batch")
def run_batch(
    config_file: Annotated[str, typer.Argument(help="Batch config (YAML/JSON)")],
    parallel: Annotated[
        int,
        typer.Option("--parallel", "-p", help="Number of parallel runs"),
    ] = 1,
    resume: Annotated[
        bool,
        typer.Option("--resume", help="Resume from previous run"),
    ] = False,
) -> None:
    """Run a parameter sweep from a batch configuration file.

    .. note::

        This command is a **placeholder** — the batch-sweep engine has
        not been implemented yet.  For now use ``echo2d run single``
        inside a shell loop or a Python script that calls
        :func:`pyecho.runner.ECHO2DRunner`.

        Planned features:
        - YAML/JSON sweep definitions
        - Parallel execution with ``--parallel``
        - Resume support for interrupted sweeps
    """
    console.print(Panel.fit(
        "[bold yellow]⏳  Planned feature[/bold yellow]\n\n"
        "Batch parameter sweeps are not yet implemented.\n\n"
        "Workaround: use a shell loop or Python script calling\n"
        "[cyan]ECHO2DRunner[/cyan] directly.\n\n"
        "Expected: [cyan]echo2d v0.2.0[/cyan]",
        title="Batch Runner",
    ))


@run_app.command("converge")
def run_converge(
    project: Annotated[
        Optional[str],
        typer.Option("--project", "-p", help="Project name or path (auto-detected if in project dir)"),
    ] = None,
    mesh_factors: Annotated[
        str,
        typer.Option("--mesh-factors", "-m", help="Space-separated mesh step factors (e.g. '2.0 1.0 0.5')"),
    ] = "2.0 1.0 0.5",
    modes: Annotated[
        Optional[str],
        typer.Option("--modes", help="Modes to compute (default: from base config)"),
    ] = None,
    threads: Annotated[
        int,
        typer.Option("--threads", "-j", help="OpenMP threads per run"),
    ] = 1,
) -> None:
    """Run an automated mesh-convergence study.

    Given a project with existing geometry + bunch configuration,
    runs ECHO2D at multiple mesh resolutions and reports the
    convergence of the loss factor.

    \\b
    How it works:
      1. Reads base mesh from the latest run in the project
      2. Scales StepY/StepZ by each mesh factor
      3. Runs ECHO2D + postprocessing for each resolution
      4. Reports loss factor at each mesh, checks <5% convergence

    \\b
    Examples:
      echo2d run converge -p myproj
      echo2d run converge -p myproj -m "2.0 1.0 0.5 0.25" -j 4
      echo2d run converge -p myproj --modes "0 1"
    """
    from pyecho.project import find_project_root, _get_workspace_root
    from pyecho.converge import run_convergence as _run_conv

    # Resolve project
    proj_dir: Path | None = None
    if project:
        proj_dir = _get_workspace_root() / project
        if not proj_dir.is_dir():
            proj_dir = Path(project).resolve()
    else:
        proj_dir = find_project_root()

    if proj_dir is None or not (proj_dir / ".echo2d.yaml").is_file():
        console.print("[red]Error: Not in an ECHO2D project. Use --project to specify one.[/red]")
        raise typer.Exit(1)

    console.print(
        Panel.fit(
            f"Project:     [cyan]{proj_dir.name}[/cyan]\n"
            f"Mesh factors: [cyan]{mesh_factors}[/cyan]\n"
            f"Threads:     [cyan]{threads}[/cyan]",
            title="Convergence Study",
        )
    )

    try:
        report = _run_conv(
            project=str(proj_dir),
            mesh_factors=mesh_factors,
            modes=modes,
            threads=threads,
        )
    except Exception as exc:
        console.print(f"[red]Error: Convergence study failed: {exc}[/red]")
        raise typer.Exit(1)

    # Rich table summary
    table = Table(title="Convergence Results")
    table.add_column("Mesh", style="cyan")
    table.add_column("h_y [m]", style="yellow")
    table.add_column("h_z [m]", style="yellow")
    table.add_column("Loss [V/pC]", style="green")
    table.add_column("Time", justify="right")
    for p in report.points:
        loss_str = f"{p.loss_factor:.6f}" if p.loss_factor is not None else "[red]FAILED[/red]"
        table.add_row(p.label, f"{p.step_y:.2e}", f"{p.step_z:.2e}", loss_str, f"{p.elapsed_s:.1f}s")
    console.print(table)

    if report.converged:
        console.print("\n[green]✓ Converged (<5% between finest two meshes)[/green]")
    else:
        console.print("\n[yellow]⚠ Not converged — consider finer meshes[/yellow]")


# ===================================================================
# postprocess commands
# ===================================================================

@postprocess_app.command("wake")
def postprocess_wake(
    output_dir: Annotated[str, typer.Argument(help="Output directory or run ID (e.g. 001)")],
    wake_type: Annotated[
        Optional[list[str]],
        typer.Option("--type", "-t", help="Wake type(s)"),
    ] = None,
    geometry: Annotated[
        Optional[str],
        typer.Option("--geometry", "-g", help="Geometry type: round, recta (auto-detected if omitted)"),
    ] = None,
    output: Annotated[
        Optional[str],
        typer.Option("--output", "-o", help="Output file prefix"),
    ] = None,
    plot: Annotated[
        bool,
        typer.Option("--plot", "-p", help="Plot the wake"),
    ] = False,
) -> None:
    """Post-process wake results.

    The output directory can be:
    - A run ID (e.g. ``001``) — auto-resolved via the project manifest
    - A relative or absolute path to a run/output directory
    """
    from pyecho.api import quick_postprocess
    from pyecho.project import resolve_run_dir

    # Resolve run ID (e.g. "001") to actual directory path
    resolved = resolve_run_dir(output_dir)
    if resolved is not None:
        output_dir = str(resolved)
        console.print(f"  [dim]Run directory: {output_dir}[/dim]")

    try:
        result = quick_postprocess(output_dir, geometry=geometry)
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] Post-processing failed: {exc}")
        raise typer.Exit(1)

    # Display summary
    from pyecho.datamodel import RoundWakeResult, FlatWakeResult

    # Resolve processed/ output directory
    out_path = Path(output_dir).resolve()
    processed_dir = _find_processed_dir(out_path)
    wake_out = processed_dir / "wake"
    wake_out.mkdir(parents=True, exist_ok=True)

    if isinstance(result, RoundWakeResult):
        console.print(
            Panel.fit(
                f"[bold green]✓ Wake processed[/bold green]\n"
                f"  Loss_long:  [cyan]{result.loss_long:.6f} V/pC[/cyan]\n"
                f"  Peak:       [cyan]{result.peak:.4f} V/pC[/cyan]",
                title="Round Wake Result",
            )
        )
        # Save monopole (m=0) — longitudinal wake
        _save_wake_round_data(result.s, result.Wlong, "monopole", "V/pC", wake_out / "wake_monopole.txt")
        summary_lines = [
            f"Geometry: round",
            f"",
            f"[Monopole (m=0)] — longitudinal wake potential",
            f"  Loss_long:  {result.loss_long:.6f} V/pC",
            f"  Peak:       {result.peak:.4f} V/pC",
            f"  RMS spread: {result.rms_spread:.4f} V/pC",
        ]
        # Save dipole (m=1) if available
        if result.Wdipole is not None:
            _save_wake_round_data(result.s, result.Wdipole, "dipole", "V/pC/m²", wake_out / "wake_dipole.txt")
            kd = result.kick_dipole if result.kick_dipole is not None else 0.0
            summary_lines.extend([
                "",
                f"[Dipole (m=1)] — modal coefficient",
                f"  Kick_dipole: {kd:.4f} V/pC/m",
            ])
            console.print(f"  [dim]Dipole (m=1) saved, Kick_dipole = {kd:.4f} V/pC/m[/dim]")
        # Write unified summary
        (wake_out / "summary.txt").write_text("\n".join(summary_lines), encoding="utf-8")
        # Update run manifest
        _try_update_processed_manifest(out_path, loss_long=result.loss_long, peak=result.peak)
    elif isinstance(result, FlatWakeResult):
        console.print(
            Panel.fit(
                f"[bold green]✓ Wake processed (rectangular)[/bold green]\n"
                f"  Longitudinal loss: [cyan]{result.loss_long:.6f} V/pC[/cyan]\n"
                f"  Quadrupole kick:   [cyan]{result.kick_quad:.6f} V/pC/mm[/cyan]\n"
                f"  Dipole kick:       [cyan]{result.kick_dipole:.6f} V/pC/mm[/cyan]",
                title="Rectangular Wake Result",
            )
        )
        # Save processed data
        _save_wake_flat(result, wake_out)
        # Update run manifest
        _try_update_processed_manifest(
            out_path,
            loss_long=result.loss_long,
            kick_quad=result.kick_quad,
            kick_dipole=result.kick_dipole,
        )

    console.print(f"  [dim]Data saved to {wake_out}/[/dim]")

    if plot:
        import matplotlib.pyplot as plt
        if isinstance(result, FlatWakeResult):
            from pyecho.visualize import plot_flat_wake
            data_dir = _resolve_plot_data_dir(output_dir)
            offset = _read_offset_from_dir(data_dir)
            from pyecho.parser import load_bunch_profile
            _, bunch = load_bunch_profile(data_dir, offset, result.s)
            fig, axes = plot_flat_wake(result, bunch=bunch)
            if output:
                save_path = f"{output}_wake.png"
            else:
                save_path = str(wake_out / "wake_plot.png")
            fig.savefig(save_path, dpi=150, bbox_inches="tight")
            console.print(f"  [dim]Plot saved to {save_path}[/dim]")
            plt.show()
        else:
            from pyecho.visualize import plot_round_wake

            fig, axes = plot_round_wake(result)
            save_path = str(wake_out / "wake_plot.png") if not output else f"{output}_wake.png"
            fig.savefig(save_path, dpi=150, bbox_inches="tight")
            console.print(f"  [dim]Plot saved to {save_path}[/dim]")
            plt.show()


@postprocess_app.command("field")
def postprocess_field(
    output_dir: Annotated[str, typer.Argument(help="Output directory or run ID")],
    list_monitors: Annotated[
        bool,
        typer.Option("--list", "-l", help="List available field monitors"),
    ] = False,
    mode: Annotated[
        int,
        typer.Option("--mode", "-m", help="Azimuthal mode number"),
    ] = 0,
    monitor_id: Annotated[
        int,
        typer.Option("--monitor-id", "-n", help="Monitor index (N in Monitor_mXX_NYY.txt)"),
    ] = 1,
    component: Annotated[
        Optional[str],
        typer.Option("--component", "-c", help="Field component: Ex, Ey, Ez, Hx, Hy, Hz"),
    ] = None,
    point_t: Annotated[
        Optional[float],
        typer.Option("--point-t", help="Fixed time/s coordinate for extraction"),
    ] = None,
    point_z: Annotated[
        Optional[float],
        typer.Option("--point-z", help="Fixed z coordinate for extraction"),
    ] = None,
    point_r: Annotated[
        Optional[float],
        typer.Option("--point-r", help="Fixed r/y coordinate for extraction"),
    ] = None,
    synthesize: Annotated[
        bool,
        typer.Option("--synthesize", help="Synthesize total field from modal monitors"),
    ] = False,
    total: Annotated[
        Optional[str],
        typer.Option("--total", help="Auto-synthesize and save MonitorTotal (specify output dir)"),
    ] = None,
    extract_point: Annotated[
        Optional[str],
        typer.Option("--extract-point", help="Extract point trace: 'z,r' in meters (e.g. 0.03,0.0015)"),
    ] = None,
    x0: Annotated[
        float,
        typer.Option("--x0", help="Source transverse offset [m] for synthesis (default: 0)"),
    ] = 0.0,
    x: Annotated[
        float,
        typer.Option("--x", help="Observation transverse position [m] for synthesis (default: 0)"),
    ] = 0.0,
    D: Annotated[
        Optional[float],
        typer.Option("--D", "--width", help="Structure width [m] for synthesis (auto-detected if omitted)"),
    ] = None,
    n_modes_synth: Annotated[
        int,
        typer.Option("--n-modes", help="Number of odd modes for synthesis (default: 15)"),
    ] = 15,
    output: Annotated[
        Optional[str],
        typer.Option("--output", "-o", help="Output file for extracted data"),
    ] = None,
    plot: Annotated[
        bool,
        typer.Option("--plot", "-p", help="Plot as 2-D pseudocolor"),
    ] = False,
    plot_3d: Annotated[
        bool,
        typer.Option("--plot-3d", help="Plot as 3-D surface (replicates MATLAB mesh)"),
    ] = False,
    animate: Annotated[
        Optional[str],
        typer.Option("--animate", help="Animate time series, save to .gif/.mp4"),
    ] = None,
    fps: Annotated[
        int,
        typer.Option("--fps", help="Frames per second for animation"),
    ] = 10,
    geometry: Annotated[
        str,
        typer.Option("--geometry", "-g", help="Geometry type: round, recta (for Ep*r handling)"),
    ] = "recta",
    no_show: Annotated[
        bool,
        typer.Option("--no-show", help="Do not display plot window"),
    ] = False,
) -> None:
    """Post-process field monitor data.

    Supports both recta (rectangular) and round geometries.  For round
    geometry Ep (E_phi) is stored as Ep*r by ECHO2D and automatically
    divided by r to recover the physical field.

    \\b
    Examples:
      echo2d postprocess field . --list                       # list monitors
      echo2d postprocess field . -m 1 -n 1 -c Ez              # load & show info
      echo2d postprocess field . --extract-point "0.03,0.001" # point trace
      echo2d postprocess field . --synthesize -c Ez -n 1      # total field
      echo2d postprocess field . -m 1 -n 1 -c Ez --animate field.gif
      echo2d postprocess field . -m 0 -n 2 -c Ep -g round --plot-3d
    """
    from pathlib import Path as _Path
    from pyecho.project import resolve_run_dir
    from pyecho.parser import OutputLoader
    from pyecho.postprocess.fields import (
        process_field_monitor,
        synthesize_total_field_from_loader,
        extract_point_monitor,
        save_point_monitor,
        animate_field_monitor,
        plot_field_3d,
    )
    import numpy as np

    # Resolve run ID to directory
    resolved = resolve_run_dir(output_dir)
    if resolved is not None:
        output_dir = str(resolved)
        console.print(f"  [dim]Run directory: {output_dir}[/dim]")

    out_path = _Path(output_dir).resolve()
    loader = OutputLoader(out_path)

    # --list: show available monitors with details
    if list_monitors:
        monitors = loader.list_monitors()
        if not monitors:
            console.print("[yellow]No field monitors found.[/yellow]")
            return
        table = Table(title="Available Field Monitors")
        table.add_column("Mode", style="cyan")
        table.add_column("ID", style="green")
        table.add_column("Component", style="yellow")
        table.add_column("Type")
        table.add_column("Shape", style="dim")
        table.add_column("Filename", style="dim")
        for m, n in sorted(monitors):
            try:
                mon = loader.load_monitor(mode=m, monitor_id=n)
                comp = mon.field_component if mon else "?"
                ttype = mon.time_type if mon else "?"
                shape = str(mon.F.shape) if mon else "?"
            except Exception:
                comp, ttype, shape = "?", "?", "?"
            table.add_row(str(m), str(n), comp, ttype, shape,
                         f"Monitor_m{m:02d}_N{n:02d}.txt")
        console.print(table)
        return

    # --synthesize or --total: build total field from modal monitors
    if synthesize or total is not None:
        if component is None:
            console.print("[red]Error: --component is required for field synthesis.[/red]")
            raise typer.Exit(1)
        try:
            total_field = synthesize_total_field_from_loader(
                magn_dir=loader._resolve_data_dir(),
                component=component,
                monitor_id=monitor_id,
                x0=x0,
                x=x,
                n_modes=n_modes_synth,
                D=D,
            )
        except Exception as exc:
            console.print(f"[red]Error: Field synthesis failed: {exc}[/red]")
            raise typer.Exit(1)

        console.print(f"[green]✓ Total field synthesized: {component}, shape={total_field.shape}[/green]")

        if total is not None:
            # Save as MonitorTotal format
            total_dir = _Path(total)
            total_dir.mkdir(parents=True, exist_ok=True)
            out_file = total_dir / f"MonitorTotal_N{monitor_id:02d}.txt"
            _save_monitor_total(out_file, total_field, component, "z", D or 0.05,
                               T=None, Z=None, R=None)
            console.print(f"  [dim]MonitorTotal saved to {out_file}[/dim]")

        if output:
            np.savetxt(output, total_field, header=f"Total {component} field", fmt="%.8e")
            console.print(f"  [dim]Saved to {output}[/dim]")

        if plot:
            _plot_monitor_slice(total_field, title=f"Total {component} field",
                               output=output, no_show=no_show)
        return

    # --extract-point: shorthand for point extraction
    if extract_point is not None:
        parts = extract_point.split(",")
        if len(parts) != 2:
            console.print("[red]Error: --extract-point requires 'z,r' format (e.g. 0.03,0.0015)[/red]")
            raise typer.Exit(1)
        point_z = float(parts[0].strip())
        point_r = float(parts[1].strip())

    # --load single monitor
    try:
        monitor = loader.load_monitor(mode=mode, monitor_id=monitor_id)
    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise typer.Exit(1)

    if monitor is None:
        console.print(
            f"[yellow]Monitor m{mode}_N{monitor_id} not found.[/yellow]\n"
            f"Use --list to see available monitors."
        )
        return

    # Show monitor info
    console.print(
        Panel.fit(
            f"[bold]Monitor m{mode}_N{monitor_id}[/bold]\n"
            f"  Component:  [cyan]{monitor.field_component}[/cyan]\n"
            f"  Time type:  [cyan]{monitor.time_type}[/cyan]\n"
            f"  T range:    [{monitor.T[0]:.3e}, {monitor.T[-1]:.3e}] ({len(monitor.T)} pts)\n"
            f"  Z range:    [{monitor.Z[0]:.3e}, {monitor.Z[-1]:.3e}] ({len(monitor.Z)} pts)\n"
            f"  R range:    [{monitor.R[0]:.3e}, {monitor.R[-1]:.3e}] ({len(monitor.R)} pts)\n"
            f"  Field shape: {monitor.F.shape}",
            title="Field Monitor Info",
        )
    )

    # Extract field at specified point
    if point_t is not None or point_z is not None or point_r is not None:
        z_val = point_z if point_z is not None else 0.0
        r_val = point_r if point_r is not None else 0.0
        T, trace = extract_point_monitor(monitor, z=z_val, r=r_val, geometry=geometry)
        console.print(
            f"[green]✓ Point trace extracted: "
            f"min={np.min(trace):.4e}, max={np.max(trace):.4e}, "
            f"points={len(trace)}[/green]"
        )
        if output:
            save_point_monitor(_Path(output), T, trace, monitor.field_component, geometry)
            console.print(f"  [dim]PointMonitor saved to {output}[/dim]")

    # --animate
    if animate is not None:
        animate_field_monitor(monitor, output=animate, fps=fps, geometry=geometry)
        console.print(f"[green]✓ Animation saved to {animate}[/green]")
        return

    # Plot: 3-D surface or 2-D slice
    if plot_3d:
        plot_field_3d(monitor, time_step=0, output=output, geometry=geometry)
    elif plot:
        _plot_monitor_slice(monitor, title=f"{monitor.field_component} — m{mode}_N{monitor_id}",
                           output=output, no_show=no_show)


@postprocess_app.command("particles")
def postprocess_particles(
    output_dir: Annotated[str, typer.Argument(help="Output directory or run ID")],
    to_astra: Annotated[
        Optional[str],
        typer.Option("--to-astra", help="Convert particles to ASTRA format, specify output file"),
    ] = None,
    total_charge: Annotated[
        Optional[float],
        typer.Option("--charge", "-q", help="Total bunch charge [C] for ASTRA conversion"),
    ] = None,
    energy: Annotated[
        float,
        typer.Option("--energy", "-e", help="Reference beam energy [MeV] for ASTRA"),
    ] = 100.0,
    output: Annotated[
        Optional[str],
        typer.Option("--output", "-o", help="Output file for particle statistics"),
    ] = None,
    phase_space: Annotated[
        bool,
        typer.Option("--phase-space", help="Generate phase-space scatter plots"),
    ] = False,
) -> None:
    """Post-process particle tracking data.

    Loads ``particles.out`` from ECHO2D output and displays phase-space
    statistics.  Optionally converts to ASTRA format for further tracking.

    \\b
    Examples:
      echo2d postprocess particles .                 # show statistics
      echo2d postprocess particles . --phase-space    # phase-space plots
      echo2d postprocess particles . --to-astra out.astra -q 1e-9
    """
    from pathlib import Path as _Path
    from pyecho.project import resolve_run_dir
    from pyecho.parser import OutputLoader
    from pyecho.postprocess.particles import (
        load_echo_particles, compute_particle_statistics, convert_echo_to_astra,
    )

    resolved = resolve_run_dir(output_dir)
    if resolved is not None:
        output_dir = str(resolved)
        console.print(f"  [dim]Run directory: {output_dir}[/dim]")

    out_path = _Path(output_dir).resolve()
    loader = OutputLoader(out_path)
    data_dir = loader._resolve_data_dir()
    part_file = data_dir / "particles.out"

    if not part_file.exists():
        console.print(f"[yellow]No particles.out found in {data_dir}[/yellow]")
        console.print(
            "[dim]Enable particle output with ParticleMotion=1 and "
            "DumpParticles=1 in input_in.txt[/dim]"
        )
        return

    # Load particles
    try:
        particles = load_echo_particles(part_file)
    except Exception as exc:
        console.print(f"[red]Error loading particles: {exc}[/red]")
        raise typer.Exit(1)

    Np = int(particles.get("Np", 0))
    stats = compute_particle_statistics(particles)

    # Display statistics
    console.print(
        Panel.fit(
            f"[bold]Particle Data: {part_file.name}[/bold]\n"
            f"  Particles:  [cyan]{Np}[/cyan]\n"
            f"  Mean x:     {stats.get('mean_x', 0):.4e} m\n"
            f"  Mean y:     {stats.get('mean_y', 0):.4e} m\n"
            f"  Mean z:     {stats.get('mean_z', 0):.4e} m\n"
            f"  σ_x:        {stats.get('sigma_x', 0):.4e} m\n"
            f"  σ_y:        {stats.get('sigma_y', 0):.4e} m\n"
            f"  σ_z:        {stats.get('sigma_z', 0):.4e} m\n"
            f"  Mean px:    {stats.get('mean_px', 0):.4e}\n"
            f"  Mean py:    {stats.get('mean_py', 0):.4e}\n"
            f"  Mean pz:    {stats.get('mean_pz', 0):.4e}",
            title="Particle Statistics",
        )
    )

    if output:
        _Path(output).write_text(
            f"# ECHO2D Particle Statistics\n"
            f"# Np = {Np}\n"
            + "\n".join(f"# {k} = {v}" for k, v in stats.items()),
            encoding="utf-8",
        )
        console.print(f"  [dim]Statistics saved to {output}[/dim]")

    # ASTRA conversion
    if to_astra:
        try:
            n_conv = convert_echo_to_astra(
                echo_file=part_file,
                astra_file=to_astra,
                total_charge=total_charge,
                reference_energy_MeV=energy,
            )
            console.print(
                f"[green]✓ Converted {n_conv} particles to ASTRA: "
                f"[cyan]{to_astra}[/cyan][/green]"
            )
        except Exception as exc:
            console.print(f"[red]Error: ASTRA conversion failed: {exc}[/red]")
            raise typer.Exit(1)

    # Phase-space plots
    if phase_space:
        import matplotlib.pyplot as plt
        active = particles["status"] == 0
        x = particles["x"][active][:5000]
        y = particles["y"][active][:5000]
        z = particles["z"][active][:5000]
        px = particles["px"][active][:5000]
        py = particles["py"][active][:5000]
        pz = particles["pz"][active][:5000]

        fig, axes = plt.subplots(1, 3, figsize=(15, 4))
        axes[0].scatter(x * 1e3, px, s=1, alpha=0.5)
        axes[0].set_xlabel("x [mm]"); axes[0].set_ylabel("px [kg·m/s]")
        axes[0].set_title("x–px phase space"); axes[0].grid(True, alpha=0.3)

        axes[1].scatter(y * 1e3, py, s=1, alpha=0.5)
        axes[1].set_xlabel("y [mm]"); axes[1].set_ylabel("py [kg·m/s]")
        axes[1].set_title("y–py phase space"); axes[1].grid(True, alpha=0.3)

        axes[2].scatter(z * 1e3, pz, s=1, alpha=0.5)
        axes[2].set_xlabel("z [mm]"); axes[2].set_ylabel("pz [kg·m/s]")
        axes[2].set_title("z–pz phase space"); axes[2].grid(True, alpha=0.3)

        fig.suptitle(f"Phase Space (N={Np}, active only)", fontweight="bold")
        fig.tight_layout()
        if output:
            fig.savefig(output.replace(".txt", "") + "_phase_space.png", dpi=150, bbox_inches="tight")
        plt.show()


@postprocess_app.command("wake-monitor")
def postprocess_wake_monitor(
    output_dir: Annotated[str, typer.Argument(help="Output directory or run ID")],
    list_monitors: Annotated[
        bool,
        typer.Option("--list", "-l", help="List available WakeMonitor files"),
    ] = False,
    mode: Annotated[
        int,
        typer.Option("--mode", "-m", help="WakeMonitor mode number"),
    ] = 0,
    index: Annotated[
        int,
        typer.Option("--index", "-i", help="WakeMonitor index"),
    ] = 0,
    output: Annotated[
        Optional[str],
        typer.Option("--output", "-o", help="Save wake data to file"),
    ] = None,
    plot: Annotated[
        bool,
        typer.Option("--plot", "-p", help="Plot the wake monitor"),
    ] = False,
) -> None:
    """Post-process WakeMonitor binary files (WakeM_XX_YYYYYY.bin).

    WakeMonitor files record the wake potential at specific time steps
    during the simulation (different from the final wakeL files).

    \\b
    Examples:
      echo2d postprocess wake-monitor . --list
      echo2d postprocess wake-monitor . -m 0 -i 1 --plot
    """
    from pyecho.project import resolve_run_dir
    from pyecho.parser import OutputLoader
    import numpy as np

    resolved = resolve_run_dir(output_dir)
    if resolved is not None:
        output_dir = str(resolved)

    loader = OutputLoader(output_dir)

    if list_monitors:
        wm_data = loader.load_all_wake_monitors()
        if not wm_data:
            console.print("[yellow]No WakeMonitor files found.[/yellow]")
            return
        table = Table(title="Available WakeMonitors")
        table.add_column("Mode", style="cyan")
        table.add_column("Index", style="green")
        table.add_column("Points", justify="right")
        for (m, idx), data in sorted(wm_data.items()):
            table.add_row(str(m), str(idx), str(data["n"]))
        console.print(table)
        return

    wm = loader.load_wake_monitor(mode=mode, index=index)
    if wm is None:
        console.print(
            f"[yellow]WakeMonitor m{mode}_{index:06d} not found.[/yellow]\n"
            f"Use --list to see available WakeMonitors."
        )
        return

    wake = wm["wake"]
    n = wm["n"]
    console.print(
        Panel.fit(
            f"[bold]WakeMonitor m{mode}_{index:06d}.bin[/bold]\n"
            f"  Points:     [cyan]{n}[/cyan]\n"
            f"  Min wake:   [cyan]{np.min(wake):.4e}[/cyan]\n"
            f"  Max wake:   [cyan]{np.max(wake):.4e}[/cyan]",
            title="WakeMonitor Data",
        )
    )

    if output:
        np.savetxt(output, wake, header=f"WakeMonitor m{mode}_{index:06d}", fmt="%.8e")
        console.print(f"  [dim]Saved to {output}[/dim]")

    if plot:
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(wake, "b-", linewidth=1.5, alpha=0.7, label=f"WakeM_{mode:02d}_{index:06d}")

        # Overlay final wakeL if available (MATLAB WakeMonitor.m behavior)
        try:
            s, W, _, _, _, _ = loader.load_wake(mode=mode)
            W_pc = W * 1e-3  # m·V/nC → V/pC
            ax.plot(W_pc, "r-", linewidth=1.5, alpha=0.7, label=f"wakeL_{mode:02d} (final)")
            ax.legend(loc="best")
        except Exception:
            pass  # wakeL not available, just show WakeMonitor

        ax.set_xlabel("Time step / s-index")
        ax.set_ylabel("Wake potential [V/pC]")
        ax.set_title(f"WakeMonitor m{mode}_{index:06d} + final wakeL")
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        if output:
            fig.savefig(output.replace(".txt", ".png"), dpi=150, bbox_inches="tight")
        plt.show()


@postprocess_app.command("beam-moments")
def postprocess_beam_moments(
    output_dir: Annotated[str, typer.Argument(help="Output directory or run ID")],
    output: Annotated[
        Optional[str],
        typer.Option("--output", "-o", help="Save beam moments to file"),
    ] = None,
    plot: Annotated[
        bool,
        typer.Option("--plot", "-p", help="Plot beam moments evolution"),
    ] = False,
) -> None:
    """Post-process BeamMomentsMonitor.txt.

    Displays and optionally plots the evolution of beam moments
    (centroid position, RMS size, emittance) during the simulation.

    \\b
    Examples:
      echo2d postprocess beam-moments .
      echo2d postprocess beam-moments . --plot -o moments.csv
    """
    from pyecho.project import resolve_run_dir
    from pyecho.parser import OutputLoader
    import numpy as np

    resolved = resolve_run_dir(output_dir)
    if resolved is not None:
        output_dir = str(resolved)

    loader = OutputLoader(output_dir)
    data = loader.load_beam_moments()

    if data is None:
        console.print("[yellow]No BeamMomentsMonitor.txt found.[/yellow]")
        console.print(
            "[dim]Enable beam monitoring with the BeamMonitor parameter "
            "in input_in.txt[/dim]"
        )
        return

    n_rows, n_cols = data.shape
    console.print(
        Panel.fit(
            f"[bold]BeamMomentsMonitor.txt[/bold]\n"
            f"  Time steps: [cyan]{n_rows}[/cyan]\n"
            f"  Moments:    [cyan]{n_cols}[/cyan]",
            title="Beam Moments",
        )
    )

    if output:
        header = "time_step " + " ".join(f"moment_{i}" for i in range(n_cols))
        np.savetxt(output, data, header=header, fmt="%.8e")
        console.print(f"  [dim]Saved to {output}[/dim]")

    if plot:
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(min(n_cols, 4), 1, figsize=(10, 3 * min(n_cols, 4)), sharex=True)
        if n_cols == 1:
            axes = [axes]
        for i in range(min(n_cols, 4)):
            axes[i].plot(data[:, i], linewidth=1.2)
            axes[i].set_ylabel(f"Moment {i}")
            axes[i].grid(True, alpha=0.3)
        axes[-1].set_xlabel("Time step")
        fig.suptitle("Beam Moments Evolution", fontweight="bold")
        fig.tight_layout()
        if output:
            fig.savefig(output.replace(".txt", "").replace(".csv", "") + "_moments.png",
                        dpi=150, bbox_inches="tight")
        plt.show()


@postprocess_app.command("all")
def postprocess_all(
    output_dir: Annotated[str, typer.Argument(help="Output directory or run ID")],
    auto_detect: Annotated[
        bool,
        typer.Option("--auto-detect/--no-auto-detect", help="Auto-detect geometry type"),
    ] = True,
    skip: Annotated[
        Optional[list[str]],
        typer.Option("--skip", help="Steps to skip: wake, field, particles"),
    ] = None,
    output: Annotated[
        Optional[str],
        typer.Option("--output", "-o", help="Output directory for processed results"),
    ] = None,
    plot: Annotated[
        bool,
        typer.Option("--plot", "-p", help="Generate plots for each step"),
    ] = False,
) -> None:
    """Run all post-processing steps (wake + field + particles).

    Auto-detects the geometry type and runs the appropriate pipeline:
    - Round: monopole (m=0) + dipole (m=1) wake processing
    - Recta: Wcc + Wss assembly → Wlong, Wquad, Wdipole
    - Field monitors: list and extract available monitors
    - Particles: statistics and optional ASTRA conversion

    \\b
    Examples:
      echo2d postprocess all .                    # run everything
      echo2d postprocess all . --skip field       # skip field processing
      echo2d postprocess all . -o results/ --plot # custom output + plots
    """
    from pyecho.project import resolve_run_dir
    from pyecho.parser import OutputLoader
    import numpy as np

    skip_set = set(skip or [])

    # Resolve run ID to directory
    resolved = resolve_run_dir(output_dir)
    if resolved is not None:
        output_dir = str(resolved)
    out_path = Path(output_dir).resolve()

    # Determine output directory
    processed_dir = _find_processed_dir(out_path) if output is None else Path(output)
    processed_dir.mkdir(parents=True, exist_ok=True)

    # Detect geometry
    loader = OutputLoader(out_path)
    try:
        from pyecho.postprocess import PostProcessor
        pp = PostProcessor(loader)
        geo_type = pp.geometry_type
    except Exception:
        geo_type = "unknown"

    console.print(
        Panel.fit(
            f"Output dir:  [cyan]{out_path}[/cyan]\n"
            f"Geometry:    [cyan]{geo_type}[/cyan]\n"
            f"Processed:   [cyan]{processed_dir}[/cyan]",
            title="Post-Process All",
        )
    )

    results: dict = {"geometry_type": geo_type}

    # ── Step 1: Wake processing ──
    if "wake" not in skip_set:
        console.print("\n[bold]▶ Step 1: Wake processing[/bold]")
        try:
            from pyecho.api import quick_postprocess
            wake_result = quick_postprocess(output_dir, geometry=geo_type)
            results["wake"] = wake_result

            # Save wake data
            wake_out = processed_dir / "wake"
            wake_out.mkdir(parents=True, exist_ok=True)

            if geo_type == "round":
                _save_wake_round_data(wake_result.s, wake_result.Wlong,
                                      "monopole", "V/pC", wake_out / "wake_monopole.txt")
                if wake_result.Wdipole is not None:
                    _save_wake_round_data(wake_result.s, wake_result.Wdipole,
                                          "dipole", "V/pC/m²", wake_out / "wake_dipole.txt")
                console.print(
                    f"  [green]✓[/green] Round wake: "
                    f"loss_long={wake_result.loss_long:.4f} V/pC, "
                    f"peak={wake_result.peak:.4f} V/pC"
                )
            else:
                _save_wake_flat(wake_result, wake_out)
                console.print(
                    f"  [green]✓[/green] Recta wake: "
                    f"loss_long={wake_result.loss_long:.4f} V/pC, "
                    f"kick_quad={wake_result.kick_quad:.4f} V/pC/mm, "
                    f"kick_dipole={wake_result.kick_dipole:.4f} V/pC/mm"
                )

            _try_update_processed_manifest(out_path,
                loss_long=wake_result.loss_long if geo_type == "round" else wake_result.loss_long,
                peak=getattr(wake_result, "peak", None),
                kick_quad=getattr(wake_result, "kick_quad", None),
                kick_dipole=getattr(wake_result, "kick_dipole", None),
            )

            if plot:
                _plot_wake_result(wake_result, geo_type, wake_out)

        except Exception as exc:
            console.print(f"  [yellow]⚠ Wake processing failed: {exc}[/yellow]")
            results["wake"] = None

    # ── Step 2: Field monitor processing ──
    if "field" not in skip_set:
        console.print("\n[bold]▶ Step 2: Field monitor processing[/bold]")
        monitors = loader.list_monitors()
        if monitors:
            console.print(f"  Found [cyan]{len(monitors)}[/cyan] monitor(s)")
            field_out = processed_dir / "field"
            field_out.mkdir(parents=True, exist_ok=True)
            for m, n in monitors[:10]:  # limit to first 10
                try:
                    monitor = loader.load_monitor(mode=m, monitor_id=n)
                    if monitor is not None:
                        console.print(
                            f"  [green]✓[/green] m{m}_N{n}: "
                            f"{monitor.field_component}, "
                            f"shape={monitor.F.shape}"
                        )
                except Exception as exc:
                    console.print(f"  [dim]○ m{m}_N{n}: {exc}[/dim]")
        else:
            console.print("  [dim]No field monitors found[/dim]")

    # ── Step 3: Particle processing ──
    if "particles" not in skip_set:
        console.print("\n[bold]▶ Step 3: Particle processing[/bold]")
        data_dir = loader._resolve_data_dir()
        part_file = data_dir / "particles.out"
        if part_file.exists():
            try:
                from pyecho.postprocess.particles import (
                    load_echo_particles, compute_particle_statistics,
                )
                particles = load_echo_particles(part_file)
                stats = compute_particle_statistics(particles)
                Np = int(particles.get("Np", 0))
                results["particles"] = {"n_particles": Np, "stats": stats}
                console.print(
                    f"  [green]✓[/green] {Np} particles loaded, "
                    f"σ_z={stats.get('sigma_z', 0):.4e} m"
                )
                # Save statistics
                part_out = processed_dir / "particles"
                part_out.mkdir(parents=True, exist_ok=True)
                (part_out / "statistics.txt").write_text(
                    f"# ECHO2D Particle Statistics\n"
                    f"# Np = {Np}\n"
                    + "\n".join(f"# {k} = {v}" for k, v in stats.items()),
                    encoding="utf-8",
                )
            except Exception as exc:
                console.print(f"  [yellow]⚠ Particle processing failed: {exc}[/yellow]")
        else:
            console.print("  [dim]No particles.out found[/dim]")

    # ── Summary ──
    console.print(f"\n[bold green]✓ Post-processing complete.[/bold green]")
    console.print(f"  Results saved to [cyan]{processed_dir}[/cyan]")


def _plot_wake_result(wake_result: Any, geo_type: str, wake_out: Path) -> None:
    """Generate and save wake plots (best-effort)."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        if geo_type == "round":
            from pyecho.visualize import plot_round_wake
            fig, _ = plot_round_wake(wake_result)
        else:
            from pyecho.visualize import plot_flat_wake
            data_dir = wake_out.parent.parent  # run dir
            for sub in ("magn", "elec"):
                cand = data_dir / sub
                if cand.is_dir():
                    data_dir = cand
                    break
            from pyecho.parser import load_bunch_profile
            # Try to load bunch from magn/ directory
            magn_dir = data_dir / "magn" if (data_dir / "magn").is_dir() else data_dir
            _, bunch = load_bunch_profile(magn_dir, 0, wake_result.s)
            fig, _ = plot_flat_wake(wake_result, bunch=bunch)

        fig.savefig(str(wake_out / "wake_plot.png"), dpi=150, bbox_inches="tight")
        plt.close(fig)
    except Exception:
        pass  # plotting is best-effort


# ===================================================================
# visualize commands
# ===================================================================

@visualize_app.command("wake")
def visualize_wake(
    wake_file: Annotated[str, typer.Argument(help="Wake file path")],
    bunch_file: Annotated[
        Optional[str],
        typer.Option("--bunch", "-b", help="Bunch profile file"),
    ] = None,
    output: Annotated[
        Optional[str],
        typer.Option("--output", "-o", help="Save plot to file"),
    ] = None,
    no_show: Annotated[
        bool,
        typer.Option("--no-show", help="Do not display plot"),
    ] = False,
) -> None:
    """Visualize wake potential from a wakeL file."""
    from pyecho.parser import parse_wake_file
    from pyecho.visualize import plot_wake_round

    try:
        parsed = parse_wake_file(wake_file)
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] Failed to parse wake file: {exc}")
        raise typer.Exit(1)

    bunch = None
    if bunch_file:
        try:
            bunch = np.loadtxt(bunch_file)
        except Exception as exc:
            console.print(f"[yellow]Warning:[/yellow] Could not load bunch file: {exc}")

    s = parsed["s"]
    W = parsed["W_raw"] * 1e-3  # Convert to V/pC

    fig, ax = plot_wake_round(
        s, W,
        bunch=bunch,
        title=f"Wake Potential — Mode {parsed['mode']}",
    )

    console.print(
        f"[green]Mode {parsed['mode']}: "
        f"hr={parsed['hr']:.2e}, D={parsed['D']:.3f}, σ={parsed['sigma']:.4f}[/green]"
    )

    if output:
        fig.savefig(output, dpi=150, bbox_inches="tight")
        console.print(f"[green]Plot saved to {output}[/green]")

    if not no_show:
        import matplotlib.pyplot as plt
        plt.show()


@visualize_app.command("compare")
def visualize_compare(
    files: Annotated[list[str], typer.Argument(help="Wake files to compare")],
    labels: Annotated[
        Optional[list[str]],
        typer.Option("--labels", "-l", help="Labels for each file"),
    ] = None,
    difference: Annotated[
        bool,
        typer.Option("--diff", "-d", help="Show difference from first"),
    ] = False,
    output: Annotated[
        Optional[str],
        typer.Option("--output", "-o", help="Save plot to file"),
    ] = None,
) -> None:
    """Compare multiple wake potential results."""
    from pyecho.parser import parse_wake_file
    from pyecho.visualize import plot_comparison

    results: list[tuple] = []
    for i, f in enumerate(files):
        label = labels[i] if labels and i < len(labels) else Path(f).stem
        try:
            parsed = parse_wake_file(f)
            results.append((label, parsed["s"], parsed["W_raw"] * 1e-3))
        except Exception as exc:
            console.print(f"[bold red]Error:[/bold red] Failed to parse {f}: {exc}")
            raise typer.Exit(1)

    fig, ax = plot_comparison(results, difference=difference)

    # Warn if comparing different modes in round geometry
    modes_seen: set[int] = set()
    for f in files:
        try:
            parsed = parse_wake_file(f)
            modes_seen.add(parsed["mode"])
        except Exception:
            pass
    # v0.1.1: guard against comparing different azimuthal modes
    # in the same round-geometry run (common user mistake).
    # Correct use: same mode across different runs/projects.
    if len(modes_seen) > 1:
        console.print(
            "[yellow]Warning:[/yellow] Note: Comparing different azimuthal modes "
            f"({sorted(modes_seen)}).  In round geometry these have "
            "different physical meanings & units.\n"
            "  m=0 → longitudinal wake [V/pC]\n"
            "  m=1 → dipole modal coefficient [V/pC/m²]\n\n"
            "[cyan]compare[/cyan] is meant for the [bold]same mode[/bold] "
            "across different runs\n"
            "(mesh convergence, parameter scans, etc.)."
        )

    if output:
        fig.savefig(output, dpi=150, bbox_inches="tight")
        console.print(f"[green]Plot saved to {output}[/green]")

    import matplotlib.pyplot as plt
    plt.show()


@visualize_app.command("modes")
def visualize_modes(
    data_dir: Annotated[
        str,
        typer.Argument(
            help="Path to magn/ or elec/ directory with wakeL_XX.txt files"
        ),
    ],
    n_modes: Annotated[
        Optional[int],
        typer.Option("--n-modes", "-n", help="Number of odd modes to plot"),
    ] = None,
    no_bunch: Annotated[
        bool,
        typer.Option(
            "--no-bunch",
            help="Do not overlay bunch profile from Iz0.txt",
        ),
    ] = False,
    output: Annotated[
        Optional[str],
        typer.Option("--output", "-o", help="Save plot to file"),
    ] = None,
    no_show: Annotated[
        bool,
        typer.Option("--no-show", help="Do not display plot window"),
    ] = False,
) -> None:
    """Plot modal decomposition of rectangular-geometry wakes.

    \b
    Each odd Fourier mode (m=1,3,5,...) is drawn as a different
    coloured line W_m(s) on the same 2D axes.  This replaces the
    MATLAB 3D mesh plot with an easier-to-read line plot.

    \b
    Examples:
      echo2d visualize modes magn/ -n 8
      echo2d visualize modes elec/
    """
    from pyecho.visualize import plot_wake_modes

    try:
        fig, ax = plot_wake_modes(
            data_dir,
            n_modes=n_modes,
            show_bunch=not no_bunch,
        )
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] Failed to plot modal decomposition: {exc}")
        raise typer.Exit(1)

    if output:
        fig.savefig(output, dpi=150, bbox_inches="tight")
        console.print(f"[green]Plot saved to {output}[/green]")

    if not no_show:
        import matplotlib.pyplot as plt
        plt.show()


@visualize_app.command("field")
def visualize_field(
    output_dir: Annotated[str, typer.Argument(help="Output directory")],
    mode: Annotated[
        int,
        typer.Option("--mode", "-m", help="Azimuthal mode number"),
    ] = 0,
    monitor_id: Annotated[
        int,
        typer.Option("--monitor-id", "-n", help="Monitor index"),
    ] = 1,
    component: Annotated[
        Optional[str],
        typer.Option("--component", "-c", help="Field component (if multiple per monitor)"),
    ] = None,
    time_step: Annotated[
        int,
        typer.Option("--time-step", "-t", help="Time step index to display"),
    ] = 0,
    output: Annotated[
        Optional[str],
        typer.Option("--output", "-o", help="Save plot to file"),
    ] = None,
    animate: Annotated[
        Optional[str],
        typer.Option("--animate", help="Animate time series, save to .gif/.mp4"),
    ] = None,
    fps: Annotated[
        int,
        typer.Option("--fps", help="Frames per second for animation"),
    ] = 10,
    plot_3d: Annotated[
        bool,
        typer.Option("--3d", help="Use 3-D surface plot (MATLAB mesh style)"),
    ] = False,
    geometry: Annotated[
        str,
        typer.Option("--geometry", "-g", help="Geometry type: round, recta"),
    ] = "recta",
    no_show: Annotated[
        bool,
        typer.Option("--no-show", help="Do not display plot window"),
    ] = False,
) -> None:
    """Visualize field monitor data.

    Supports 2-D pseudocolor, 3-D surface, and time-series animation.
    For round geometry, Ep (E_phi) is stored as Ep*r and handled correctly.

    \\b
    Examples:
      echo2d visualize field . -m 1 -n 1 -t 0              # 2-D slice
      echo2d visualize field . -m 1 -n 1 --3d -o field.png  # 3-D surface
      echo2d visualize field . -m 1 -n 1 --animate anim.gif # animation
      echo2d visualize field . -m 0 -n 2 -c Ep -g round --3d
    """
    from pyecho.parser import OutputLoader
    from pyecho.postprocess.fields import (
        animate_field_monitor,
        plot_field_3d,
    )
    from pyecho.visualize import plot_field
    import matplotlib.pyplot as plt

    loader = OutputLoader(output_dir)
    monitor = loader.load_monitor(mode=mode, monitor_id=monitor_id)

    if monitor is None:
        console.print(
            f"[yellow]Monitor m{mode}_N{monitor_id} not found.[/yellow]\n"
            f"Use [cyan]echo2d postprocess field --list[/cyan] to see available monitors."
        )
        return

    # Select time slice for 3-D data
    if monitor.F.ndim >= 3 and time_step < monitor.F.shape[0]:
        console.print(
            f"  [dim]Selecting time step {time_step}/{monitor.F.shape[0]} "
            f"(t = {monitor.T[time_step]:.3e})[/dim]"
        )

    # --animate
    if animate is not None:
        animate_field_monitor(monitor, output=animate, fps=fps, geometry=geometry)
        console.print(f"[green]✓ Animation saved to {animate}[/green]")
        return

    # --3d or 2D
    try:
        if plot_3d:
            plot_field_3d(monitor, time_step=time_step, output=output, geometry=geometry)
        else:
            fig, ax = plot_field(monitor, time_step=time_step)
            if output:
                fig.savefig(output, dpi=150, bbox_inches="tight")
                console.print(f"[green]Plot saved to {output}[/green]")
            if not no_show:
                plt.show()
    except Exception as exc:
        console.print(f"[red]Error plotting field: {exc}[/red]")
        raise typer.Exit(1)


# ===================================================================
# export commands
# ===================================================================

@export_app.command("hdf5")
def export_hdf5(
    output_dir: Annotated[str, typer.Argument(help="Output directory")],
    output: Annotated[
        Optional[str],
        typer.Option("--output", "-o", help="Output HDF5 file"),
    ] = None,
    compress: Annotated[
        int,
        typer.Option("--compress", "-c", help="Compression level (0-9)"),
    ] = 4,
) -> None:
    """Export results to HDF5 format."""
    import h5py
    from pyecho.parser import OutputLoader

    loader = OutputLoader(output_dir)
    out_path = Path(output or f"{Path(output_dir).name}_results.h5")

    with h5py.File(out_path, "w") as f:
        # Export wakes
        wakes = loader.load_all_wakes()
        if wakes:
            wake_grp = f.create_group("wakes")
            for mode, (s, W, hr, offset, D, sigma) in wakes.items():
                g = wake_grp.create_group(f"mode_{mode:02d}")
                g.create_dataset("s", data=s, compression="gzip", compression_opts=compress)
                g.create_dataset("W_raw", data=W, compression="gzip", compression_opts=compress)
                g.attrs["hr"] = hr
                g.attrs["offset"] = offset
                g.attrs["D"] = D
                g.attrs["sigma"] = sigma

        # Export currents
        currents = loader.load_currents()
        if currents is not None:
            f.create_dataset("currents_z", data=currents[1], compression="gzip", compression_opts=compress)
            f.create_dataset("s_current", data=currents[0], compression="gzip", compression_opts=compress)

        # Export field monitors
        monitors = loader.list_monitors()
        for mode, mon_id in monitors:
            mon = loader.load_monitor(mode=mode, monitor_id=mon_id)
            if mon is not None:
                g = f.create_group(f"monitors/m{mode:02d}_N{mon_id:02d}")
                g.create_dataset("T", data=mon.T, compression="gzip", compression_opts=compress)
                g.create_dataset("Z", data=mon.Z, compression="gzip", compression_opts=compress)
                g.create_dataset("R", data=mon.R, compression="gzip", compression_opts=compress)
                g.create_dataset("F", data=mon.F, compression="gzip", compression_opts=compress)
                g.attrs["component"] = mon.field_component
                g.attrs["time_type"] = mon.time_type
                g.attrs["D"] = mon.D

    console.print(f"[bold green]✓[/bold green] Exported to [cyan]{out_path}[/cyan]")


@export_app.command("csv")
def export_csv(
    output_dir: Annotated[str, typer.Argument(help="Output directory")],
    output: Annotated[
        Optional[str],
        typer.Option("--output", "-o", help="Output directory for CSV files"),
    ] = None,
) -> None:
    """Export results to CSV format."""
    import numpy as np
    from pyecho.parser import OutputLoader

    loader = OutputLoader(output_dir)
    out_dir = Path(output or f"{Path(output_dir).name}_csv")
    out_dir.mkdir(parents=True, exist_ok=True)

    wakes = loader.load_all_wakes()
    for mode, (s, W, hr, offset, D, sigma) in wakes.items():
        data = np.column_stack([s, W])
        header = f"s[m],W_raw[m*V/nC]"
        np.savetxt(
            out_dir / f"wake_mode_{mode:02d}.csv",
            data,
            delimiter=",",
            header=header,
            comments="",
        )

    console.print(f"[bold green]✓[/bold green] CSV files exported to [cyan]{out_dir}[/cyan]")


# ===================================================================
# compare commands
# ===================================================================

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

@system_app.command("info")
def system_info(
    ctx: typer.Context,
) -> None:
    """Show system and ECHO2D information."""
    # Support global --json flag for machine-readable output
    _json = ctx.obj.get("json", False)

    import platform
    import sys as _sys

    info = {
        "pyecho_version": __version__,
        "python_version": _sys.version,
        "platform": platform.platform(),
        "system": platform.system(),
        "machine": platform.machine(),
        "processor": platform.processor(),
    }

    if _json:
        console.print_json(json.dumps(info))
        return

    console.print(Panel.fit(
        f"[bold]ECHO2D Toolkit v{__version__}[/bold]",
        title="System Information",
    ))

    table = Table()
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")

    for k, v in info.items():
        table.add_row(k, str(v))

    console.print(table)


@system_app.command("detect")
def system_detect(
    scan: Annotated[
        Optional[str],
        typer.Option("--scan", "-s", help="Directory to scan for executables"),
    ] = None,
) -> None:
    """Detect ECHO2D executables on the system."""
    import platform as _platform
    from pyecho.runner import ECHO2DRunner

    _machine = _platform.machine().lower()
    _arch = "x86_64" if _machine in ("x86_64", "amd64") else "arm64"
    platform_key = f"{_platform.system()}_{_arch}"
    console.print(f"Platform: [cyan]{platform_key}[/cyan]")

    try:
        runner = ECHO2DRunner(Path.cwd() / ".echo2d_temp")
        console.print(f"[green]✓ Found: {runner.executable}[/green]")
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] Not found: {exc}")

    # List all available executables (platform-aware suffix)
    project_root = Path(__file__).resolve().parent.parent
    codes_dir = project_root / "ECHO2D_v3_5" / "Codes"
    if codes_dir.is_dir():
        console.print("\n[bold]Available executables:[/bold]")
        for child in sorted(codes_dir.iterdir()):
            if child.is_dir():
                exe = _find_exe_in_dir(child)
                if exe:
                    console.print(f"  [green]✓[/green] {child.name}  [dim]({exe.name})[/dim]")
                else:
                    console.print(f"  [red]✗[/red] {child.name}  [dim](no binary)[/dim]")


@system_app.command("check")
def system_check(
    fix: Annotated[
        Optional[str],
        typer.Option(
            "--fix",
            help="Auto-install missing packages: pip, conda, or brew",
            autocompletion=lambda: ["pip", "conda", "brew"],
        ),
    ] = None,
) -> None:
    """Check system dependencies and ECHO2D installation.

    Verifies all required Python packages are importable and detects
    the ECHO2D solver binary.  When packages are missing, suggests
    install commands tailored to your environment.

    Use ``--fix pip``, ``--fix conda``, or ``--fix brew`` to
    auto-install with the chosen package manager.
    """
    import importlib
    import os as _os
    import subprocess
    import sys as _sys
    from importlib.metadata import PackageNotFoundError, version

    # Validate --fix value early
    _valid_fix = {"pip", "conda", "brew"}
    if fix is not None and fix not in _valid_fix:
        console.print(
            f"[red]Invalid --fix value '{fix}'.[/red] "
            f"Choose from: {', '.join(sorted(_valid_fix))}"
        )
        raise typer.Exit(2)

    # ------------------------------------------------------------------
    # 0. Detect environment type
    # ------------------------------------------------------------------
    _env_type, _env_name = _detect_python_env()

    # ------------------------------------------------------------------
    # 1. Python package dependencies (aligned with pyproject.toml)
    # ------------------------------------------------------------------
    # Mapping: import_name → (display_name, pip_package_name, metadata_name)
    # *metadata_name* may differ from *import_name* (e.g. PyYAML imports
    # as ``yaml`` but its dist-info is ``pyyaml``).
    # Some packages also have conda / brew equivalents for suggestions.
    _DEPS: dict[str, tuple[str, str, str, str | None, str | None]] = {
        #            (display,    pip,       metadata,   conda,         brew)
        "numpy":      ("NumPy",          "numpy",      "numpy",      "numpy",       None),
        "scipy":      ("SciPy",          "scipy",      "scipy",      "scipy",       None),
        "matplotlib": ("Matplotlib",     "matplotlib", "matplotlib", "matplotlib",  None),
        "pydantic":   ("Pydantic",       "pydantic",   "pydantic",   "pydantic",    None),
        "yaml":       ("PyYAML",         "pyyaml",     "pyyaml",     "pyyaml",      None),
        "h5py":       ("HDF5 (h5py)",    "h5py",       "h5py",       "h5py",        None),
        "typer":      ("Typer",          "typer",      "typer",      "typer",       None),
        "rich":       ("Rich",           "rich",       "rich",       "rich",        None),
        "jinja2":     ("Jinja2",         "jinja2",     "jinja2",     "jinja2",      None),
        "pint":       ("Pint",           "pint",       "pint",       "pint",        None),
        "tqdm":       ("tqdm",           "tqdm",       "tqdm",       "tqdm",        None),
    }

    console.print(
        f"[bold]Checking Python dependencies…[/bold]  "
        f"[dim](env: {_env_name})[/dim]\n"
    )

    table = Table(show_header=True, header_style="bold")
    table.add_column("Package", style="cyan")
    table.add_column("Status")
    table.add_column("Version", style="dim")

    missing_imports: list[str] = []   # import names
    missing_pips: list[str] = []      # pip package names

    for mod, (label, pip_name, meta_name, _c, _b) in _DEPS.items():
        try:
            importlib.import_module(mod)
            try:
                ver = version(meta_name)
            except PackageNotFoundError:
                ver = "—"
            table.add_row(label, "[green]✓ installed[/green]", ver)
        except ImportError:
            table.add_row(label, "[red]✗ missing[/red]", "—")
            missing_imports.append(mod)
            missing_pips.append(pip_name)

    console.print(table)

    # ------------------------------------------------------------------
    # 2. ECHO2D solver binary
    # ------------------------------------------------------------------
    console.print("\n[bold]Checking ECHO2D solver…[/bold]\n")
    from pyecho.runner import ECHO2DRunner

    binary_ok = True
    try:
        runner = ECHO2DRunner(Path.cwd() / ".echo2d_temp")
        console.print(f"  [green]✓[/green] Binary: {runner.executable}")
        # Clean up the temp dir that the runner may have created
        _td = Path(runner.work_dir)
        if _td.exists() and _td.name == ".echo2d_temp":
            import shutil
            shutil.rmtree(_td, ignore_errors=True)
    except Exception as exc:
        console.print(f"  [red]✗[/red] Binary: {exc}")
        binary_ok = False

    # ------------------------------------------------------------------
    # 3. Report & suggest
    # ------------------------------------------------------------------
    if not missing_imports and binary_ok:
        console.print("\n[bold green]All dependencies satisfied.[/bold green]")
        return

    if not missing_imports:
        console.print(
            "\n[yellow]ECHO2D binary not found.[/yellow] "
            "Make sure the [cyan]ECHO2D_v3_5/Codes/[/cyan] directory "
            "contains a matching executable for your platform."
        )
        raise typer.Exit(1)

    # --- build install suggestions ---
    pkg_list = " ".join(missing_pips)

    # Determine conda / brew package names
    _conda_pkgs: list[str] = []
    _brew_pkgs: list[str] = []
    for mod in missing_imports:
        _, pip_name, _, conda_name, brew_name = _DEPS[mod]
        _conda_pkgs.append(conda_name if conda_name else pip_name)
        if brew_name:
            _brew_pkgs.append(brew_name)

    lines: list[str] = []
    lines.append(f"[bold]pip[/bold]        [dim]pip install {pkg_list}[/dim]")

    conda_tag = "" if _env_type == "conda" else "  [dim](if using conda)[/dim]"
    lines.append(
        f"[bold]conda[/bold]      [dim]conda install -c conda-forge "
        f"{' '.join(_conda_pkgs)}[/dim]{conda_tag}"
    )

    if _brew_pkgs:
        lines.append(
            f"[bold]brew[/bold]       [dim]brew install {' '.join(_brew_pkgs)}[/dim]"
            f"  [dim](system Python only)[/dim]"
        )

    # project-level install
    lines.append(
        f"[bold]project[/bold]    [dim]pip install -e .[/dim]"
        f"  [dim](installs all deps from pyproject.toml)[/dim]"
    )

    suggestion_body = "\n".join(lines)

    if fix is None:
        # Show multi-option install panel
        console.print(
            Panel.fit(
                f"[bold yellow]{len(missing_imports)} package(s) missing[/bold yellow]\n\n"
                f"{suggestion_body}\n\n"
                "Choose the method that matches your environment.\n"
                "After installing, re-run this check to verify.\n\n"
                "Auto-install with:\n"
                "  [cyan]echo2d system check --fix pip[/cyan]\n"
                "  [cyan]echo2d system check --fix conda[/cyan]\n"
                "  [cyan]echo2d system check --fix brew[/cyan]",
                title="Installation Options",
                border_style="yellow",
            )
        )
        raise typer.Exit(1)

    # ------------------------------------------------------------------
    # 4. Auto-fix: install via the chosen package manager
    # ------------------------------------------------------------------
    _run_auto_fix(
        method=fix,
        missing_pips=missing_pips,
        missing_imports=missing_imports,
        deps=_DEPS,
        env_type=_env_type,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _detect_python_env() -> tuple[str, str]:
    """Detect the Python environment type and a human-readable name.

    Returns
    -------
    tuple[str, str]
        ``(env_type, env_name)`` where *env_type* is one of
        ``"conda"``, ``"venv"``, ``"system"`` and *env_name* is a
        display label like ``"conda:base"`` or ``"system Python 3.13"``.
    """
    import os as _os
    import sys as _sys

    # Conda
    conda_prefix = _os.environ.get("CONDA_PREFIX", "")
    conda_env = _os.environ.get("CONDA_DEFAULT_ENV", "")
    if conda_prefix and conda_env:
        return ("conda", f"conda:{conda_env}")

    # venv / virtualenv
    if _os.environ.get("VIRTUAL_ENV"):
        venv_name = _os.path.basename(_os.environ["VIRTUAL_ENV"])
        return ("venv", f"venv:{venv_name}")

    # Distinguish venv-style from system by comparing prefix
    if hasattr(_sys, "base_prefix") and _sys.prefix != _sys.base_prefix:
        return ("venv", f"venv:{_sys.prefix}")

    # System Python
    py_ver = f"{_sys.version_info.major}.{_sys.version_info.minor}"
    return ("system", f"system Python {py_ver}")


def _copy_geometry_to_run(run_dir: Path, geom_name: str, proj_dir: Path) -> bool:
    """Try to find and copy a geometry file into the run directory.

    Searches:
    1. Project templates directory (pyecho/templates/)
    2. Project root directory
    3. Adjacent runs

    Returns True if the file was copied successfully.
    """
    import shutil as _shutil

    # 1. Check pyecho templates
    tmpl = _TEMPLATES_DIR / geom_name
    if tmpl.is_file():
        _shutil.copy2(str(tmpl), str(run_dir / geom_name))
        console.print(f"  [dim]Copied geometry from templates: {geom_name}[/dim]")
        return True

    # 2. Check project root
    proj_geom = proj_dir / geom_name
    if proj_geom.is_file() and proj_geom.parent != run_dir:
        _shutil.copy2(str(proj_geom), str(run_dir / geom_name))
        console.print(f"  [dim]Copied geometry from project root: {geom_name}[/dim]")
        return True

    # 3. Check other runs in the same project
    runs_dir = proj_dir / "runs"
    if runs_dir.is_dir():
        for child in runs_dir.iterdir():
            if child.is_dir() and child != run_dir:
                src = child / geom_name
                if src.is_file():
                    _shutil.copy2(str(src), str(run_dir / geom_name))
                    console.print(f"  [dim]Copied geometry from run {child.name}[/dim]")
                    return True

    return False


def _resolve_input_file(explicit: str | None) -> Path | None:
    """Find input_in.txt with project-context awareness.

    1. If *explicit* is given, use it directly.
    2. Look for ``input_in.txt`` in the current directory.
    3. Look in ``runs/*/`` subdirectories (project context).
    4. Walk up to find a project root and look in ``runs/``.
    """
    if explicit:
        p = Path(explicit)
        if p.is_file():
            return p.resolve()
        return None

    # Current directory
    cwd = Path.cwd()
    candidate = cwd / "input_in.txt"
    if candidate.is_file():
        return candidate

    # Runs subdirectories
    runs_dir = cwd / "runs"
    if runs_dir.is_dir():
        for child in sorted(runs_dir.iterdir(), reverse=True):
            if child.is_dir():
                f = child / "input_in.txt"
                if f.is_file():
                    return f

    # Walk up to find project root, then check runs/
    current = cwd
    for _ in range(10):
        if (current / ".echo2d.yaml").is_file():
            rdir = current / "runs"
            if rdir.is_dir():
                for child in sorted(rdir.iterdir(), reverse=True):
                    if child.is_dir():
                        f = child / "input_in.txt"
                        if f.is_file():
                            return f
            break
        parent = current.parent
        if parent == current:
            break
        current = parent

    return None


def _show_welcome() -> None:
    """Display the welcome / portal screen when ``echo2d`` is invoked
    without a subcommand."""
    import platform as _platform
    import sys as _sys

    console.print(
        Panel.fit(
            "[bold cyan]⚡ ECHO2D[/bold cyan] — Accelerator Wakefield / Impedance Solver\n\n"
            "Based on ECHO2D by Igor Zagorodnov (DESY)\n"
            "Official site: [link=https://echo4d.de]https://echo4d.de[/link]\n\n"
            "[bold]Tools:[/bold]\n"
            "  [cyan]echo2d[/cyan]          Command-line toolkit (this tool)\n"
            "  [cyan]echo2d-tui[/cyan]      Terminal UI  [dim](coming soon)[/dim]\n\n"
            "[bold]Quick start:[/bold]\n"
            "  [dim]$[/dim] echo2d project init myproj -t round_collimator\n"
            "  [dim]$[/dim] echo2d run start --threads 4\n"
            "  [dim]$[/dim] echo2d postprocess wake . --plot\n\n"
            "[bold]Workflow:[/bold]\n"
            "  [dim]$[/dim] echo2d project init   →  create a project\n"
            "  [dim]$[/dim] echo2d run new          →  add a run\n"
            "  [dim]$[/dim] echo2d run start        →  execute\n"
            "  [dim]$[/dim] echo2d run list         →  view history\n\n"
            "[bold]Explore:[/bold]\n"
            "  [dim]$[/dim] echo2d [cyan]--help[/cyan]           Full command tree\n"
            "  [dim]$[/dim] echo2d [cyan]workspace[/cyan]         Show workspace\n"
            "  [dim]$[/dim] echo2d [cyan]example[/cyan] list      Built-in examples\n"
            "  [dim]$[/dim] echo2d [cyan]system[/cyan] check      Verify installation\n\n"
            "[bold]Pro tip:[/bold]\n"
            "  [dim]$[/dim] echo2d [cyan]--install-completion[/cyan] zsh  "
            "Enable Tab autocomplete",
            title=f"ECHO2D v{__version__}",
            subtitle=f"Python {_sys.version_info.major}.{_sys.version_info.minor}  ·  "
                      f"{_platform.system()} {_platform.machine()}",
            border_style="cyan",
        )
    )


def _run_auto_fix(
    method: str,
    missing_pips: list[str],
    missing_imports: list[str],
    deps: dict,
    env_type: str,
) -> None:
    """Install missing packages via the chosen package manager.

    Parameters
    ----------
    method : str
        One of ``"pip"``, ``"conda"``, ``"brew"``.
    missing_pips : list[str]
        Pip package names to install.
    missing_imports : list[str]
        Import names (keys into *deps*).
    deps : dict
        Dependency mapping: import_name → (display, pip, meta, conda, brew).
    env_type : str
        Detected environment type (for warnings).
    """
    import importlib
    import subprocess
    import sys as _sys

    # Build the command per method
    if method == "pip":
        cmd = [_sys.executable, "-m", "pip", "install", *missing_pips]
        label = "pip"
    elif method == "conda":
        _conda_pkgs: list[str] = []
        for mod in missing_imports:
            _, pip_name, _, conda_name, _ = deps[mod]
            _conda_pkgs.append(conda_name if conda_name else pip_name)
        cmd = ["conda", "install", "-c", "conda-forge", "-y", *_conda_pkgs]
        label = "conda"
    elif method == "brew":
        _brew_pkgs: list[str] = []
        for mod in missing_imports:
            _, _, _, _, brew_name = deps[mod]
            if brew_name:
                _brew_pkgs.append(brew_name)
        if not _brew_pkgs:
            console.print(
                "[red]None of the missing packages have Homebrew formulas.[/red]"
            )
            raise typer.Exit(1)
        cmd = ["brew", "install", *_brew_pkgs]
        label = "brew"
    else:
        console.print(f"[bold red]Error:[/bold red] Unknown install method: {method}")
        raise typer.Exit(2)

    pkg_str = " ".join(missing_pips)

    # Warn if method mismatches environment
    if method == "conda" and env_type != "conda":
        console.print(
            "[yellow]Warning:[/yellow] You are not in a conda environment. "
            "conda install may fail or install into the wrong environment."
        )
    if method == "brew" and env_type != "system":
        console.print(
            "[yellow]Warning:[/yellow] brew installs system-level packages. "
            "These may not be visible to your current Python environment."
        )

    console.print(
        Panel.fit(
            f"Auto-installing [bold]{len(missing_pips)} package(s)[/bold] "
            f"via [cyan]{label}[/cyan]…\n\n"
            f"[dim]{' '.join(cmd)}[/dim]",
            title=f"Auto-Fix ({label})",
            border_style="cyan",
        )
    )

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(
                f"{label} install {pkg_str}", total=None
            )
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
            )
            progress.update(task, completed=True)

        if result.returncode != 0:
            console.print(
                f"\n[red]Installation failed (exit {result.returncode})[/red]"
            )
            stderr_tail = result.stderr.strip().split("\n")[-8:]
            if stderr_tail:
                console.print(
                    Panel("\n".join(stderr_tail),
                          title=f"{label} stderr",
                          border_style="red")
                )
            raise typer.Exit(1)

        console.print(f"\n[bold green]✓ Packages installed via {label}.[/bold green]")

        # Re-verify
        still_missing: list[str] = []
        for mod, pip_name in zip(missing_imports, missing_pips):
            try:
                importlib.import_module(mod)
                console.print(f"  [green]✓[/green] {pip_name} now importable")
            except ImportError:
                console.print(f"  [red]✗[/red] {pip_name} still missing")
                still_missing.append(pip_name)

        if still_missing:
            console.print(
                f"\n[red]{len(still_missing)} package(s) could not be "
                f"installed.[/red]"
            )
            raise typer.Exit(1)

        console.print(
            "\n[bold green]All Python dependencies are now satisfied.[/bold green]"
        )

    except FileNotFoundError:
        console.print(
            f"\n[red]Cannot find [cyan]{label}[/cyan].[/red] "
            "Is it installed and on your PATH?"
        )
        raise typer.Exit(1)


def _find_exe_in_dir(directory: Path) -> Path | None:
    """Find an ECHO2D executable in *directory*, handling platform suffixes.

    On Windows the binary is ``ECHO2D.exe``; on Unix it is ``ECHO2D``.
    Returns the first match found, or ``None``.
    """
    for name in ("ECHO2D.exe", "ECHO2D"):
        candidate = directory / name
        if candidate.is_file():
            return candidate
    return None


def _collect_output(work_dir: Path, dest_dir: Path, symmetry: str) -> None:
    """Collect ECHO2D output files from *work_dir* into *dest_dir*.

    Moves wake files, field data, and logs produced by a single
    sub-run into the appropriate output subdirectory.
    """
    # Wake files
    for pattern in ("wakeL_*.txt", "Wcc_*.txt", "Wss_*.txt", "Iz0.txt"):
        for f in work_dir.glob(pattern):
            dest = dest_dir / f.name
            if not dest.exists():
                shutil.move(str(f), str(dest))
    # Log files
    for f in work_dir.glob("*.log"):
        dest = dest_dir / f.name
        if not dest.exists():
            shutil.move(str(f), str(dest))
    # Field monitor data (if any)
    for child in work_dir.iterdir():
        if child.is_dir() and child.name.startswith("FieldMonitor"):
            dest = dest_dir / child.name
            if not dest.exists():
                shutil.move(str(child), str(dest))



def _serialize_geo(geo: dict) -> dict:
    """Serialize geometry dict to JSON-compatible format."""
    result = {
        "materials": [],
    }
    for mat in geo.get("materials", []):
        m = {
            "epsilon": mat["epsilon"],
            "mu": mat["mu"],
            "sigma": mat["sigma"],
            "segments": [],
        }
        for idx in mat.get("segments", []):
            seg = geo["segments"][idx]
            m["segments"].append({
                "z1": seg["z1"],
                "z2": seg["z2"],
                "r1": seg["r1"],
                "r2": seg["r2"],
                "d": seg.get("d", 1),
                "k": seg.get("k", 0.0),
            })
        result["materials"].append(m)
    return result


def _write_pipe_default(
    out_path: Path,
    radius: float = 2.0,
    inner_radius: float = 1.0,
    section_length: float = 5.0,
) -> None:
    """Write a simple pipe-step-pipe geometry file.

    Creates a symmetric structure:
      pipe(radius) → step → pipe(inner_radius) → step → pipe(radius)

    The format is universal — use ``GeometryType=round`` or ``recta``
    in ``input_in.txt`` to control the interpretation.
    """
    z0 = 0.0
    z1 = section_length
    z2 = 2 * section_length
    z3 = 3 * section_length

    content = (
        f"% Number of materials\n"
        f"1\n"
        f"% Number of elements in metal with conductive walls, "
        f"permeability, permitivity, conductivity\n"
        f"5 1 1 0\n"
        f"% Segments of lines and elipses with conductivity\n"
        f"{z0}\t{radius}\t{z1}\t{radius}\t0\t0\t0\t0\t1\t0\n"
        f"{z1}\t{radius}\t{z1}\t{inner_radius}\t0\t0\t0\t0\t1\t0\n"
        f"{z1}\t{inner_radius}\t{z2}\t{inner_radius}\t0\t0\t0\t0\t1\t0\n"
        f"{z2}\t{inner_radius}\t{z2}\t{radius}\t0\t0\t0\t0\t1\t0\n"
        f"{z2}\t{radius}\t{z3}\t{radius}\t0\t0\t0\t0\t1\t0\n"
    )
    out_path.write_text(content, encoding="utf-8")


def _write_pipe_from_segments(out_path: Path, spec: str) -> None:
    """Write a pipe geometry from a segment specification string.

    Format: "r:2.0,l:5.0;r:1.0,l:5.0;r:2.0,l:5.0"
    Each segment: r=<radius>, l=<length>
    """
    segs: list[tuple[float, float]] = []
    for part in spec.split(";"):
        part = part.strip()
        if not part:
            continue
        kv = {}
        for item in part.split(","):
            item = item.strip()
            if ":" in item:
                k, v = item.split(":", 1)
                kv[k.strip()] = float(v.strip())
        r = kv.get("r", kv.get("y", 1.0))
        l = kv.get("l", 1.0)
        segs.append((r, l))

    if not segs:
        segs = [(2.0, 5.0)]

    lines = [
        "% Number of materials",
        "1",
        "% Number of elements in metal with conductive walls, "
        "permeability, permitivity, conductivity",
        f"{len(segs)} 1 1 0",
        "% Segments of lines and elipses with conductivity",
    ]

    z = 0.0
    for r, l in segs:
        z_next = z + l
        lines.append(
            f"{z}\t{r}\t{z_next}\t{r}\t0\t0\t0\t0\t1\t0"
        )
        z = z_next

    out_path.write_text("\n".join(lines), encoding="utf-8")


def _write_dlw_geometry(
    out_path: Path,
    half_gap: float = 5.0,
    thickness: float = 2.0,
    length: float = 80.0,
    epsilon_r: float = 5.6,
) -> None:
    """Write a recta DLW geometry file to *out_path*."""
    a = half_gap
    d = thickness
    L = length
    b = a + d

    content = (
        f"% Number of materials\n"
        f"2\n"
        f"% Number of elements in metal with conductive walls, "
        f"permeability, permitivity, conductivity\n"
        f"1 1 1 0\n"
        f"% Segments of lines and elipses with conductivity\n"
        f"0\t{b}\t{L}\t{b}\t0\t0\t0\t0\t1\t0\n"
        f"% Number of elements in material 1, permitivity, "
        f"permeability, conductivity\n"
        f"4 {epsilon_r} 1 0\n"
        f"% Segments of lines and elipses\n"
        f"0\t{a}\t0\t{b}\t0\t0\t0\t0\t1\t0\n"
        f"0\t{b}\t{L}\t{b}\t0\t0\t0\t0\t1\t0\n"
        f"{L}\t{b}\t{L}\t{a}\t0\t0\t0\t0\t1\t0\n"
        f"{L}\t{a}\t0\t{a}\t0\t0\t0\t0\t1\t0\n"
    )
    out_path.write_text(content, encoding="utf-8")


def _generate_corrugated_geometry(
    out_path: Path,
    gap: float = 5.0,
    depth: float = 2.0,
    corr_gap: float = 3.0,
    period: float = 5.0,
    num_periods: int = 10,
) -> None:
    """Write a recta corrugated dechirper geometry file to *out_path*.

    The structure alternates between narrow-gap and wide-gap sections:
    - Narrow gap (corrugation tooth): half_gap = corr_gap
    - Wide gap (cavity):            half_gap = gap + depth

    Each period = 4 segments: step-down, narrow, step-up, wide.
    The geometry uses a single material (conductive wall).
    All coordinates in the geometry file are in the units specified
    by ``Units`` in ``input_in.txt`` (typically mm for dechirpers).

    Reference: Phys. Rev. STAB 18, 104401 (2015), N6 example.
    """
    p2 = period / 2.0  # half-period width
    a_narrow = corr_gap
    a_wide = gap + depth
    L_total = num_periods * period
    n_seg_total = 4 * num_periods + 1  # +1 for lead-in pipe

    lines = [
        f"% Corrugated dechirper geometry (recta)",
        f"% a_gap={gap} mm  h={depth} mm  g={corr_gap} mm  "
        f"p={period} mm  N={num_periods}",
        f"% Total length: {L_total} mm",
        f"% Number of materials",
        f"1",
        f"% Number of elements in metal with conductive walls, "
        f"permeability, permitivity, conductivity",
        f"{n_seg_total} 1 1 0",
        f"% Segments of lines and elipses with conductivity",
    ]

    # Lead-in: a short pipe at the wide gap radius (1 mm before first tooth)
    lead_in = -1.0
    lines.append(
        f"{lead_in}\t{a_wide}\t0\t{a_wide}\t0\t0\t0\t0\t1\t0"
    )

    z = 0.0
    for i in range(num_periods):
        # Step DOWN: wide → narrow
        lines.append(
            f"{z}\t{a_wide}\t{z}\t{a_narrow}\t0\t0\t0\t0\t1\t0"
        )
        # Narrow horizontal section
        z_narrow_end = z + p2
        lines.append(
            f"{z}\t{a_narrow}\t{z_narrow_end}\t{a_narrow}\t0\t0\t0\t0\t1\t0"
        )
        # Step UP: narrow → wide
        lines.append(
            f"{z_narrow_end}\t{a_narrow}\t{z_narrow_end}\t{a_wide}\t0\t0\t0\t0\t1\t0"
        )
        z = z_narrow_end
        # Wide horizontal section
        z_wide_end = z + p2
        lines.append(
            f"{z}\t{a_wide}\t{z_wide_end}\t{a_wide}\t0\t0\t0\t0\t1\t0"
        )
        z = z_wide_end

    out_path.write_text("\n".join(lines), encoding="utf-8")



def _plot_monitor_slice(
    monitor_or_data: Any,
    *,
    title: str = "",
    output: str | None = None,
    no_show: bool = False,
    time_step: int = 0,
) -> None:
    """Plot a 2-D slice from a field monitor or raw numpy array.

    For 3-D monitor data (kt, kz, kr), takes a slice at *time_step*.
    For 2-D data, plots directly.
    Falls back to line plot if dimensions don't match.

    Parameters
    ----------
    monitor_or_data : MonitorData or np.ndarray
        MonitorData object (with F/Z/R attrs) or raw 2-D field array.
    title : str
        Plot title.
    output : str, optional
        Save plot to file.
    no_show : bool
        If True, do not display plot window.
    time_step : int
        Time slice index for 3-D data.
    """
    import matplotlib.pyplot as plt

    if hasattr(monitor_or_data, "F"):
        # MonitorData object
        F = monitor_or_data.F
        Z = getattr(monitor_or_data, "Z", None)
        R = getattr(monitor_or_data, "R", None)
    else:
        F = monitor_or_data
        Z = None
        R = None

    # For 3-D data, take a time slice
    if F.ndim == 3:
        idx = min(time_step, F.shape[0] - 1)
        F = F[idx, :, :]
    elif F.ndim == 1:
        # 1-D trace: simple line plot
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(F, linewidth=1.2)
        ax.set_xlabel("Index")
        ax.set_ylabel("Field")
        ax.set_title(title or "Field Monitor")
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        if output:
            fig.savefig(output.replace(".txt", ".png"), dpi=150, bbox_inches="tight")
        if not no_show:
            plt.show()
        else:
            plt.close(fig)
        return

    n_rows, n_cols = F.shape
    if Z is None:
        Z = np.arange(n_cols)
    if R is None:
        R = np.arange(n_rows)

    # Smooth 2-D pseudocolor with contour overlay
    from pyecho.postprocess.fields import _plot_field_2d
    fig, ax = plt.subplots(figsize=(10, 6))
    _plot_field_2d(ax, Z, R, F)
    fig.colorbar(ax.collections[0], ax=ax, label="Field")
    ax.set_xlabel("z [mm]")
    ax.set_ylabel("r/y [mm]")
    ax.set_title(title or "Field Monitor")
    fig.tight_layout()

    if output:
        fig.savefig(output.replace(".txt", ".png"), dpi=150, bbox_inches="tight")
        console.print(f"  [dim]Plot saved to {output.replace('.txt', '.png')}[/dim]")
    if not no_show:
        plt.show()
    else:
        plt.close(fig)


def _save_monitor_total(
    out_path: Path,
    F: "np.ndarray",
    component: str,
    time_type: str,
    D: float,
    T: "np.ndarray | None" = None,
    Z: "np.ndarray | None" = None,
    R: "np.ndarray | None" = None,
) -> None:
    """Save synthesised total field in ECHO2D MonitorTotal format.

    Writes a header compatible with ``PP_FieldMonitor_rect.m`` /
    ``PP_FieldMonitor_round.m`` and the data matrix.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # F is 2-D: (kt, kz*kr) after synthesis (flat array)
    if F.ndim == 2:
        kt = F.shape[0]
        k_space = F.shape[1]
    else:
        kt = F.shape[0]
        k_space = F.shape[1] * F.shape[2]

    k_ct = kt
    h_ct = (T[1] - T[0]) if T is not None and len(T) > 1 else 1.0
    ct0 = float(T[0]) if T is not None else 0.0
    kr = len(R) if R is not None else 1
    hr = (R[1] - R[0]) if R is not None and len(R) > 1 else 1.0
    r0 = float(R[0]) if R is not None else 0.0

    lines = [
        f"% Field={component} time={time_type}  width={D:.6e}",
        f"% k_ct={k_ct} h_ct={h_ct:.6e} ct0={ct0:.6e}",
        f"% k_r={kr} h_r={hr:.6e} r0={r0:.6e}",
    ]
    if time_type == "s":
        kz = len(Z) if Z is not None else k_space // kr
        hz = (Z[1] - Z[0]) if Z is not None and len(Z) > 1 else 1.0
        z0 = float(Z[0]) if Z is not None else 0.0
        lines.append(f"% k_z={kz} h_z={hz:.6e} z0={z0:.6e}")
    else:
        ks = len(Z) if Z is not None else k_space // kr
        hs = abs(Z[1] - Z[0]) if Z is not None and len(Z) > 1 else 1.0
        s0 = abs(float(Z[0])) if Z is not None else 0.0
        lines.append(f"% k_s={ks} h_s={hs:.6e} s0={s0:.6e}")

    # Write header + flattened data
    header = "\n".join(lines) + "\n"
    # Flatten F to 2-D if needed
    F_flat = F.reshape(F.shape[0], -1) if F.ndim == 3 else F
    # Prepend T column (ct for s-type, or use index for z-type)
    if T is not None:
        out = np.column_stack([T, F_flat])
    else:
        out = np.column_stack([np.arange(kt) * h_ct + ct0, F_flat])
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(header)
        np.savetxt(f, out, fmt="%.6e")


def _resolve_plot_data_dir(output_dir: str) -> Path:
    """Find the data directory for bunch loading.

    Searches for round/, magn/, or elec/ subdirectory depending on
    geometry type.  If output_dir itself is already the data directory,
    use it directly.
    """
    p = Path(output_dir)
    if p.name in ("round", "magn", "elec"):
        return p
    for sub in ("round", "magn", "elec"):
        if (p / sub).is_dir():
            return p / sub
    return p


def _read_offset_from_dir(data_dir: Path) -> int:
    """Read the bunch offset from a wakeL file in the data directory."""
    import glob
    wake_files = sorted(glob.glob(str(data_dir / "wakeL_*.txt")))
    if not wake_files:
        return 0
    with open(wake_files[0]) as f:
        for line in f:
            if line.startswith("%"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                return int(float(parts[1]))
    return 0


def _find_processed_dir(output_dir: Path) -> Path:
    """Find or create the processed/ directory for a run or project.

    Walks up from *output_dir* looking for a run directory
    (contains ``.run.yaml``) or project root (contains
    ``.echo2d.yaml``), then returns ``<root>/processed/``.
    Falls back to ``output_dir/processed/``.
    """
    current = output_dir
    for _ in range(10):
        if (current / ".run.yaml").is_file():
            return current / "processed"
        if (current / ".echo2d.yaml").is_file():
            return current / "processed"
        parent = current.parent
        if parent == current:
            break
        current = parent
    # Fallback: create processed/ under the output_dir
    return output_dir / "processed"


def _try_update_processed_manifest(
    output_dir: Path,
    loss_long: float | None = None,
    kick_quad: float | None = None,
    kick_dipole: float | None = None,
    peak: float | None = None,
) -> None:
    """Update .run.yaml with processed wake results, best-effort."""
    try:
        from pyecho.project import find_project_root, update_processed

        # Find the run directory from output_dir
        current = output_dir
        run_dir = None
        for _ in range(10):
            if (current / ".run.yaml").is_file():
                run_dir = current
                break
            parent = current.parent
            if parent == current:
                break
            current = parent

        if run_dir is not None:
            update_processed(
                run_dir,
                loss_long=loss_long,
                kick_quad=kick_quad,
                kick_dipole=kick_dipole,
                peak=peak,
            )
    except Exception:
        pass  # best-effort, don't break on manifest update failure


def _save_wake_round_data(
    s: "np.ndarray",
    W: "np.ndarray",
    label: str,
    units: str,
    out_path: Path,
) -> None:
    """Save a single round-geometry wake component to disk.

    Parameters
    ----------
    s : np.ndarray
        s-coordinate [m].
    W : np.ndarray
        Wake potential data.
    label : str
        Component label (e.g. ``"monopole"``, ``"dipole"``).
    units : str
        Physical units string.
    out_path : Path
        Output file path.
    """
    import numpy as np
    out_path.parent.mkdir(parents=True, exist_ok=True)
    data = np.column_stack((s, W))
    header = (
        f"# {label} wake (round geometry)\n"
        f"# s [mm]  W [{units}]"
    )
    np.savetxt(str(out_path), data, header=header, fmt="%.8e")


def _save_wake_flat(result: Any, out_dir: Path) -> None:
    """Save recta (rectangular) wake result to disk.

    Writes
    ------
    Wlong.txt
        Two-column: s [mm], Wlong [V/pC].
    Wquad.txt
        Two-column: s [mm], Wquad [V/pC/mm].
    Wdipole.txt
        Two-column: s [mm], Wdipole [V/pC/mm] (if non-zero).
    summary.txt
        Loss factor, quad/dipole kick factors.
    """
    import numpy as np
    out_dir.mkdir(parents=True, exist_ok=True)

    def _save_col(name: str, y: "np.ndarray", unit: str) -> None:
        data = np.column_stack((result.s, y))
        header = f"# {name} wake (recta geometry)\n# s [mm]  W [{unit}]"
        np.savetxt(out_dir / f"{name}.txt", data, header=header, fmt="%.8e")

    _save_col("wake_longitudinal", result.Wlong, "V/pC")
    _save_col("wake_quadrupole", result.Wquad, "V/pC/mm")

    if hasattr(result, "Wdipole") and np.any(result.Wdipole):
        _save_col("wake_dipole", result.Wdipole, "V/pC/mm")

    # summary
    summary = (
        f"Geometry: rectangular (recta)\n"
        f"Longitudinal loss: {result.loss_long:.6f} V/pC\n"
        f"Quadrupole kick:   {result.kick_quad:.6f} V/pC/mm\n"
        f"Dipole kick:       {result.kick_dipole:.6f} V/pC/mm\n"
    )
    (out_dir / "summary.txt").write_text(summary, encoding="utf-8")




# ===================================================================
# Entry point
# ===================================================================

if __name__ == "__main__":
    app()
