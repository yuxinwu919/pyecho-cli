"""Geometry creation and validation commands for the ECHO2D CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.table import Table

from pyecho.cli import geometry_app, console
from pyecho.cli._helpers import (
    _generate_corrugated_geometry,
    _serialize_geo,
    _write_dlw_geometry,
    _write_pipe_default,
    _write_pipe_from_segments,
)

# ---------------------------------------------------------------------------
# Geometry commands
# ---------------------------------------------------------------------------

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
