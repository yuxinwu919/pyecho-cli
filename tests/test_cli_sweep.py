"""Tests for the ``echo2d run sweep`` command.

Covers value-string parsing (literal list vs. arithmetic range), the
``--dry-run`` sweep generator (creates run skeletons, edits
``input_in.txt`` in place, regenerates geometry, executes nothing), and
error handling for mismatched/missing options.

All filesystem operations happen under ``tmp_path`` and the workspace is
redirected there via ``ECHO2D_WORKSPACE``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from pyecho.cli import app
from pyecho.cli.run import (
    _geometry_file_in_run,
    _parse_sweep_values,
    _set_input_param,
    _sweep_geometry_radial,
)
from pyecho.project import init_project, load_run_meta

runner = CliRunner()


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_project(tmp_path: Path, name: str = "proj") -> Path:
    """Init a round project from the round-collimator template."""
    init_project(
        name,
        template="round_collimator",
        geometry_type="round",
        workspace=tmp_path,
    )
    return tmp_path / name


def _sweep_run_dirs(tmp_path: Path) -> list[Path]:
    """All run directories except the baseline."""
    runs_dir = tmp_path / "proj" / "runs"
    return sorted(
        d
        for d in runs_dir.iterdir()
        if d.is_dir() and d.name != "001_baseline"
    )


# ---------------------------------------------------------------------------
# Value-string parsing
# ---------------------------------------------------------------------------


def test_parse_literal_list() -> None:
    """Four comma-separated values stay a literal list."""
    assert _parse_sweep_values("0.5,1.0,1.5,2.0") == ["0.5", "1.0", "1.5", "2.0"]


def test_parse_two_value_list() -> None:
    """Two comma-separated values are a literal list."""
    assert _parse_sweep_values("0.5,1.0") == ["0.5", "1.0"]


def test_parse_range_three_numeric() -> None:
    """Three numeric values are interpreted as start,stop,step."""
    assert _parse_sweep_values("0.5,2.0,0.5") == ["0.5", "1", "1.5", "2"]


def test_parse_range_small_steps() -> None:
    """Small-step ranges expand without floating-point drift."""
    assert _parse_sweep_values("0.0001,0.0005,0.0001") == [
        "0.0001",
        "0.0002",
        "0.0003",
        "0.0004",
        "0.0005",
    ]


def test_parse_non_numeric_list() -> None:
    """Non-numeric tokens are never treated as a range."""
    assert _parse_sweep_values("a,b,c") == ["a", "b", "c"]


def test_parse_whitespace_robust() -> None:
    """Surrounding whitespace is trimmed."""
    assert _parse_sweep_values(" 0.5 , 1.0 , 1.5 , 2.0 ") == [
        "0.5",
        "1.0",
        "1.5",
        "2.0",
    ]


# ---------------------------------------------------------------------------
# Parameter editing
# ---------------------------------------------------------------------------


def test_set_input_param_edits_value_and_keeps_comment(tmp_path: Path) -> None:
    """The regex edit replaces the value token but keeps the comment."""
    f = tmp_path / "input_in.txt"
    f.write_text(
        "BunchSigma=0.001\t% RMS bunch length [m]\nStepZ=0.0002\n",
        encoding="utf-8",
    )
    _set_input_param(f, "BunchSigma", "0.5")
    assert f.read_text() == (
        "BunchSigma=0.5\t% RMS bunch length [m]\nStepZ=0.0002\n"
    )


def test_set_input_param_missing_param_raises(tmp_path: Path) -> None:
    """Editing a parameter that is absent raises ValueError."""
    f = tmp_path / "input_in.txt"
    f.write_text("StepZ=0.0002\n", encoding="utf-8")
    with pytest.raises(ValueError):
        _set_input_param(f, "BunchSigma", "0.5")


def test_geometry_file_in_run_parses_input(tmp_path: Path) -> None:
    """The geometry file name is read from input_in.txt."""
    run_dir = tmp_path / "run1"
    run_dir.mkdir()
    (run_dir / "input_in.txt").write_text(
        "GeometryFile=collimator.txt\t% geometry\n",
        encoding="utf-8",
    )
    assert _geometry_file_in_run(run_dir) == run_dir / "collimator.txt"


# ---------------------------------------------------------------------------
# Geometry regeneration
# ---------------------------------------------------------------------------


def test_sweep_geometry_radial_half_gap_shift(tmp_path: Path) -> None:
    """half_gap sweep shifts the minimum radius, preserving offsets."""
    g = tmp_path / "geo.txt"
    g.write_text(
        "0\t2\t5\t2\t0\t0\t0\t0\t1\t0\n"
        "5\t2\t5\t1\t0\t0\t0\t0\t1\t0\n"
        "5\t1\t10\t1\t0\t0\t0\t0\t1\t0\n",
        encoding="utf-8",
    )
    _sweep_geometry_radial(g, "half_gap", 0.5)
    text = g.read_text()
    assert "0\t1.5\t5\t1.5" in text  # outer pipe wall follows by delta
    assert "5\t1.5\t5\t0.5" in text  # step-down edge recomputed
    assert "5\t0.5\t10\t0.5" in text  # narrow section at new half-gap


def test_sweep_geometry_radial_radius_scale(tmp_path: Path) -> None:
    """radius sweep scales all radial coordinates proportionally."""
    g = tmp_path / "geo.txt"
    g.write_text("0\t2\t5\t2\t0\t0\t0\t0\t1\t0\n", encoding="utf-8")
    _sweep_geometry_radial(g, "radius", 4.0)
    assert g.read_text() == "0\t4\t5\t4\t0\t0\t0\t0\t1\t0"


# ---------------------------------------------------------------------------
# CLI: --dry-run sweep generation
# ---------------------------------------------------------------------------


def test_sweep_dry_run_creates_runs_and_edits_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--dry-run plans runs, edits input_in.txt, and executes nothing."""
    _make_project(tmp_path)
    monkeypatch.setenv("ECHO2D_WORKSPACE", str(tmp_path))

    result = runner.invoke(
        app,
        [
            "run", "sweep",
            "-p", "BunchSigma",
            "-v", "0.5,2.0,0.5",
            "-f", "001",
            "--project", "proj",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0, result.exception

    run_dirs = _sweep_run_dirs(tmp_path)
    assert len(run_dirs) == 4  # 0.5, 1, 1.5, 2

    # Each run's input_in.txt reflects its swept value
    seen = set()
    for d in run_dirs:
        text = (d / "input_in.txt").read_text(encoding="utf-8")
        val = text.split("BunchSigma=", 1)[1].split("\t")[0].strip()
        seen.add(val)
    assert seen == {"0.5", "1", "1.5", "2"}

    # Nothing was executed — every run is still pending
    for d in run_dirs:
        assert load_run_meta(d).status == "pending"

    # Summary table rendered with the planned runs
    assert "Sweep Summary" in result.output
    assert "002_sweep_BunchSigma_0.5" in result.output


def test_sweep_dry_run_with_geometry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A geometry sweep pairs geometry values with parameter values."""
    _make_project(tmp_path)
    monkeypatch.setenv("ECHO2D_WORKSPACE", str(tmp_path))

    result = runner.invoke(
        app,
        [
            "run", "sweep",
            "-p", "BunchSigma",
            "-v", "0.5,1.0",
            "-g", "half_gap",
            "--geo-values", "0.5,1.0",
            "-f", "001",
            "--project", "proj",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0, result.exception

    run_dirs = _sweep_run_dirs(tmp_path)
    assert len(run_dirs) == 2

    # The first run's geometry file was regenerated with half_gap = 0.5
    geom = run_dirs[0] / "round_collimator.txt"
    assert geom.is_file()
    radial = []
    for line in geom.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if len(fields) == 10:
            try:
                radial += [float(fields[1]), float(fields[3])]
            except ValueError:
                pass
    assert min(radial) == 0.5
    assert max(radial) == 1.5  # outer wall preserved the 1.0 offset


# ---------------------------------------------------------------------------
# CLI: error handling
# ---------------------------------------------------------------------------


def test_sweep_geo_values_length_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--geo-values must provide one geometry value per parameter value."""
    _make_project(tmp_path)
    monkeypatch.setenv("ECHO2D_WORKSPACE", str(tmp_path))

    result = runner.invoke(
        app,
        [
            "run", "sweep",
            "-p", "BunchSigma",
            "-v", "0.5,1.0",
            "-g", "half_gap",
            "--geo-values", "0.5,1.0,1.5",
            "-f", "001",
            "--project", "proj",
            "--dry-run",
        ],
    )
    assert result.exit_code != 0
    assert "same number of values" in result.output


def test_sweep_geo_param_without_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--geo-param requires --geo-values (and vice-versa)."""
    _make_project(tmp_path)
    monkeypatch.setenv("ECHO2D_WORKSPACE", str(tmp_path))

    result = runner.invoke(
        app,
        [
            "run", "sweep",
            "-p", "BunchSigma",
            "-v", "0.5,1.0",
            "-g", "half_gap",
            "-f", "001",
            "--project", "proj",
            "--dry-run",
        ],
    )
    assert result.exit_code != 0


def test_sweep_unknown_template_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--from-run must reference an existing run."""
    _make_project(tmp_path)
    monkeypatch.setenv("ECHO2D_WORKSPACE", str(tmp_path))

    result = runner.invoke(
        app,
        [
            "run", "sweep",
            "-p", "BunchSigma",
            "-v", "0.5,1.0",
            "-f", "999",
            "--project", "proj",
            "--dry-run",
        ],
    )
    assert result.exit_code != 0
    assert "not found" in result.output


def test_sweep_requires_options(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The required sweep options must be present."""
    _make_project(tmp_path)
    monkeypatch.setenv("ECHO2D_WORKSPACE", str(tmp_path))

    result = runner.invoke(app, ["run", "sweep", "--project", "proj", "--dry-run"])
    assert result.exit_code != 0
