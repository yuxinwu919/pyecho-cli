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
import sys
from pathlib import Path
from typing import Annotated, Optional

import numpy as np
import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.syntax import Syntax
from rich.tree import Tree

from pyecho._version import __version__

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = typer.Typer(
    rich_markup_mode="rich",
    name="echo2d",
    help="ECHO2D — accelerator wakefield / impedance solver toolkit.  "
         "Run 'echo2d <command> --help' for detailed usage.",
    add_completion=False,
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
test_app = typer.Typer(help="Testing and validation")
system_app = typer.Typer(help="System information")

app.add_typer(project_app, name="project")
app.add_typer(geometry_app, name="geometry")
app.add_typer(config_app, name="config")
app.add_typer(run_app, name="run")
app.add_typer(postprocess_app, name="postprocess")
app.add_typer(visualize_app, name="visualize")
app.add_typer(export_app, name="export")
app.add_typer(compare_app, name="compare")
app.add_typer(test_app, name="test")
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
            "Default = magn symmetry (longitudinal + quadrupole); "
            "use --symmetry elec for dipole wake."
        ),
        "geometry": "flat_absorber.txt",
        "params": {
            "units": "cm",
            "geometry_type": "recta",
            "width": 0.07,
            "symmetry": "magn",
            "bunch_sigma": 0.004,
            "offset": -1,
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


def _generate_input_in(
    out_path: Path,
    geometry_file: str,
    *,
    units: str = "cm",
    geometry_type: str = "round",
    width: float = 0.0,
    symmetry: str = "magn",
    bunch_sigma: float = 0.001,
    offset: int = -1,
    modes: str = "0",
    mesh_length: int = 52,
    step_y: float = 0.0002,
    step_z: float = 0.0002,
    adjust_mesh: int = 1,
    wake_method: str = "ind",
) -> None:
    """Generate an ECHO2D ``input_in.txt`` file."""
    content = f"""%%%%%%%%%%%%%% geometry %%%%%%%%%%%%%%%%%%%%

GeometryFile={geometry_file}	% -(Gaussian beam)
Units={units}	% -m/cm/mm
GeometryType={geometry_type}	 % recta / round
Width={width}	% in meters
SymmetryCondition={symmetry}	 % magn/elec
Convex=1

%%%%%%%%%%%%%% beam %%%%%%%%%%%%%%%%%%%%%%%%

InPartFile=-
BunchSigma={bunch_sigma}
Offset={offset}
InjectionTimeStep=0

%%%%%%%%%%%%%%  field %%%%%%%%%%%%%%%%%%%%%%

InFieldDir=-
PortDir=-
PortPosition=-1

%%%%%%%%%%%%%% model %%%%%%%%%%%%%%%%%%%%%%%

WakeIntMethod={wake_method}
Modes={modes} 
ParticleMotion=0
ParticleField=1
CurrentFilter=0
ParticleLoss=0

%%%%%%%%%%%%%% mesh %%%%%%%%%%%%%%%%%%%%%%%

MeshLength={mesh_length}
StartPosition=0
TimeSteps=-1
StepY={step_y}
StepZ={step_z}
NStepsInConductive=0
AdjustMesh={adjust_mesh}
MeshMotionFile=-

%%%%%%%%%%%%%% monitors %%%%%%%%%%%%%%%%%%%%%%%

DumpField=0
DumpParticles=0
DumpCurrent=0
DumpMesh=0
"""
    out_path.write_text(content, encoding="utf-8")


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
        elif isinstance(result, WakeResult):
            lines.append("")
            lines.append(
                f"  Loss factor:  [cyan]{result.loss_factor:.6f} V/pC[/cyan]"
            )
            lines.append(
                f"  Peak:         [cyan]{result.peak:.4f} V/pC[/cyan]"
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
            autocompletion=lambda: list(_EXAMPLES.keys()),
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
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview steps without executing"),
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
      echo2d example                          # list examples
      echo2d example round-collimator         # run with defaults
      echo2d example flat-absorber -o mydemo  # custom output dir
      echo2d example tesla-cavity --no-run    # only generate files
    """
    # Merge deprecated --np alias
    if _np_alias is not None:
        threads = _np_alias

    # ── No name → list examples ──
    if not name:
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
        console.print(f"[red]Unknown example '{name}'.[/red]")
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

    # ── Dry run ──
    steps = [
        f"Create directory [cyan]{out_dir}[/cyan]",
        f"Copy geometry [cyan]{ex['geometry']}[/cyan]",
        f"Generate [cyan]input_in.txt[/cyan]",
        f"Run ECHO2D solver ({threads} thread(s))",
        f"Postprocess wake data",
    ]
    if dry_run:
        lines = "\n".join(
            f"  [bold]Step {i+1}[/bold]  {s}" for i, s in enumerate(steps)
        )
        console.print(Panel.fit(lines, title=f"Example: {name}"))
        return

    # ── Execute ──
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # Step 1: create output dir
        task = progress.add_task("Creating output directory...", total=None)
        out_dir.mkdir(parents=True, exist_ok=True)
        progress.update(
            task, completed=True,
            description=f"[green]✓[/green] Directory [cyan]{out_dir}[/cyan]"
        )

        # Step 2: copy geometry
        task = progress.add_task("Copying geometry file...", total=None)
        geo_src = _TEMPLATES_DIR / ex["geometry"]
        if not geo_src.exists():
            console.print(
                f"[red]Template not found: {geo_src}[/red]"
            )
            raise typer.Exit(1)
        geo_dst = out_dir / ex["geometry"]
        geo_dst.write_bytes(geo_src.read_bytes())
        progress.update(
            task, completed=True,
            description="[green]✓[/green] Geometry copied"
        )

        # Step 3: generate input_in.txt
        task = progress.add_task("Generating input_in.txt...", total=None)
        _generate_input_in(
            out_dir / "input_in.txt",
            ex["geometry"],
            units=p["units"],
            geometry_type=p["geometry_type"],
            width=p["width"],
            symmetry=p["symmetry"],
            bunch_sigma=p["bunch_sigma"],
            offset=p["offset"],
            modes=p["modes"],
            mesh_length=p["mesh_length"],
            step_y=p["step_y"],
            step_z=p["step_z"],
            adjust_mesh=p["adjust_mesh"],
        )
        progress.update(
            task, completed=True,
            description="[green]✓[/green] input_in.txt generated"
        )

        if no_run:
            progress.stop()
            console.print()
            console.print(
                f"[bold green]✓[/bold green] Files ready in "
                f"[cyan]{out_dir}[/cyan]"
            )
            console.print(
                f"  Run: [dim]cd {out_dir} && "
                f"echo2d run single --threads {threads}[/dim]"
            )
            return

        # Step 4: run ECHO2D
        task = progress.add_task(
            f"Running ECHO2D solver ({threads} threads)...",
            total=None,
        )
        from pyecho.runner import ECHO2DRunner

        runner = ECHO2DRunner(work_dir=str(out_dir))
        try:
            result = runner.run(
                np=threads,
                show_progress=False,
            )
            elapsed = result.metadata.elapsed_seconds
            progress.update(
                task, completed=True,
                description=(
                    f"[green]✓[/green] Simulation complete "
                    f"([dim]{elapsed:.1f}s[/dim])"
                ),
            )
        except Exception as exc:
            progress.update(
                task, completed=True,
                description=f"[red]✗[/red] Simulation failed: {exc}",
            )
            console.print(f"[red]Error: {exc}[/red]")
            raise typer.Exit(1)

        # Step 5: postprocess
        task = progress.add_task("Postprocessing wake data...", total=None)
        try:
            from pyecho.api import quick_postprocess
            from pyecho.datamodel import FlatWakeResult, WakeResult

            result = quick_postprocess(str(out_dir), geometry=p["geometry_type"])
            progress.update(
                task, completed=True,
                description="[green]✓[/green] Postprocessing done",
            )
        except Exception as exc:
            progress.update(
                task, completed=True,
                description=f"[yellow]⚠[/yellow] Postprocess warning: {exc}",
            )
            result = None

    # ── Summary ──
    console.print()
    _print_example_summary(out_dir, name, ex, result, p)

    # ── Plot (if requested) ──
    if not no_plot and result is not None:
        console.print("[dim]Launching plot...[/dim]")
        try:
            import matplotlib.pyplot as plt

            if isinstance(result, FlatWakeResult):
                from pyecho.visualize import plot_flat_wake
                data_dir = _resolve_plot_data_dir(str(out_dir))
                offset = _read_offset_from_dir(data_dir)
                from pyecho.parser import load_bunch_profile
                _, bunch = load_bunch_profile(data_dir, offset, result.s)
                plot_flat_wake(result, bunch=bunch)
            else:
                from pyecho.visualize import plot_wake_round
                plot_wake_round(result)
            plt.show()
        except Exception as exc:
            console.print(f"[yellow]⚠ Plot error: {exc}[/yellow]")


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
    config_file: Annotated[
        Optional[str],
        typer.Option("--config", "-c", help="Config file path"),
    ] = None,
    version: Annotated[
        bool,
        typer.Option("--version", help="Show version and exit"),
    ] = False,
) -> None:
    """ECHO2D — accelerator wakefield / impedance solver toolkit.

    Based on the ECHO2D solver by Igor Zagorodnov (DESY).
    Official site: https://echo4d.de

    Quick start:
      echo2d project init myproj -t round_collimator --force
      cd myproj && echo2d run single -d . --threads 4
      echo2d postprocess wake round/ --plot
    """
    if version:
        console.print(f"[bold]echo2d[/bold] version [cyan]{__version__}[/cyan]")
        console.print(f"Python [cyan]{sys.version}[/cyan]")
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

    if config_file:
        console.print(f"[dim]Using config: {config_file}[/dim]")

    # Store in context for subcommands
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["config_file"] = config_file


# ===================================================================
# project commands
# ===================================================================

@project_app.command("init")
def project_init(
    name: Annotated[str, typer.Argument(help="Project name")],
    template: Annotated[
        str,
        typer.Option("--template", "-t", help="Project template"),
    ] = "empty",
    example: Annotated[
        Optional[str],
        typer.Option("--example", "-e", help="Example to copy from"),
    ] = None,
    directory: Annotated[
        Optional[str],
        typer.Option("--dir", "-d", help="Target directory"),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Overwrite existing directory"),
    ] = False,
) -> None:
    """Initialize a new ECHO2D project."""
    target = Path(directory or name)
    if target.exists() and not force:
        console.print(f"[red]Directory '{target}' already exists. Use --force to overwrite.[/red]")
        raise typer.Exit(1)

    target.mkdir(parents=True, exist_ok=force)

    # Create basic project structure
    (target / "geometry").mkdir(exist_ok=True)
    (target / "results").mkdir(exist_ok=True)
    (target / "postprocess").mkdir(exist_ok=True)

    # Write a minimal input_in.txt
    input_content = _generate_template_input(template)
    (target / "input_in.txt").write_text(input_content, encoding="utf-8")

    # Auto-generate geometry for DLW template
    if template == "dlw":
        _generate_dlw_geometry(target)

    # Write README
    if template == "dlw":
        readme = _generate_dlw_readme(name)
    else:
        readme = f"# {name}\n\nECHO2D simulation project.\n"
    (target / "README.md").write_text(readme, encoding="utf-8")

    console.print(
        Panel.fit(
            f"[bold green]✓[/bold green] Project '{name}' created at [cyan]{target.resolve()}[/cyan]",
            title="Project Initialized",
        )
    )

    tree = Tree("Project structure")
    tree.add("geometry/")
    tree.add("results/")
    tree.add("postprocess/")
    tree.add("input_in.txt")
    if template == "dlw":
        tree.add("dlw.txt")
    tree.add("README.md")
    console.print(tree)


@project_app.command("templates")
def project_templates() -> None:
    """List available project templates."""
    from pyecho.config import ECHO2DParams

    templates = ECHO2DParams.list_templates()

    table = Table(title="Available Templates")
    table.add_column("Name", style="cyan")
    table.add_column("Description", style="green")

    descriptions = {
        "round_collimator": "Rotationally symmetric collimator (round)",
        "flat_absorber": "Rectangular photon absorber (flat)",
        "tesla_cavity": "TESLA 9-cell superconducting cavity",
        "dlw": "Dielectric lined waveguide (DLW)",
    }

    for t in templates:
        table.add_row(t, descriptions.get(t, "—"))

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
    status: Annotated[
        bool,
        typer.Option("--status", "-s", help="Show status of each project"),
    ] = False,
    sort_by: Annotated[
        str,
        typer.Option("--sort", help="Sort by: name, date"),
    ] = "name",
) -> None:
    """List local projects in the workspace."""
    cwd = Path.cwd()
    projects: list[Path] = []

    # Find directories with input_in.txt
    for d in cwd.iterdir():
        if d.is_dir() and (d / "input_in.txt").exists():
            projects.append(d)

    if not projects:
        console.print("[yellow]No ECHO2D projects found in current directory.[/yellow]")
        return

    table = Table(title="Local Projects")
    table.add_column("Project", style="cyan")
    table.add_column("Path", style="dim")
    if status:
        table.add_column("Status", style="yellow")

    for p in sorted(projects, key=lambda x: x.name if sort_by == "name" else x.stat().st_mtime):
        has_results = (p / "round").is_dir() or (p / "magn").is_dir() or (p / "elec").is_dir()
        if status:
            table.add_row(p.name, str(p), "✓ Has results" if has_results else "○ No results")
        else:
            table.add_row(p.name, str(p))

    console.print(table)


@project_app.command("info")
def project_info(
    project_dir: Annotated[
        str,
        typer.Option("--dir", "-d", help="Project directory"),
    ] = ".",
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output as JSON"),
    ] = False,
) -> None:
    """Show project information."""
    pdir = Path(project_dir).resolve()
    input_file = pdir / "input_in.txt"

    if not input_file.exists():
        console.print(f"[red]No input_in.txt found in {pdir}[/red]")
        raise typer.Exit(1)

    from pyecho.config import load_params

    try:
        params = load_params(input_file)
    except Exception as exc:
        console.print(f"[red]Failed to parse input file: {exc}[/red]")
        raise typer.Exit(1)

    if json_output:
        console.print_json(params.model_dump_json(indent=2))
        return

    # Rich output
    console.print(Panel.fit(f"[bold]Project: {pdir.name}[/bold]", title="Project Info"))

    table = Table(title="Configuration")
    table.add_column("Parameter", style="cyan")
    table.add_column("Value", style="green")

    key_params = [
        "GeometryFile", "GeometryType", "Units",
        "BunchSigma", "Modes", "StepY", "StepZ",
        "MeshLength", "TimeSteps",
    ]
    for key in key_params:
        val = getattr(params, key, "—")
        table.add_row(key, str(val))

    console.print(table)


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
            help="Structure type: pipe (step-in/out), dlw, corrugated",
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
    units: Annotated[
        str,
        typer.Option("--units", "-u", help="Units: cm, mm, m"),
    ] = "cm",
    geometry_type: Annotated[
        str,
        typer.Option("--type", "-t", help="Geometry type"),
    ] = "round",
) -> None:
    """Validate a geometry file."""
    from pyecho.geometry import load_geometry

    try:
        geo = load_geometry(geometry_file)
    except Exception as exc:
        console.print(f"[red]✗ Validation failed: {exc}[/red]")
        raise typer.Exit(1)

    n_seg = len(geo.get("segments", []))
    n_mat = len(geo.get("materials", []))

    console.print(
        Panel.fit(
            f"[bold green]✓[/bold green] Geometry is valid.\n"
            f"  Materials: {n_mat}\n"
            f"  Segments:  {n_seg}",
            title="Validation Result",
        )
    )


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
        console.print(f"[red]Failed to plot geometry: {exc}[/red]")
        raise typer.Exit(1)

    if output:
        fig.savefig(output, dpi=150, bbox_inches="tight")
        console.print(f"[green]Plot saved to {output}[/green]")

    if not no_show:
        import matplotlib.pyplot as plt
        plt.show()


@geometry_app.command("info")
def geometry_info(
    geometry_file: Annotated[str, typer.Argument(help="Geometry file path")],
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output as JSON"),
    ] = False,
) -> None:
    """Show geometry information."""
    from pyecho.geometry import load_geometry

    try:
        geo = load_geometry(geometry_file)
    except Exception as exc:
        console.print(f"[red]Failed to load geometry: {exc}[/red]")
        raise typer.Exit(1)

    if json_output:
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
        typer.Option("--template", "-t", help="Template name"),
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
        str,
        typer.Argument(help="Input file path"),
    ] = "input_in.txt",
) -> None:
    """Validate input_in.txt."""
    from pyecho.config import load_params

    try:
        params = load_params(input_file)
    except Exception as exc:
        console.print(f"[red]✗ Validation failed: {exc}[/red]")
        raise typer.Exit(1)

    console.print(
        Panel.fit(
            f"[bold green]✓[/bold green] Configuration is valid.\n"
            f"  Geometry: {params.GeometryFile} ({params.GeometryType})\n"
            f"  Bunch σ:  {params.BunchSigma} m\n"
            f"  Modes:    {params.Modes}\n"
            f"  Mesh:     h_y={params.StepY}, h_z={params.StepZ}",
            title="Validation Result",
        )
    )


@config_app.command("show")
def config_show(
    input_file: Annotated[
        str,
        typer.Argument(help="Input file path"),
    ] = "input_in.txt",
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output as JSON"),
    ] = False,
) -> None:
    """Display configuration."""
    from pyecho.config import load_params

    try:
        params = load_params(input_file)
    except Exception as exc:
        console.print(f"[red]Failed to parse {input_file}: {exc}[/red]")
        raise typer.Exit(1)

    if json_output:
        console.print_json(params.model_dump_json(indent=2))
        return

    table = Table(title=f"Configuration: {input_file}")
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
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show what would be executed"),
    ] = False,
) -> None:
    """Run a single ECHO2D simulation."""
    from pyecho.runner import ECHO2DRunner
    from pyecho.config import load_params

    wdir = Path(work_dir).resolve()

    # Load params
    params = None
    if config:
        params = load_params(config)
    elif (wdir / "input_in.txt").exists():
        params = load_params(wdir / "input_in.txt")
    else:
        console.print(
            "[red]Error:[/red] No input_in.txt found and no --config specified.\n"
            "Generate one with: [cyan]echo2d config generate[/cyan]"
        )
        raise typer.Exit(1)

    if dry_run:
        console.print(Panel.fit(
            f"Working dir: [cyan]{wdir}[/cyan]\n"
            f"Executable:  [cyan]{executable or 'auto-detect'}[/cyan]\n"
            f"Threads:     [cyan]{np}[/cyan]\n"
            f"Config:      [cyan]{config or 'input_in.txt'}[/cyan]",
            title="Dry Run"
        ))
        return

    # Merge deprecated --np alias into --threads
    if _np_alias is not None:
        np = _np_alias

    try:
        runner = ECHO2DRunner(wdir, executable)
    except Exception as exc:
        console.print(f"[red]Failed to initialize runner: {exc}[/red]")
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
            from rich.progress import Progress, BarColumn, TextColumn, \
                TimeElapsedColumn

            gen = runner.run_stream(params=params, np=np, timeout=timeout)
            result = None
            with Progress(
                TextColumn("[bold blue]ECHO2D"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>5.0f}%"),
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
                pbar.update(task, completed=100,
                            description="Simulation complete")
    except Exception as exc:
        console.print(f"[red]✗ Simulation failed: {exc}[/red]")
        raise typer.Exit(1)

    # Display summary
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


# ===================================================================
# postprocess commands
# ===================================================================

@postprocess_app.command("wake")
def postprocess_wake(
    output_dir: Annotated[str, typer.Argument(help="Output directory")],
    wake_type: Annotated[
        Optional[list[str]],
        typer.Option("--type", "-t", help="Wake type(s)"),
    ] = None,
    geometry: Annotated[
        Optional[str],
        typer.Option("--geometry", "-g", help="Geometry type: round, flat (auto-detected if omitted)"),
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
    """Post-process wake results."""
    from pyecho.api import quick_postprocess

    try:
        result = quick_postprocess(output_dir, geometry=geometry)
    except Exception as exc:
        console.print(f"[red]Post-processing failed: {exc}[/red]")
        raise typer.Exit(1)

    # Display summary
    from pyecho.datamodel import WakeResult, FlatWakeResult

    if isinstance(result, WakeResult):
        console.print(
            Panel.fit(
                f"[bold green]✓ Wake processed[/bold green]\n"
                f"  Label:       [cyan]{result.label}[/cyan]\n"
                f"  Loss factor: [cyan]{result.loss_factor:.6f} V/pC[/cyan]\n"
                f"  Peak:        [cyan]{result.peak:.4f} V/pC[/cyan]\n"
                f"  RMS spread:  [cyan]{result.rms_spread:.4f} V/pC[/cyan]",
                title="Wake Result",
            )
        )
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

    if plot:
        import matplotlib.pyplot as plt
        if isinstance(result, FlatWakeResult):
            from pyecho.visualize import plot_flat_wake
            data_dir = _resolve_plot_data_dir(output_dir)
            offset = _read_offset_from_dir(data_dir)
            from pyecho.parser import load_bunch_profile
            _, bunch = load_bunch_profile(data_dir, offset, result.s)
            fig, axes = plot_flat_wake(result, bunch=bunch)
        else:
            from pyecho.visualize import plot_wake_round
            data_dir = _resolve_plot_data_dir(output_dir)
            offset = _read_offset_from_dir(data_dir)
            from pyecho.parser import load_bunch_profile
            _, bunch = load_bunch_profile(data_dir, offset, None)
            fig, ax = plot_wake_round(result, bunch=bunch)
        if output:
            fig.savefig(f"{output}_wake.png", dpi=150, bbox_inches="tight")
        plt.show()


@postprocess_app.command("all")
def postprocess_all(
    output_dir: Annotated[str, typer.Argument(help="Output directory")],
    auto_detect: Annotated[
        bool,
        typer.Option("--auto-detect/--no-auto-detect", help="Auto-detect geometry type"),
    ] = True,
    skip: Annotated[
        Optional[list[str]],
        typer.Option("--skip", help="Steps to skip"),
    ] = None,
    output_dir_out: Annotated[
        Optional[str],
        typer.Option("--output-dir", "-o", help="Output directory for results"),
    ] = None,
) -> None:
    """Run all post-processing steps (wake + field + particles).

    .. note::

        This command is a **placeholder** — only ``echo2d postprocess wake``
        is currently implemented.  Use that command for wake analysis.
        Full pipeline (auto-detect → wake → field → particles → report)
        is planned for a future release.
    """
    console.print(Panel.fit(
        "[bold yellow]⏳  Planned feature[/bold yellow]\n\n"
        "Full post-processing pipeline is not yet implemented.\n\n"
        "Available now:\n"
        "  [cyan]echo2d postprocess wake <dir>[/cyan] — wake analysis\n"
        "  [cyan]echo2d visualize wake <file>[/cyan]  — wake plotting\n\n"
        "Expected: [cyan]echo2d v0.2.0[/cyan]",
        title="Post-Process All",
    ))


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
        console.print(f"[red]Failed to parse wake file: {exc}[/red]")
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
            console.print(f"[red]Failed to parse {f}: {exc}[/red]")
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
            "[yellow]⚠ Note:[/yellow] Comparing different azimuthal modes "
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
        console.print(f"[red]Failed to plot modal decomposition: {exc}[/red]")
        raise typer.Exit(1)

    if output:
        fig.savefig(output, dpi=150, bbox_inches="tight")
        console.print(f"[green]Plot saved to {output}[/green]")

    if not no_show:
        import matplotlib.pyplot as plt
        plt.show()


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
        console.print(f"[red]Comparison failed: {exc}[/red]")
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
# test commands
# ===================================================================

@test_app.command("suite")
def test_suite(
    examples: Annotated[
        Optional[list[int]],
        typer.Option("--examples", "-e", help="Example indices to test"),
    ] = None,
    timeout: Annotated[
        Optional[int],
        typer.Option("--timeout", "-t", help="Timeout per test in seconds"),
    ] = None,
    parallel: Annotated[
        int,
        typer.Option("--parallel", "-p", help="Number of parallel tests"),
    ] = 1,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Verbose output"),
    ] = False,
) -> None:
    """Run regression test suite against reference results.

    .. note::

        This command is a **placeholder** — automated regression testing
        is planned.  For manual validation, run each example and compare
        with the MATLAB reference outputs in
        ``ECHO2D_v3_5/Examples/*/PostProcessor2D/``.
    """
    console.print(Panel.fit(
        "[bold yellow]⏳  Planned feature[/bold yellow]\n\n"
        "Automated regression tests are not yet implemented.\n\n"
        "Manual workflow:\n"
        "  1. [cyan]echo2d run single[/cyan] on example\n"
        "  2. Run the MATLAB PP_*.m script for reference\n"
        "  3. [cyan]echo2d compare runs[/cyan] to check agreement\n\n"
        "Expected: [cyan]echo2d v0.3.0[/cyan]",
        title="Test Suite",
    ))


@test_app.command("example")
def test_example(
    name: Annotated[str, typer.Argument(help="Example name")],
    keep_results: Annotated[
        bool,
        typer.Option("--keep", help="Keep results after test"),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Verbose output"),
    ] = False,
) -> None:
    """Test a single example against reference.

    .. note::

        This command is a **placeholder**.  See ``echo2d test suite --help``
        for manual validation instructions.
    """
    console.print(Panel.fit(
        "[bold yellow]⏳  Planned feature[/bold yellow]\n\n"
        "Single-example testing is not yet implemented.\n"
        "Expected: [cyan]echo2d v0.3.0[/cyan]",
        title="Test Example",
    ))


@test_app.command("list")
def test_list() -> None:
    """List available test examples."""
    from pyecho.config import ECHO2DParams

    templates = ECHO2DParams.list_templates()

    table = Table(title="Available Test Examples")
    table.add_column("Name", style="cyan")
    table.add_column("Type", style="yellow")

    for t in templates:
        try:
            params = ECHO2DParams.from_template(t)
            gtype = "Round" if params.GeometryType == "round" else "Flat (recta)"
        except Exception:
            gtype = "—"
        table.add_row(t, gtype)

    console.print(table)


# ===================================================================
# system commands
# ===================================================================

@system_app.command("info")
def system_info(
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output as JSON"),
    ] = False,
) -> None:
    """Show system and ECHO2D information."""
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

    if json_output:
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
        console.print(f"[red]✗ Not found: {exc}[/red]")

    # List all available executables
    project_root = Path(__file__).resolve().parent.parent
    codes_dir = project_root / "ECHO2D_v3_5" / "Codes"
    if codes_dir.is_dir():
        console.print("\n[bold]Available executables:[/bold]")
        for child in sorted(codes_dir.iterdir()):
            if child.is_dir():
                exe = child / "ECHO2D"
                status = "[green]✓[/green]" if exe.is_file() else "[red]✗[/red]"
                console.print(f"  {status} {child.name}")


@system_app.command("check")
def system_check(
    fix: Annotated[
        bool,
        typer.Option("--fix", help="Attempt to fix issues"),
    ] = False,
) -> None:
    """Check system dependencies for ECHO2D."""
    import importlib

    console.print("[bold]Checking dependencies...[/bold]\n")

    deps = {
        "numpy": "NumPy",
        "pydantic": "Pydantic",
        "matplotlib": "Matplotlib",
        "typer": "Typer",
        "rich": "Rich",
        "h5py": "HDF5 (h5py)",
    }

    all_ok = True
    for module, name in deps.items():
        try:
            importlib.import_module(module)
            console.print(f"  [green]✓[/green] {name}")
        except ImportError:
            console.print(f"  [red]✗[/red] {name} [dim](not installed)[/dim]")
            all_ok = False

    if all_ok:
        console.print("\n[bold green]All dependencies satisfied.[/bold green]")
    else:
        console.print("\n[yellow]Some dependencies are missing. Install with:[/yellow]")
        console.print("  [dim]pip install numpy pydantic matplotlib typer rich h5py[/dim]")

        if fix:
            console.print("[yellow]Auto-fix not yet implemented.[/yellow]")


# ===================================================================
# Entry point
# ===================================================================

if __name__ == "__main__":
    app()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _generate_template_input(template: str) -> str:
    """Generate a minimal input_in.txt from a template name."""
    from pyecho.config import ECHO2DParams

    try:
        params = ECHO2DParams.from_template(template)
    except ValueError:
        params = ECHO2DParams.from_template("round_collimator")

    return params.to_input_file()


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
    num_periods: float = 10,
) -> None:
    """Write a recta corrugated dechirper geometry file to *out_path*.

    The structure alternates between narrow-gap and wide-gap sections:
    - Narrow gap (corrugation):  half_gap = corr_gap
    - Wide gap (cavity):         half_gap = gap + depth

    Each period = 2 segments (narrow + wide), each of length period/2.
    """
    p2 = period / 2.0  # half-period
    a_narrow = corr_gap
    a_wide = gap + depth
    L_total = num_periods * period

    lines = [
        f"% Corrugated dechirper geometry (recta)",
        f"% a_gap={gap} mm  h={depth} mm  g={corr_gap} mm  "
        f"p={period} mm  N={num_periods}",
        f"% Number of materials",
        f"1",
        f"% Number of elements in metal with conductive walls, "
        f"permeability, permitivity, conductivity",
        f"0\t{a_wide}\t{L_total}\t{a_wide}\t0\t0\t0\t0\t0\t0",
        f"% Number of elements in material 1, permitivity, "
        f"permeability, conductivity",
        f"{2 * num_periods} 1 1 0",
    ]

    z = 0.0
    for i in range(num_periods):
        # Narrow gap (corrugation tooth)
        z_next = z + p2
        lines.append(
            f"{z}\t{a_wide}\t{z}\t{a_narrow}\t0\t0\t0\t0\t1\t0"
        )
        lines.append(
            f"{z}\t{a_narrow}\t{z_next}\t{a_narrow}\t0\t0\t0\t0\t1\t0"
        )
        lines.append(
            f"{z_next}\t{a_narrow}\t{z_next}\t{a_wide}\t0\t0\t0\t0\t1\t0"
        )
        z = z_next

        # Wide gap (cavity)
        z_next = z + p2
        lines.append(
            f"{z}\t{a_wide}\t{z_next}\t{a_wide}\t0\t0\t0\t0\t1\t0"
        )
        z = z_next

    out_path.write_text("\n".join(lines), encoding="utf-8")


def _generate_dlw_geometry(
    target: Path,
    half_gap: float = 5.0,
    thickness: float = 2.0,
    length: float = 80.0,
    epsilon_r: float = 5.6,
) -> str:
    """Generate a recta DLW geometry file.

    Creates a dielectric-lined waveguide geometry with the specified
    parameters.  Units should match the template's Units field (mm).
    """
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
    filename = "dlw.txt"
    (target / filename).write_text(content, encoding="utf-8")
    return filename


def _resolve_plot_data_dir(output_dir: str) -> Path:
    """Find the data directory (magn/ or elec/) for bunch loading.

    If output_dir itself is magn/ or elec/, use it directly.
    Otherwise, look for magn/ or elec/ subdirectories.
    """
    p = Path(output_dir)
    if p.name in ("magn", "elec"):
        return p
    for sub in ("magn", "elec"):
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


def _generate_dlw_readme(name: str) -> str:
    """Generate a detailed README for DLW projects."""
    return f"""# {name} — Dielectric Lined Waveguide (DLW)

## 结构参数 (geometry file: dlw.txt)

| 参数 | 值 | 单位 | 说明 |
|------|-----|------|------|
| 半间隙 a | 5.0 | mm | 真空区域，对称面到介质内表面 |
| 介质厚度 d | 2.0 | mm | 介质层厚度 |
| 外边界 b | 7.0 | mm | a + d，金属壁位置 |
| 长度 L | 80.0 | mm | 结构纵向长度 |
| 介电常数 εᵣ | 5.6 | — | 介质相对介电常数 |
| 管道宽度 | 20.0 | mm | 矩形管道物理宽度 |

```
侧视图 (y-z 平面，y=0 是对称轴):
  y (mm)
  7.0 ┌───────────────┐ ← 金属外壁
      │░░░░ 介质 ░░░░░│
  5.0 ├───────────────┤ ← 介质内表面
      │   真空区域    │
  0.0 ════════════════ ← 对称面
      z=0         z=80
```

## 仿真参数

| 参数 | 值 | 单位 | 说明 |
|------|-----|------|------|
| BunchSigma | 0.1 | mm | 束团 RMS 长度 |
| Offset | 0 | 网格线 | y₀ = Offset × StepY = 0 (在轴上) |
| StepY, StepZ | 0.05 | mm | 网格步长 |
| MeshLength | 250 | 网格线 | 移动网格长度 |
| Modes | 1,3,5 | — | 计算的 Fourier 模式 |
| SymmetryCondition | magn | — | 先跑 magn，再改 elec 跑第二遍 |
| WakeIntMethod | dir | — | 直接 wake 积分法 |

### Offset 说明
- 矩形几何: y₀ = Offset × StepY (无 +0.5 偏移)
- 圆形几何: r₀ = (Offset + 0.5) × StepR
- Offset = -1: 自动取最大可能值

## 使用方法

```bash
# 1. 验证配置
echo2d config validate input_in.txt

# 2. 跑 magn 仿真
echo2d run single -d . -n 4

# 3. 改 SymmetryCondition=elec，再跑
echo2d run single -d . -n 4

# 4. 后处理 (组装 magn + elec)
echo2d postprocess wake . --plot

# 5. 导出结果
echo2d export csv elec/ -o csv_elec/
echo2d export csv magn/ -o csv_magn/
```

## 模板自定义

修改 `input_in.txt` 中的参数后直接运行。几何文件 `dlw.txt` 可手动编辑或替换为其他 DLW 几何。
"""
