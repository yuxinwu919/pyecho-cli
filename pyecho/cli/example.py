"""Built-in example runner for the ECHO2D CLI."""

from __future__ import annotations

import logging
import os
import shutil
import time
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.panel import Panel
from rich.table import Table
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.syntax import Syntax

from pyecho.cli import app, console
from pyecho.cli._examples import (
    _EXAMPLES,
    _TEMPLATES_DIR,
    _print_example_summary,
)
from pyecho.cli._helpers import _find_exe_in_dir, _show_welcome

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
