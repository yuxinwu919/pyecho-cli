"""Tests for the ``echo2d run batch`` command.

Covers YAML config parsing/validation, base-run resolution, the
``--dry-run`` planner (creates run skeletons and edits ``input_in.txt``
in place, executes nothing), and error handling for missing or
malformed configs.

All filesystem operations happen under ``tmp_path`` and the workspace is
redirected there via ``ECHO2D_WORKSPACE``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from pyecho.cli import app
from pyecho.cli.run import _load_batch_config, _resolve_batch_base
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


def _write_config(tmp_path: Path, text: str, fname: str = "batch.yaml") -> Path:
    cfg = tmp_path / fname
    cfg.write_text(text, encoding="utf-8")
    return cfg


def _batch_run_dirs(tmp_path: Path) -> list[Path]:
    """All run directories except the baseline."""
    runs_dir = tmp_path / "proj" / "runs"
    return sorted(
        d
        for d in runs_dir.iterdir()
        if d.is_dir() and d.name != "001_baseline"
    )


_BATCH_YAML = """
base: runs/001_baseline
runs:
  - name: fine_mesh
    params:
      StepY: 0.0001
      StepZ: 0.0001
  - name: large_offset
    params:
      Offset: 50
      BunchSigma: 0.002
"""


# ---------------------------------------------------------------------------
# YAML config parsing
# ---------------------------------------------------------------------------


def test_batch_config_parses_valid_yaml(tmp_path: Path) -> None:
    """A valid config exposes base and the runs list with their params."""
    cfg = _load_batch_config(_write_config(tmp_path, _BATCH_YAML))
    assert cfg["base"] == "runs/001_baseline"
    assert [r["name"] for r in cfg["runs"]] == ["fine_mesh", "large_offset"]
    assert cfg["runs"][0]["params"] == {"StepY": 0.0001, "StepZ": 0.0001}
    assert cfg["runs"][1]["params"] == {"Offset": 50, "BunchSigma": 0.002}


def test_batch_config_missing_file(tmp_path: Path) -> None:
    """A missing config file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        _load_batch_config(tmp_path / "nope.yaml")


def test_batch_config_invalid_yaml(tmp_path: Path) -> None:
    """Malformed YAML raises ValueError with a parse message."""
    with pytest.raises(ValueError, match="Failed to parse"):
        _load_batch_config(_write_config(tmp_path, "base: [unclosed\n  runs:\n"))


def test_batch_config_missing_base(tmp_path: Path) -> None:
    """A config without 'base' raises ValueError."""
    with pytest.raises(ValueError, match="'base'"):
        _load_batch_config(
            _write_config(tmp_path, "runs:\n  - name: x\n    params: {}\n")
        )


def test_batch_config_missing_runs(tmp_path: Path) -> None:
    """A config without 'runs' raises ValueError."""
    with pytest.raises(ValueError, match="'runs'"):
        _load_batch_config(_write_config(tmp_path, "base: \"001\"\n"))


def test_batch_config_empty_runs_list(tmp_path: Path) -> None:
    """An empty 'runs' list is rejected."""
    with pytest.raises(ValueError, match="non-empty"):
        _load_batch_config(_write_config(tmp_path, "base: \"001\"\nruns: []\n"))


def test_batch_config_entry_requires_name(tmp_path: Path) -> None:
    """Each runs entry must carry a 'name'."""
    with pytest.raises(ValueError, match="'name'"):
        _load_batch_config(
            _write_config(tmp_path, "base: \"001\"\nruns:\n  - params: {StepZ: 0.1}\n")
        )


# ---------------------------------------------------------------------------
# Base run resolution
# ---------------------------------------------------------------------------


def test_batch_resolve_base_supports_id_path_and_prefix(tmp_path: Path) -> None:
    """base can be a run ID, a project-relative path, or a dir-name prefix."""
    proj = _make_project(tmp_path)
    assert _resolve_batch_base("001", proj).name == "001_baseline"
    assert _resolve_batch_base("runs/001_baseline", proj).name == "001_baseline"
    assert _resolve_batch_base("001_baseline", proj).name == "001_baseline"
    assert _resolve_batch_base("999", proj) is None


# ---------------------------------------------------------------------------
# CLI: --dry-run batch planning
# ---------------------------------------------------------------------------


def test_batch_dry_run_creates_runs_and_edits_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--dry-run plans each run, applies param overrides, executes nothing."""
    _make_project(tmp_path)
    monkeypatch.setenv("ECHO2D_WORKSPACE", str(tmp_path))
    cfg = _write_config(tmp_path, _BATCH_YAML)

    result = runner.invoke(
        app,
        ["run", "batch", str(cfg), "--project", "proj", "--dry-run"],
    )
    assert result.exit_code == 0, result.exception

    run_dirs = _batch_run_dirs(tmp_path)
    assert len(run_dirs) == 2
    assert run_dirs[0].name == "002_fine_mesh"
    assert run_dirs[1].name == "003_large_offset"

    # input_in.txt reflects each entry's overridden params
    fine = (run_dirs[0] / "input_in.txt").read_text(encoding="utf-8")
    assert "StepY=0.0001" in fine
    assert "StepZ=0.0001" in fine
    offset = (run_dirs[1] / "input_in.txt").read_text(encoding="utf-8")
    assert "Offset=50" in offset
    assert "BunchSigma=0.002" in offset

    # Nothing was executed — every run is still pending
    for d in run_dirs:
        assert load_run_meta(d).status == "pending"

    # Summary table renders the planned runs
    assert "Batch Summary" in result.output
    assert "fine_mesh" in result.output
    assert "large_offset" in result.output


# ---------------------------------------------------------------------------
# CLI: error handling
# ---------------------------------------------------------------------------


def test_batch_config_file_not_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A missing config file produces a clear error and exit code 1."""
    _make_project(tmp_path)
    monkeypatch.setenv("ECHO2D_WORKSPACE", str(tmp_path))

    result = runner.invoke(
        app,
        ["run", "batch", str(tmp_path / "missing.yaml"), "--project", "proj"],
    )
    assert result.exit_code != 0
    assert "not found" in result.output


def test_batch_base_run_not_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unknown base run produces a clear error and exit code 1."""
    _make_project(tmp_path)
    monkeypatch.setenv("ECHO2D_WORKSPACE", str(tmp_path))
    cfg = _write_config(tmp_path, "base: \"999\"\nruns:\n  - name: x\n    params: {}\n")

    result = runner.invoke(
        app,
        ["run", "batch", str(cfg), "--project", "proj", "--dry-run"],
    )
    assert result.exit_code != 0
    assert "not found" in result.output


def test_batch_invalid_yaml_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Malformed YAML config reports a parse error and exits 1."""
    _make_project(tmp_path)
    monkeypatch.setenv("ECHO2D_WORKSPACE", str(tmp_path))
    cfg = _write_config(tmp_path, "base: [unclosed\n  runs:\n")

    result = runner.invoke(
        app,
        ["run", "batch", str(cfg), "--project", "proj", "--dry-run"],
    )
    assert result.exit_code != 0
    assert "Failed to parse" in result.output


# ---------------------------------------------------------------------------
# CLI: execution path (solver stubbed out)
# ---------------------------------------------------------------------------


def test_batch_all_runs_fail_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When every run fails to execute, the command exits 1."""
    _make_project(tmp_path)
    monkeypatch.setenv("ECHO2D_WORKSPACE", str(tmp_path))
    cfg = _write_config(tmp_path, _BATCH_YAML)
    monkeypatch.setattr("pyecho.cli.run._execute_run", lambda run_dir, threads=1: False)
    monkeypatch.setattr("pyecho.cli.run._run_loss_factor", lambda run_dir: None)

    result = runner.invoke(
        app,
        ["run", "batch", str(cfg), "--project", "proj"],
    )
    assert result.exit_code == 1
    assert "All batch runs failed" in result.output
    # Both runs were created and both were marked failed
    assert len(_batch_run_dirs(tmp_path)) == 2
    assert "✗ run failed" in result.output


def test_batch_partial_failure_continues_and_warns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed run is logged as a warning; the remaining runs still execute."""
    _make_project(tmp_path)
    monkeypatch.setenv("ECHO2D_WORKSPACE", str(tmp_path))
    cfg = _write_config(tmp_path, _BATCH_YAML)

    calls: list[str] = []

    def fake_execute(run_dir, threads=1):
        calls.append(Path(run_dir).name)
        return Path(run_dir).name != "002_fine_mesh"  # first fails, second succeeds

    monkeypatch.setattr("pyecho.cli.run._execute_run", fake_execute)
    monkeypatch.setattr("pyecho.cli.run._run_loss_factor", lambda run_dir: 3.25)

    result = runner.invoke(
        app,
        ["run", "batch", str(cfg), "--project", "proj"],
    )
    assert result.exit_code == 0, result.exception
    # The failed run was reported, but the second one still ran
    assert calls == ["002_fine_mesh", "003_large_offset"]
    assert "runs failed" in result.output
    # The completed run's loss factor is rendered in the summary
    assert "3.250000" in result.output
