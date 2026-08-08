"""Integration test fixtures for ECHO2D-CLI.

These tests require the ECHO2D binary and may run simulations.
Marked with ``@pytest.mark.integration`` — skipped by default in CI.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

# Root of the repo (assumes conftest.py lives at tests/integration/conftest.py)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# ECHO2D binary auto-detection
_ECHO_BINARY = _PROJECT_ROOT / "ECHO2D_v3_5" / "Codes" / "MacOS_ARM_OpenMP" / "ECHO2D"
if not _ECHO_BINARY.is_file():
    _ECHO_BINARY = None  # Let tests decide how to handle


def echo_binary() -> str:
    """Return the path to the ECHO2D executable or raise a skip reason."""
    if _ECHO_BINARY is None:
        pytest.skip("ECHO2D binary not found")
    return str(_ECHO_BINARY)


def run_echo(work_dir: Path, timeout: int = 600) -> int:
    """Run ECHO2D in *work_dir* and return the exit code."""
    exe = echo_binary()
    proc = subprocess.run(
        [exe],
        cwd=str(work_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=timeout,
    )
    return proc.returncode


def copy_example_inputs(example_dir: Path, dest_dir: Path) -> None:
    """Copy ECHO2D input files from an example to a run directory."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    for name in os.listdir(example_dir):
        src = example_dir / name
        if src.is_file() and name not in (
            "run_Linux.sh", "run_Mac.command", "run_Windows.bat",
            "ECHO2D_GUI.exe", ".echo2d",
        ):
            shutil.copy2(src, dest_dir / name)
    # Copy InParticles / InField directories if present
    for sub in ("InParticles", "InField"):
        sub_src = example_dir / sub
        if sub_src.is_dir():
            sub_dst = dest_dir / sub
            if not sub_dst.exists():
                shutil.copytree(sub_src, sub_dst)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def echo2d_exe() -> str:
    """Session-scoped ECHO2D binary path."""
    return echo_binary()


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Repo root."""
    return _PROJECT_ROOT


@pytest.fixture(scope="session")
def examples_dir(project_root: Path) -> Path:
    """Directory containing all 16 reference examples."""
    d = project_root / "tests" / "Examples"
    if not d.is_dir():
        pytest.skip("tests/Examples/ not found")
    return d


@pytest.fixture
def run_dir(tmp_path: Path) -> Path:
    """Temporary directory for a single ECHO2D run."""
    d = tmp_path / "run"
    d.mkdir()
    return d
