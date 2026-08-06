"""Simulation execution commands for the ECHO2D CLI."""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from pyecho.cli import run_app, console
from pyecho.cli._helpers import (
    _collect_output,
    _copy_geometry_to_run,
    _find_exe_in_dir,
    _resolve_input_file,
    _run_auto_fix,
)

# ---------------------------------------------------------------------------
# Run commands
# ---------------------------------------------------------------------------

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
                            description=update.get("message", "")[:40],
                        )
                    except StopIteration as exc:
                        result = exc.value
                        break
                pbar.update(task, completed=100, description="Simulation complete")

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
