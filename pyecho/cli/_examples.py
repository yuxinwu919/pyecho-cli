"""Example template definitions for the ECHO2D CLI.

Contains the built-in example configurations and summary-printing helper.
"""

from __future__ import annotations

from pathlib import Path

from rich.panel import Panel

# Import console from parent package - use local reference to avoid circular import
from pyecho.cli import console

# Templates directory is one level up from cli/ (i.e., pyecho/templates/)
_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

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
            "Runs both magn + elec symmetries automatically."
        ),
        "geometry": "flat_absorber.txt",
        "params": {
            "units": "cm",
            "geometry_type": "recta",
            "width": 0.07,
            "symmetry": "magn",
            "bunch_sigma": 0.004,
            "offset": 0,
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
        elif hasattr(result, "loss_long"):  # RoundWakeResult
            lines.append("")
            lines.append(
                f"  Loss_long:  [cyan]{result.loss_long:.6f} V/pC[/cyan]"
            )
            lines.append(
                f"  Peak:       [cyan]{result.peak:.4f} V/pC[/cyan]"
            )
            if result.Wdipole is not None and result.kick_dipole is not None:
                lines.append(
                    f"  Kick_dipole: [cyan]{result.kick_dipole:.4f} V/pC/m[/cyan]"
                )

    console.print(
        Panel.fit("\n".join(lines), title="Example Complete")
    )
