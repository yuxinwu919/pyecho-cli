"""System diagnostics commands for the ECHO2D CLI."""

from __future__ import annotations

import logging
import os
import platform as _platform
import shutil
import sys as _sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.panel import Panel
from rich.table import Table

from pyecho._version import __version__
from pyecho.cli import system_app, console
from pyecho.cli._helpers import _detect_python_env, _find_exe_in_dir

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

    # Summary: satisfied / total dependency ratio
    deps_satisfied = len(_DEPS) - len(missing_imports)
    deps_total = len(_DEPS)
    summary_color = "bold green" if not missing_imports else "bold yellow"
    console.print(
        f"[bold]Summary:[/bold] "
        f"[{summary_color}]{deps_satisfied}/{deps_total}[/{summary_color}] "
        f"dependencies satisfied"
    )

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
