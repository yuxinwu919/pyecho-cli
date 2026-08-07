"""Simulation execution commands for the ECHO2D CLI."""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Annotated, Any, Optional

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


# ---------------------------------------------------------------------------
# Sweep helpers
# ---------------------------------------------------------------------------

def _parse_sweep_values(values: str) -> list[str]:
    """Parse a sweep ``--values`` string into a list of value strings.

    Two forms are supported:

    - Literal list:  ``"v1,v2,v3"`` → ``["v1", "v2", "v3"]``
    - Range:         ``"start,stop,step"`` → an arithmetic progression
      (``start``, ``start+step``, …, ``stop``), rendered with ``%.10g``.

    A three-element string whose parts are all numeric is interpreted as
    a range; anything else is treated as a literal list.
    """
    parts = [p.strip() for p in values.split(",") if p.strip()]
    if len(parts) == 3:
        try:
            start, stop, step = (float(p) for p in parts)
        except ValueError:
            return parts
        if step == 0:
            return parts
        result: list[str] = []
        v = start
        eps = abs(step) * 1e-12
        if step > 0:
            while v <= stop + eps:
                result.append(f"{v:.10g}")
                v += step
        else:
            while v >= stop - eps:
                result.append(f"{v:.10g}")
                v += step
        return result
    return parts


def _set_input_param(input_file: Path, param: str, value: str) -> None:
    """Set *param* to *value* in an ``input_in.txt`` file (regex edit).

    Only the value token up to the first tab/percent/whitespace after the
    ``=`` is replaced, so trailing comments are preserved.
    """
    text = input_file.read_text(encoding="utf-8")
    updated = re.sub(
        rf"^{re.escape(param)}\s*=\s*[^\t%s]+",
        f"{param}={value}",
        text,
        flags=re.MULTILINE,
    )
    if updated == text:
        raise ValueError(f"Parameter '{param}' not found in {input_file}")
    input_file.write_text(updated, encoding="utf-8")


def _geometry_file_in_run(run_dir: Path) -> Path:
    """Return the geometry file path referenced by *run_dir*/input_in.txt."""
    text = (run_dir / "input_in.txt").read_text(encoding="utf-8")
    m = re.search(r"^GeometryFile\s*=\s*([^\t%s]+)", text, re.MULTILINE)
    if m and m.group(1) != "-":
        return run_dir / m.group(1)
    for f in sorted(run_dir.glob("*.txt")):
        if f.name != "input_in.txt":
            return f
    raise FileNotFoundError(f"No geometry file found in {run_dir}")


def _sweep_geometry_radial(geom_file: Path, param: str, value: float) -> None:
    """Rewrite *geom_file* with a new geometry parameter.

    ECHO2D geometry files describe boundary segments as ten
    whitespace-separated fields, ``z1 r1 z2 r2 …``, where the radial
    coordinates are fields 2 and 4 and the longitudinal coordinates are
    fields 1 and 3.  Only the relevant coordinates are edited.

    The parameter name selects how the new value is applied:

    - ``radius`` — proportional resize: all radial coordinates are scaled
      so the maximum maps to *value* (e.g. a round pipe).
    - ``half_gap`` / ``width`` / ``gap`` — gap shift: all radial
      coordinates are shifted so the minimum maps to *value*, preserving
      offsets such as a DLW's dielectric thickness.
    - ``thickness`` / ``length`` / ``epsilon_r`` — dielectric-loaded
      (DLW) parameters, handled by :func:`_sweep_geometry_dlw`.
    """
    if param in ("thickness", "length", "epsilon_r"):
        _sweep_geometry_dlw(geom_file, param, value)
        return

    lines = geom_file.read_text(encoding="utf-8").splitlines()
    radial: list[tuple[int, int, float]] = []
    for li, line in enumerate(lines):
        fields = line.split()
        if len(fields) != 10:
            continue
        for ci in (1, 3):
            try:
                radial.append((li, ci, float(fields[ci])))
            except ValueError:
                pass
    if not radial:
        return

    old_min = min(v for _, _, v in radial)
    old_max = max(v for _, _, v in radial)

    if param == "radius":
        if old_max <= 0:
            return
        factor = value / old_max
    else:
        delta = value - old_min

    for li, ci, old in radial:
        new_v = old * factor if param == "radius" else old + delta
        _replace_token(lines, li, ci, new_v)

    geom_file.write_text("\n".join(lines), encoding="utf-8")


def _replace_token(lines: list[str], li: int, token: int, value: float) -> None:
    """Replace token *token* of line *li* with *value*, keeping separators.

    ``re.split(r"(\\s+)", line)`` yields fields at even indices — field
    *k* lives at ``tokens[2k]`` when the line has no leading whitespace.
    Lines with unusual leading whitespace are left untouched.
    """
    tokens = re.split(r"(\s+)", lines[li])
    if tokens and (tokens[0] == "" or tokens[0].isspace()):
        return  # unusual leading whitespace — leave this line alone
    tokens[2 * token] = f"{value:.10g}"
    lines[li] = "".join(tokens)


def _dlw_blocks(lines: list[str]) -> list[dict[str, Any]]:
    """Split an ECHO2D geometry file into per-material blocks.

    Each block describes one ``% Number of elements in material …`` group::

        {"header":    line index of the ``N eps mu sigma`` header line,
         "eps":       1,  # token index of the permittivity value
         "segments":  [line indices of the segment lines]}

    Comments and blank lines are skipped when walking the file, so the
    returned indices are into *lines* as passed in.
    """
    data_li = [
        li
        for li, ln in enumerate(lines)
        if ln.strip() and not ln.strip().startswith("%")
    ]
    if not data_li:
        return []
    n_materials = int(lines[data_li[0]].split()[0])
    blocks: list[dict[str, Any]] = []
    i = 1
    for _ in range(n_materials):
        header = data_li[i]
        n_seg = int(lines[header].split()[0])
        blocks.append({
            "header": header,
            "eps": 1,
            "segments": data_li[i + 1: i + 1 + n_seg],
        })
        i += 1 + n_seg
    return blocks


def _is_dlw_geometry(
    lines: list[str], blocks: list[dict[str, Any]] | None = None
) -> bool:
    """True if *lines* describe a dielectric-loaded waveguide (DLW).

    A DLW is recognized either by an explicit ``dielectric`` /
    ``material 1`` header comment or by the two-material structure where
    the first material is the conductive wall and the second the
    dielectric layer.
    """
    if "dielectric" in "\n".join(lines).lower():
        return True
    if blocks is None:
        blocks = _dlw_blocks(lines)
    return len(blocks) == 2


def _sweep_geometry_dlw(geom_file: Path, param: str, value: float) -> None:
    """Rewrite *geom_file* with a new dielectric-loaded (DLW) parameter.

    Supported parameters:

    - ``thickness`` — rescale the dielectric layer.  The dielectric region
      runs from ``y=a`` (the half-gap, kept fixed) to ``y=b`` where
      ``b = a + thickness``; the outer dielectric boundary *and* the
      conductive metal wall at ``y=b`` are both moved to ``a + value``.
    - ``length`` — rescale the longitudinal (z) coordinates of every
      segment so the total structure length maps to *value*.
    - ``epsilon_r`` — set the relative permittivity on the dielectric
      (material 1) header line, e.g. ``4 {epsilon_r} 1 0``.

    ``thickness`` and ``epsilon_r`` require a two-material DLW geometry;
    ``length`` applies to any ECHO2D geometry file.
    """
    lines = geom_file.read_text(encoding="utf-8").splitlines()
    blocks = _dlw_blocks(lines)

    if param == "length":
        _apply_length_sweep(lines, value)
    elif param == "epsilon_r":
        if not _is_dlw_geometry(lines, blocks):
            raise ValueError(
                "epsilon_r sweep requires a dielectric-loaded (DLW) geometry "
                "file with two materials."
            )
        _replace_token(lines, blocks[1]["header"], blocks[1]["eps"], value)
    elif param == "thickness":
        if not _is_dlw_geometry(lines, blocks):
            raise ValueError(
                "thickness sweep requires a dielectric-loaded (DLW) geometry "
                "file with two materials."
            )
        _apply_thickness_sweep(lines, blocks, value)
    else:
        raise ValueError(f"Unsupported DLW geometry parameter: {param}")

    geom_file.write_text("\n".join(lines), encoding="utf-8")


def _apply_thickness_sweep(
    lines: list[str], blocks: list[dict[str, Any]], value: float
) -> None:
    """Rescale the dielectric layer thickness, keeping the half-gap fixed.

    The first material block is the conductive metal wall; the remaining
    blocks form the dielectric layer between ``y=a`` (half-gap, fixed)
    and ``y=b`` (outer boundary).  Both the dielectric outer boundary and
    the metal wall are moved to ``a + value``.
    """
    dielectric_li = [li for blk in blocks[1:] for li in blk["segments"]]
    radial: list[tuple[int, int, float]] = []
    for li in dielectric_li:
        fields = lines[li].split()
        for ci in (1, 3):
            try:
                radial.append((li, ci, float(fields[ci])))
            except ValueError:
                pass
    if not radial:
        return
    a = min(v for _, _, v in radial)
    b = max(v for _, _, v in radial)
    span = b - a
    if span <= 0:
        return
    factor = value / span

    for li, ci, old in radial:
        _replace_token(lines, li, ci, a + (old - a) * factor)

    # The conductive metal wall at y=b follows the outer dielectric boundary.
    for blk in blocks[:1]:
        for li in blk["segments"]:
            fields = lines[li].split()
            for ci in (1, 3):
                try:
                    old = float(fields[ci])
                except ValueError:
                    continue
                _replace_token(lines, li, ci, a + (old - a) * factor)


def _apply_length_sweep(lines: list[str], value: float) -> None:
    """Rescale the longitudinal (z) coordinates of every segment.

    Column 1 and 3 (token indices 0 and 2) hold the segment start/end
    z-coordinates.  They are scaled about the minimum z so the structure
    start position is preserved while the total length maps to *value*.
    """
    z_pts: list[tuple[int, int, float]] = []
    for li, line in enumerate(lines):
        fields = line.split()
        if len(fields) != 10:
            continue
        for ci in (0, 2):
            try:
                z_pts.append((li, ci, float(fields[ci])))
            except ValueError:
                pass
    if not z_pts:
        return
    z0 = min(v for _, _, v in z_pts)
    z1 = max(v for _, _, v in z_pts)
    span = z1 - z0
    if span <= 0:
        return
    factor = value / span
    for li, ci, old in z_pts:
        _replace_token(lines, li, ci, z0 + (old - z0) * factor)


def _execute_run(run_dir: Path, threads: int = 1) -> bool:
    """Run every sub-run of *run_dir* and update its status.

    Mirrors ``echo2d run start``: for each symmetry, patch
    ``SymmetryCondition`` into ``input_in.txt``, run the solver, collect
    output files, and update the per-run manifest.  Returns ``True`` if
    every sub-run completed.
    """
    from pyecho.project import load_run_meta, update_run_status
    from pyecho.runner import ECHO2DRunner

    meta = load_run_meta(run_dir)
    input_file = run_dir / "input_in.txt"
    if not input_file.is_file():
        console.print(f"[bold red]Error:[/bold red] No input_in.txt in {run_dir}")
        return False

    original = input_file.read_text(encoding="utf-8")
    ok = True
    try:
        for sr in meta.sub_runs:
            sym = sr.symmetry
            out_subdir = run_dir / sr.output_dir.strip("/")
            out_subdir.mkdir(parents=True, exist_ok=True)

            # Patch SymmetryCondition for this sub-run
            patched = re.sub(
                r"SymmetryCondition=\w+",
                f"SymmetryCondition={sym}",
                original,
            )
            input_file.write_text(patched, encoding="utf-8")

            t0 = time.time()
            try:
                runner = ECHO2DRunner(run_dir)
                gen = runner.run_stream(params=None, np=threads)
                while True:
                    try:
                        update = next(gen)
                        pct = min(float(update.get("percent", 0)), 100)
                        console.print(
                            f"    {pct:5.1f}%  {update.get('message', '')[:40]}"
                        )
                    except StopIteration:
                        break
                _collect_output(runner.work_dir, out_subdir, sym)
                update_run_status(run_dir, sym, "completed", time.time() - t0)
                console.print(
                    f"    [green]✓ {sym} completed in {time.time()-t0:.1f}s[/green]"
                )
            except Exception as exc:
                update_run_status(run_dir, sym, "failed", time.time() - t0)
                console.print(f"    [red]✗ {sym} failed: {exc}[/red]")
                ok = False
                break
    finally:
        input_file.write_text(original, encoding="utf-8")
    return ok


@run_app.command("sweep")
def run_sweep(
    param: Annotated[
        str,
        typer.Option("--param", "-p", help="Parameter to sweep (e.g. BunchSigma, StepZ)"),
    ],
    values: Annotated[
        str,
        typer.Option("--values", "-v", help="Values: 'start,stop,step' or 'v1,v2,v3'"),
    ],
    template_run: Annotated[
        str,
        typer.Option("--from-run", "-f", help="Base run to copy config from"),
    ],
    project: Annotated[
        Optional[str],
        typer.Option("--project", "-P", help="Project name"),
    ] = None,
    geometry_param: Annotated[
        Optional[str],
        typer.Option(
            "--geo-param", "-g",
            help="Geometry parameter to sweep (radius, half_gap, width, gap, "
                 "thickness, length, epsilon_r)",
        ),
    ] = None,
    geometry_values: Annotated[
        Optional[str],
        typer.Option("--geo-values", help="Geometry values for sweep"),
    ] = None,
    threads: Annotated[
        int,
        typer.Option("--threads", "-j", help="OpenMP threads"),
    ] = 1,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show what would run without executing"),
    ] = False,
) -> None:
    """Run a parameter sweep — vary one parameter over multiple values.

    Creates a new run per value, copies the configuration from
    ``--from-run``, edits ``input_in.txt`` in place, and (optionally)
    regenerates the geometry before submitting each simulation.

    \\b
    Values syntax:
      - Literal list:  -v "0.5,1.0,1.5,2.0"
      - Range:         -v "0.0001,0.0005,0.0001"  (start, stop, step)

    \\b
    Geometry parameters (--geo-param):
      Radial (any geometry):
        radius     — proportional resize; max radius maps to the value
        half_gap   — shift so the minimum radius maps to the value
        width      — alias of half_gap
        gap        — alias of half_gap
      DLW (dielectric-loaded waveguide, 2-material geometry):
        thickness  — rescale the dielectric layer; half-gap stays fixed,
                     outer boundary and metal wall move to half_gap + value
        length     — rescale the longitudinal (z) coordinates so the total
                     structure length maps to the value
        epsilon_r  — set the relative permittivity of the dielectric layer

    \\b
    Examples:
      echo2d run sweep -p BunchSigma -v "0.5,1.0,1.5,2.0" -f 001 -j 4
      echo2d run sweep -p StepZ -v "0.0001,0.0005,0.0001" -f 001
      echo2d run sweep -p BunchSigma -v "0.5,2.0,0.5" -g half_gap --geo-values "0.0005,0.0020,0.0005" -f 001
      echo2d run sweep -p BunchSigma -v "0.5,1.0" -g thickness --geo-values "1.0,2.0" -f 001 --dry-run
      echo2d run sweep -p BunchSigma -v "0.5,1.0" -g length --geo-values "1000,2000" -f 001 --dry-run
      echo2d run sweep -p BunchSigma -v "0.5,1.0" -g epsilon_r --geo-values "11,14" -f 001 --dry-run
    """
    from pyecho.project import (
        _get_workspace_root,
        create_new_run,
        find_project_root,
    )

    # ── Resolve project ──────────────────────────────────────────────
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

    runs_dir = proj_dir / "runs"
    source_dir: Path | None = None
    for child in runs_dir.iterdir():
        if child.is_dir() and child.name.startswith(template_run):
            source_dir = child
            break
    if source_dir is None:
        console.print(
            f"[bold red]Error:[/bold red] Run '{template_run}' not found in {proj_dir}."
        )
        raise typer.Exit(1)

    # ── Parse sweep values ───────────────────────────────────────────
    main_values = _parse_sweep_values(values)
    if not main_values:
        console.print(
            "[bold red]Error:[/bold red] No sweep values parsed from --values."
        )
        raise typer.Exit(1)

    geo_values: list[str] | None = None
    if bool(geometry_param) != bool(geometry_values):
        console.print(
            "[bold red]Error:[/bold red] Use --geo-param and --geo-values together."
        )
        raise typer.Exit(1)
    if geometry_param and geometry_values:
        geo_values = _parse_sweep_values(geometry_values)
        if len(geo_values) != len(main_values):
            console.print(
                "[bold red]Error:[/bold red] --geo-values must provide the same "
                f"number of values as --values ({len(main_values)})."
            )
            raise typer.Exit(1)

    # ── Plan preview ─────────────────────────────────────────────────
    geo_line = ""
    if geo_values and geometry_param:
        geo_line = f"  Geometry:  [cyan]{geometry_param}[/cyan] → {', '.join(geo_values)}\n"
    mode_line = "  Mode:      [yellow]dry-run (planned only)[/yellow]" if dry_run else ""
    console.print(
        Panel.fit(
            f"[bold]Parameter sweep[/bold]\n"
            f"  Project:   [cyan]{proj_dir.name}[/cyan]\n"
            f"  Param:     [cyan]{param}[/cyan] → {', '.join(main_values)}\n"
            f"{geo_line}"
            f"  From run:  [cyan]{source_dir.name}[/cyan]\n"
            f"  Threads:   {threads}\n"
            f"{mode_line}",
            title="Sweep",
        )
    )

    # ── Build and (optionally) run each point ────────────────────────
    created: list[dict[str, str]] = []
    any_failed = False
    for i, val in enumerate(main_values):
        run = create_new_run(
            proj_dir,
            name=f"sweep_{param}_{val}",
            from_run=template_run,
        )
        run_dir = proj_dir / "runs" / run.dir_name
        input_file = run_dir / "input_in.txt"
        if not input_file.is_file():
            console.print(f"[bold red]Error:[/bold red] No input_in.txt in {run_dir}")
            any_failed = True
            break

        # 1. Update the swept parameter in input_in.txt (regex edit)
        try:
            _set_input_param(input_file, param, val)
        except ValueError as exc:
            console.print(f"[bold red]Error:[/bold red] {exc}")
            any_failed = True
            break

        # 2. Regenerate geometry for this value (in place)
        geo_val = ""
        if geo_values is not None and geometry_param:
            try:
                geom_file = _geometry_file_in_run(run_dir)
                _sweep_geometry_radial(geom_file, geometry_param, float(geo_values[i]))
                geo_val = geo_values[i]
            except Exception as exc:
                console.print(
                    f"[bold red]Error:[/bold red] Geometry sweep failed "
                    f"for {run.dir_name}: {exc}"
                )
                any_failed = True
                break

        if dry_run:
            console.print(
                f"  [dim]• planned[/dim] [cyan]{run.dir_name}[/cyan]  "
                f"{param}={val}"
                + (f"  {geometry_param}={geo_val}" if geo_val else "")
            )
            created.append(
                {"run": run.dir_name, "value": val, "geo": geo_val, "status": "planned"}
            )
        else:
            console.print(
                f"\n  [bold]• {run.dir_name}[/bold]  {param}={val}"
                + (f"  {geometry_param}={geo_val}" if geo_val else "")
            )
            ok = _execute_run(run_dir, threads)
            created.append(
                {
                    "run": run.dir_name,
                    "value": val,
                    "geo": geo_val,
                    "status": "completed" if ok else "failed",
                }
            )
            if not ok:
                any_failed = True

    # ── Summary table ────────────────────────────────────────────────
    table = Table(title="Sweep Summary")
    table.add_column("Run", style="cyan")
    table.add_column(param, style="yellow")
    if geometry_param:
        table.add_column(geometry_param, style="yellow")
    table.add_column("Status")
    for c in created:
        icon = {
            "completed": "[green]✓[/green]",
            "failed": "[red]✗[/red]",
            "planned": "[dim]○[/dim]",
        }.get(c["status"], c["status"])
        row = [c["run"], c["value"]]
        if geometry_param:
            row.append(c["geo"] or "—")
        row.append(icon)
        table.add_row(*row)
    console.print(table)

    if any_failed:
        raise typer.Exit(1)


# ===================================================================
# postprocess commands
# ===================================================================
