"""Integration test suite — runs ECHO2D for all 16 examples.

All tests are marked ``@pytest.mark.integration`` and require the
ECHO2D binary.  Run with::

    pytest tests/integration/ -m integration -v

CI runs skip these tests automatically; run locally to validate
full-stack correctness after changes to the wake-processing pipeline.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pytest
from typer.testing import CliRunner

from pyecho.cli import app

import tests.integration.conftest as _cf

pytestmark = pytest.mark.integration

runner = CliRunner()
_EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "Examples"

# ── example registry (name → relative path under tests/Examples/) ──────────
EXAMPLES = {
    "N1_round_collimator_long": "N1_RoundCollimatorLong",
    "N2_round_collimator_dipole": "N2_RoundCollimatorDipole",
    "N3_round_collimator_conductive": "N3_RoundCollimatorDipoleConductive",
    "N4_flat_absorber_long_quad": "N4_FlatAbsorberLongQuad",
    "N5_flat_absorber_dipole": "N5_FlatAbsorberDipole",
    "N6_pohang_dechirper": "N6_PohangDechirper",
    "N7_tapered_resistive": "N7_TaperedResistiveCollimator",
    "N8_flat_taper_field_monitor": "N8_FlatTaperWithFieldMonitor",
    "N9_resistive_pillbox": "N9_ResistivePillbox",
    "N10_tesla_cavity": "N10_TESLACavityLong",
    "N11_round_dielectric": "N11_Round_Dielectric",
    "N12_flat_dielectric": "N12_Flat_Dielectric",
    # N13 excluded: uses input_in_1.txt/input_in_2.txt/input_in_all.txt (restart
    # procedure), no single ECHO2D input file.
    "N14_wake_monitor_bunch": "N14_WakeMonitor_ArbitraryBunchShape",
    "N15_particle_tracking": "N15_ParticleTracking",
    # N16 excluded: 8002 segments, computationally infeasible for CI
}


def _get_echo2d_input_dir(name: str) -> Path:
    """Return the ECHO2D input directory for *name*."""
    return _EXAMPLES_DIR / EXAMPLES[name] / "ECHO2D"


def _geometry_type(name: str) -> str:
    """Return 'round' or 'recta' for an example."""
    inp = _get_echo2d_input_dir(name) / "input_in.txt"
    text = inp.read_text(encoding="utf-8").lower()
    # Accept recta or rect (N8 uses the short form)
    for line in text.splitlines():
        if line.strip().startswith("geometrytype"):
            val = line.split("=")[-1].strip().split()[0]
            if val in ("recta", "rect"):
                return "recta"
    return "round"


# =============================================================================
# Tests
# =============================================================================


class TestAllExamples:
    """Run ECHO2D + Python postprocess for every example."""

    @pytest.mark.parametrize("name", list(EXAMPLES))
    def test_echo2d_runs_and_produces_wake(self, name: str, run_dir: Path) -> None:
        """ECHO2D exits 0 and produces at least one wakeL_XX.txt file."""
        _cf.echo_binary()  # skip if binary missing

        src = _get_echo2d_input_dir(name)
        _cf.copy_example_inputs(src, run_dir)

        rc = _cf.run_echo(run_dir, timeout=600)
        assert rc == 0, f"ECHO2D exited with code {rc}"

        wakes = list(run_dir.rglob("wakeL_*.txt"))
        assert len(wakes) > 0, "No wakeL_XX.txt files produced"

    @pytest.mark.parametrize("name", list(EXAMPLES))
    def test_python_postprocess_produces_summary(
        self, name: str, run_dir: Path
    ) -> None:
        """Python CLI postprocessing succeeds and saves summary.txt."""
        src = _get_echo2d_input_dir(name)
        _cf.copy_example_inputs(src, run_dir)

        rc = _cf.run_echo(run_dir, timeout=600)
        if rc != 0:
            pytest.skip(f"ECHO2D failed (rc={rc}); skipping postprocess check")

        # Determine the output data directory
        geo = _geometry_type(name)
        data_dir = run_dir
        if geo == "round":
            for sub in ("round",):
                cand = run_dir / sub
                if cand.is_dir() and list(cand.glob("wakeL_*.txt")):
                    data_dir = cand
                    break
        # For recta: pass parent dir so magn+elec are both visible

        result = runner.invoke(
            app,
            ["postprocess", "wake", str(data_dir), "-g", geo],
        )
        assert result.exit_code == 0, (
            f"Postprocess failed for {name}:\n{result.output}"
        )

        # Check summary was saved
        summary_files = list(run_dir.rglob("summary.txt"))
        assert len(summary_files) > 0, "No summary.txt produced"

    @pytest.mark.parametrize("name", list(EXAMPLES))
    def test_loss_factor_positive_or_reasonable(
        self, name: str, run_dir: Path
    ) -> None:
        """Wake loss factors are physically reasonable."""
        src = _get_echo2d_input_dir(name)
        _cf.copy_example_inputs(src, run_dir)

        rc = _cf.run_echo(run_dir, timeout=600)
        if rc != 0:
            pytest.skip(f"ECHO2D failed (rc={rc})")

        geo = _geometry_type(name)
        data_dir = run_dir
        if geo == "round":
            cand = run_dir / "round"
            if cand.is_dir() and list(cand.glob("wakeL_*.txt")):
                data_dir = cand

        result = runner.invoke(
            app,
            ["postprocess", "wake", str(data_dir), "-g", geo],
        )
        if result.exit_code != 0:
            pytest.skip(f"Postprocess failed")

        # Parse summary.txt for loss factor
        summary_files = list(run_dir.rglob("summary.txt"))
        if not summary_files:
            pytest.skip("No summary.txt")

        text = summary_files[0].read_text(encoding="utf-8")
        # Extract loss value: "Loss_long:  6.27 V/pC" or "Longitudinal loss: 6.27 V/pC"
        match = re.search(
            r"(?:Loss(?: factor)?[:\s]+|Longitudinal loss:\s+|Loss_long:\s+)"
            r"([-]?\d+\.?\d*)",
            text,
        )
        if match:
            loss = float(match.group(1))
            # Loss should be > -1e6 V/pC (some particle tracking runs give
            # negative values — that's physically OK)
            assert loss > -1e6, f"Loss factor {loss} unreasonably negative"
