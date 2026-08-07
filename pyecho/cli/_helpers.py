"""Shared helper functions for the ECHO2D CLI.

Contains internal utilities used by multiple command modules:
geometry generation, file resolution, environment detection,
auto-fix dependency installation, result saving, and plotting helpers.
"""

from __future__ import annotations

import importlib
import json
import logging
import os
import platform as _platform
import re
import shutil as _shutil
import subprocess
import sys as _sys
import time
from pathlib import Path
from typing import Any

import numpy as np
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

from pyecho._version import __version__
from pyecho.cli import console
from pyecho.cli._examples import _TEMPLATES_DIR

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

    # Count projects found in the workspace (if any).
    projects_line = ""
    try:
        from pyecho.project import _get_workspace_root, scan_workspace
        ws_root = _get_workspace_root()
        n_projects = len(scan_workspace(ws_root))
        if n_projects:
            projects_line = (
                "[bold]Workspace:[/bold]\n"
                f"  [cyan]{n_projects}[/cyan] project(s) found in "
                f"[dim]{ws_root}[/dim]\n\n"
            )
    except Exception:
        projects_line = ""

    console.print(
        Panel.fit(
            "[bold cyan]⚡ ECHO2D[/bold cyan] — Accelerator Wakefield / Impedance Solver\n\n"
            "Based on ECHO2D by Igor Zagorodnov (DESY)\n"
            "Official site: [link=https://echo4d.de]https://echo4d.de[/link]\n\n"
            "[bold]Tools:[/bold]\n"
            "  [cyan]echo2d[/cyan]          Command-line toolkit (this tool)\n"
            "  [cyan]echo2d-tui[/cyan]      Terminal UI  [dim](coming soon)[/dim]\n\n"
            f"{projects_line}"
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
                _shutil.move(str(f), str(dest))
    # Log files
    for f in work_dir.glob("*.log"):
        dest = dest_dir / f.name
        if not dest.exists():
            _shutil.move(str(f), str(dest))
    # Particle tracking output (particles.out, Field_XX.bin snapshots)
    for pattern in ("particles.out", "Field_*.bin", "BeamMomentsMonitor.txt"):
        for f in work_dir.glob(pattern):
            dest = dest_dir / f.name
            if not dest.exists():
                _shutil.move(str(f), str(dest))
    # Field monitor data (if any)
    for child in work_dir.iterdir():
        if child.is_dir() and child.name.startswith("FieldMonitor"):
            dest = dest_dir / child.name
            if not dest.exists():
                _shutil.move(str(child), str(dest))



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


def _save_wake_recta(result: Any, out_dir: Path) -> None:
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
