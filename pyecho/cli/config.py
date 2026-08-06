"""Configuration generate/validate/show commands for the ECHO2D CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.panel import Panel
from rich.syntax import Syntax

from pyecho.cli import config_app, console
from pyecho.errors import ConfigError

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
    except (ValueError, ConfigError) as exc:
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


@config_app.command("generate-bunch")
def config_generate_bunch(
    output: Annotated[
        str,
        typer.Option("--output", "-o", help="Output file (e.g. bunch.txt)"),
    ] = "bunch.txt",
    btype: Annotated[
        str,
        typer.Option("--type", "-t", help="Bunch type: gaussian, flattop"),
    ] = "gaussian",
    sigma: Annotated[
        float,
        typer.Option("--sigma", "-s", help="RMS bunch length [m]"),
    ] = 0.001,
    rise: Annotated[
        float,
        typer.Option("--rise", "-r", help="Rise/fall length [m] (flattop only)"),
    ] = 0.0001,
    flat_length: Annotated[
        float,
        typer.Option("--flat-length", "-l", help="Flat region length [m] (flattop only)"),
    ] = 0.002,
    n_points: Annotated[
        int,
        typer.Option("--n-points", "-n", help="Number of grid points"),
    ] = 500,
    n_sigma: Annotated[
        float,
        typer.Option("--n-sigma", help="Total width in sigma units (gaussian only)"),
    ] = 6.0,
) -> None:
    """Generate a custom bunch profile file for ECHO2D.

    Creates an ASCII file in the format ``% s[m] charge [normalized]``
    that can be used with ``InPartFile=<file>`` in input_in.txt.

    \\b
    Examples:
      echo2d config generate-bunch -o my_bunch.txt
      echo2d config generate-bunch -t flattop --sigma 0.002 --rise 0.0002 -o flat.txt
      echo2d config generate-bunch -t gaussian -s 0.001 -n 1000 --n-sigma 8
    """
    import numpy as np
    from pyecho.preprocess.bunch import generate_gaussian, generate_flattop, save_bunch_profile

    if btype == "gaussian":
        s, rho = generate_gaussian(sigma=sigma, n_points=n_points, n_sigma=n_sigma)
    elif btype in ("flattop", "flat_top", "flat-top"):
        s, rho = generate_flattop(sigma=sigma, rise=rise, flat_length=flat_length, n_points=n_points)
    else:
        console.print(f"[red]Error: Unknown bunch type '{btype}'. Use 'gaussian' or 'flattop'.[/red]")
        raise typer.Exit(1)

    out_path = save_bunch_profile(output, s, rho)
    console.print(
        f"[green]✓ Bunch profile saved to [cyan]{out_path}[/cyan][/green]\n"
        f"  Type:       {btype}\n"
        f"  Points:     {n_points}\n"
        f"  s range:    [{s[0]:.4f}, {s[-1]:.4f}] m\n"
        f"  s step:     {s[1]-s[0]:.4e} m\n"
        f"  Peak:       {np.max(rho):.4f}\n\n"
        f"[dim]Set 'InPartFile={output}' in input_in.txt to use this profile.[/dim]"
    )


@config_app.command("validate-bunch")
def config_validate_bunch(
    filepath: Annotated[str, typer.Argument(help="Bunch profile file to validate")],
) -> None:
    """Validate an ECHO2D bunch profile file.

    Checks format, s-coordinate monotonicity, uniform step, and
    non-negative charge density.

    \\b
    Example:
      echo2d config validate-bunch bunch.txt
    """
    from pyecho.preprocess.bunch import validate_bunch_profile

    result = validate_bunch_profile(filepath)

    if result["valid"]:
        console.print(
            Panel.fit(
                f"[bold green]✓ Valid bunch profile[/bold green]\n"
                f"  Points:  [cyan]{result['n_points']}[/cyan]\n"
                f"  s range: [cyan]{result['s_range'][0]:.4f} → {result['s_range'][1]:.4f}[/cyan] m\n"
                f"  s step:  [cyan]{result['s_step']:.4e}[/cyan] m\n"
                f"  Peak:    [cyan]{result['peak']:.4f}[/cyan]",
                title="Bunch Profile Validation",
            )
        )
    else:
        console.print(f"[bold red]✗ Invalid bunch profile[/bold red]")
        for issue in result["issues"]:
            console.print(f"  [red]• {issue}[/red]")
        raise typer.Exit(1)


# ===================================================================
# run commands
# ===================================================================
# Phase 2: run new / start / list / info integrate with the project
# management framework.  run single is kept for backward compatibility
# with legacy (flat-directory) workflows.
