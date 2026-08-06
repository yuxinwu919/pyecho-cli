"""Post-processing commands for the ECHO2D CLI."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Annotated, Optional, Any

import numpy as np
import typer
from rich.panel import Panel
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
)
from rich.table import Table

from pyecho.cli import postprocess_app, console
from pyecho.cli._helpers import (
    _find_processed_dir,
    _plot_monitor_slice,
    _read_offset_from_dir,
    _resolve_plot_data_dir,
    _save_monitor_total,
    _save_wake_flat,
    _save_wake_round_data,
    _try_update_processed_manifest,
)

# ---------------------------------------------------------------------------
# Postprocess commands
# ---------------------------------------------------------------------------

def _fmt_factor(value: float | None, fmt: str = ".6f") -> str:
    """Format and color-code a loss/kick factor for table display.

    Green = physical (positive) value; yellow = warning (zero, negative,
    or missing).
    """
    if value is None:
        return "[yellow]—[/yellow]"
    text = format(value, fmt)
    if value > 0:
        return f"[green]{text}[/green]"
    return f"[yellow]{text}[/yellow]"


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
        summary_table = Table(title="✓ Wake processed — Round Wake Result")
        summary_table.add_column("Quantity")
        summary_table.add_column("Value", justify="right")
        summary_table.add_column("Units")
        summary_table.add_row("Loss (longitudinal)", _fmt_factor(result.loss_long), "V/pC")
        summary_table.add_row("Peak", _fmt_factor(result.peak, ".4f"), "V/pC")
        summary_table.add_row("RMS spread", _fmt_factor(result.rms_spread, ".4f"), "V/pC")
        if result.Wdipole is not None:
            kd = result.kick_dipole if result.kick_dipole is not None else 0.0
            summary_table.add_row("Kick (dipole)", _fmt_factor(kd, ".4f"), "V/pC/m")
        console.print(summary_table)
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
        summary_table = Table(title="✓ Wake processed — Rectangular Wake Result")
        summary_table.add_column("Quantity")
        summary_table.add_column("Value", justify="right")
        summary_table.add_column("Units")
        summary_table.add_row("Loss (longitudinal)", _fmt_factor(result.loss_long), "V/pC")
        summary_table.add_row("Kick (quadrupole)", _fmt_factor(result.kick_quad), "V/pC/mm")
        summary_table.add_row("Kick (dipole)", _fmt_factor(result.kick_dipole), "V/pC/mm")
        console.print(summary_table)
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
