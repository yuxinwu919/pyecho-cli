"""Visualization commands for the ECHO2D CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import typer

from pyecho.cli import visualize_app, console

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


@visualize_app.command("impedance")
def visualize_impedance(
    output_dir: Annotated[str, typer.Argument(help="Output directory or run ID")],
    mode: Annotated[int, typer.Option("--mode", "-m", help="Mode number")] = 0,
    output: Annotated[
        Optional[str],
        typer.Option("--output", "-o", help="Save plot to file"),
    ] = None,
    log_scale: Annotated[
        bool,
        typer.Option("--log", "-l", help="Use log scale for frequency"),
    ] = False,
) -> None:
    """Plot impedance spectrum Z(f) — Re, Im, and magnitude vs frequency.

    The longitudinal wake potential W(s) (``wakeL_XX.txt``) is Fourier
    transformed into the frequency domain with :func:`wake2impedance`,
    giving the complex impedance Z(f) in ohms.

    \\b
    Examples:
      echo2d visualize impedance . -m 0
      echo2d visualize impedance 001 -m 0 --log -o impedance.png
    """
    import numpy as np

    # Run-ID / directory resolution (e.g. "001" -> runs/001_*).
    try:
        from pyecho.project import resolve_run_dir

        resolved = resolve_run_dir(output_dir)
        if resolved is not None:
            output_dir = str(resolved)
    except Exception:
        pass

    from pyecho.parser import OutputLoader
    from pyecho.mathlib.fft import wake2impedance

    try:
        loader = OutputLoader(output_dir)
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] Cannot open output directory: {exc}")
        raise typer.Exit(1)

    # Load wake data for the requested mode; bail out gracefully if absent.
    try:
        s, W_raw, hr, offset, D, sigma = loader.load_wake(mode=mode)
    except Exception:
        available = sorted(loader.load_all_wakes().keys())
        console.print(
            f"[yellow]No wake data for mode {mode} in {output_dir}.[/yellow]"
        )
        if available:
            console.print(
                f"  Available modes: {', '.join(f'm={m}' for m in available)}\n"
                f"  Use [cyan]echo2d visualize impedance {output_dir} "
                f"-m {available[0]}[/cyan]"
            )
        else:
            console.print(
                "  No wakeL_XX.txt files found in this directory. "
                "Run a simulation first or point at the correct output directory."
            )
        return

    # Wake units: m·V/nC -> V/pC (×1e-3) -> V/C (×1e12), so that the
    # Fourier transform yields an impedance in ohms.
    w_vc = W_raw * 1e-3 * 1e12
    f, z = wake2impedance(s, w_vc)
    n = len(f)
    f_pos, z_pos = f[: n // 2 + 1], z[: n // 2 + 1]

    mag = np.abs(z_pos)
    re = z_pos.real
    im = z_pos.imag

    # Use a headless backend when saving to a file.
    if output:
        import matplotlib

        matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, (ax_mag, ax_re) = plt.subplots(
        2, 1,
        figsize=(9, 7),
        sharex=True,
        constrained_layout=True,
    )

    # Top panel: |Z(f)| (log-log with --log, linear otherwise).
    if log_scale:
        keep = mag > 0
        ax_mag.loglog(f_pos[keep], mag[keep], "b-", lw=1.5, label=r"$|Z(f)|$")
    else:
        ax_mag.plot(f_pos, mag, "b-", lw=1.5, label=r"$|Z(f)|$")
    ax_mag.set_ylabel(r"$|Z|$ [$\Omega$]")
    ax_mag.set_title(f"Impedance spectrum — mode {mode}")
    ax_mag.grid(True, which="both", alpha=0.3)
    ax_mag.legend(loc="best")

    # Bottom panel: dual y-axis — Re(Z) on the left, Im(Z) on the right.
    ax_im = ax_re.twinx()
    if log_scale:
        ax_re.semilogx(f_pos, re, "g-", lw=1.2, alpha=0.85, label=r"$\mathrm{Re}(Z)$")
        ax_im.semilogx(f_pos, im, "r--", lw=1.2, alpha=0.85, label=r"$\mathrm{Im}(Z)$")
    else:
        ax_re.plot(f_pos, re, "g-", lw=1.2, alpha=0.85, label=r"$\mathrm{Re}(Z)$")
        ax_im.plot(f_pos, im, "r--", lw=1.2, alpha=0.85, label=r"$\mathrm{Im}(Z)$")
    ax_re.set_xlabel("f [Hz]")
    ax_re.set_ylabel(r"$\mathrm{Re}(Z)$ [$\Omega$]", color="g")
    ax_im.set_ylabel(r"$\mathrm{Im}(Z)$ [$\Omega$]", color="r")
    ax_re.grid(True, which="both", alpha=0.3)
    lines_re, labels_re = ax_re.get_legend_handles_labels()
    lines_im, labels_im = ax_im.get_legend_handles_labels()
    ax_re.legend(lines_re + lines_im, labels_re + labels_im, loc="best")

    console.print(
        f"[green]Mode {mode}: f_max={f_pos[-1]:.3e} Hz, "
        f"max|Z|={mag.max():.4g} Ω[/green]"
    )

    if output:
        fig.savefig(output, dpi=150, bbox_inches="tight")
        console.print(f"[green]Plot saved to {output}[/green]")
    else:
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
