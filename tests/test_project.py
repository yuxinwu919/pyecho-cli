"""Tests for ``pyecho/project.py`` project & run management.

Covers:
- ``MANIFEST_FILE`` / ``RUN_META_FILE`` constants
- ``init_project`` directory scaffolding (round + recta)
- ``save_project`` / ``load_project`` and ``save_run_meta`` / ``load_run_meta``
  round-trips plus missing-file error paths
- ``scan_workspace`` project discovery
- ``find_project_root`` upward walk
- ``create_new_run`` directory generation, sequential IDs, copying
- ``list_runs`` ordering
- ``is_echo2d_project`` / ``is_legacy_project`` detection
- ``migrate_project`` (incl. dry-run and error path)

All tests use ``tmp_path`` for full filesystem isolation.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pyecho.errors import ProjectError
from pyecho.project import (
    MANIFEST_FILE,
    PROCESSED_DIR,
    RUN_META_FILE,
    RUNS_DIR,
    ProjectManifest,
    RunManifest,
    SubRunInfo,
    create_new_run,
    find_project_root,
    init_project,
    is_echo2d_project,
    is_legacy_project,
    list_runs,
    load_project,
    load_run_meta,
    migrate_project,
    save_project,
    save_run_meta,
    scan_workspace,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_project(
    tmp_path: Path,
    name: str = "proj",
    geometry_type: str = "round",
    template: str = "",
) -> Path:
    """Init a project inside *tmp_path* and return its root directory."""
    init_project(
        name,
        template=template,
        geometry_type=geometry_type,
        workspace=tmp_path,
    )
    return tmp_path / name


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


def test_manifest_file_and_run_meta_file_constants() -> None:
    """The manifest and per-run metadata filenames are stable constants."""
    assert MANIFEST_FILE == ".echo2d.yaml"
    assert RUN_META_FILE == ".run.yaml"


# ---------------------------------------------------------------------------
# init_project
# ---------------------------------------------------------------------------


def test_init_project_creates_directory_structure(tmp_path) -> None:
    """A new project gets manifest, baseline run, sub-run and processed dirs."""
    manifest = init_project("alpha", workspace=tmp_path)

    root = tmp_path / "alpha"
    assert root.is_dir()
    assert (root / MANIFEST_FILE).is_file()

    first = root / RUNS_DIR / "001_baseline"
    assert first.is_dir()
    assert (first / RUN_META_FILE).is_file()
    assert (first / "input_in.txt").is_file()
    assert (first / "round").is_dir()
    for sub in ("wake", "field", "particles"):
        assert (first / PROCESSED_DIR / sub).is_dir()

    # Manifest carries the project metadata and the baseline run
    assert manifest.name == "alpha"
    assert manifest.template == ""
    assert manifest.geometry_type == "round"
    assert manifest.latest_run is not None
    assert manifest.latest_run.id == "001"
    assert manifest.latest_run.name == "baseline"
    assert manifest.latest_run.status == "pending"


def test_init_project_recta_creates_magn_elec_subruns(tmp_path) -> None:
    """Rectangular projects scaffold magn + elec sub-runs instead of round."""
    manifest = init_project("beta", geometry_type="recta", workspace=tmp_path)

    first = tmp_path / "beta" / RUNS_DIR / "001_baseline"
    assert (first / "magn").is_dir()
    assert (first / "elec").is_dir()
    assert not (first / "round").exists()

    assert manifest.geometry_type == "recta"
    assert [sr.symmetry for sr in manifest.runs[0].sub_runs] == ["magn", "elec"]


def test_init_project_raises_when_directory_exists(tmp_path) -> None:
    """Re-initialising an existing project directory raises FileExistsError."""
    init_project("gamma", workspace=tmp_path)
    with pytest.raises(FileExistsError):
        init_project("gamma", workspace=tmp_path)


# ---------------------------------------------------------------------------
# YAML load/save round-trips
# ---------------------------------------------------------------------------


def test_save_project_load_project_roundtrip(tmp_path) -> None:
    """A saved ProjectManifest loads back with equal field values."""
    m = ProjectManifest(
        name="roundtrip",
        template="round_collimator",
        geometry_type="round",
    )
    run = RunManifest(id="001", name="baseline", status="completed")
    run.sub_runs.append(
        SubRunInfo(symmetry="magn", status="completed", duration_s=12.5)
    )
    m.runs.append(run)

    written = save_project(m, tmp_path / "rt")
    assert written == tmp_path / "rt" / MANIFEST_FILE

    loaded = load_project(tmp_path / "rt")
    assert loaded.name == "roundtrip"
    assert loaded.template == "round_collimator"
    assert loaded.geometry_type == "round"
    assert loaded.schema_version == m.schema_version
    assert len(loaded.runs) == 1
    r = loaded.runs[0]
    assert r.id == "001"
    assert r.name == "baseline"
    assert r.status == "completed"
    assert r.sub_runs[0].duration_s == pytest.approx(12.5)
    assert r.total_duration_s == pytest.approx(12.5)


def test_load_project_raises_on_missing_manifest(tmp_path) -> None:
    """Loading a non-project directory raises ProjectError mentioning the file."""
    with pytest.raises(ProjectError, match=".echo2d.yaml"):
        load_project(tmp_path / "nope")


def test_save_load_run_meta_roundtrip(tmp_path) -> None:
    """A saved RunManifest loads back with equal field values."""
    run = RunManifest(
        id="007",
        name="coarse",
        geometry_type="recta",
        status="running",
    )
    run.sub_runs.append(SubRunInfo(symmetry="magn", status="running", duration_s=3.0))

    written = save_run_meta(run, tmp_path / "runs" / "007_coarse")
    assert written == tmp_path / "runs" / "007_coarse" / RUN_META_FILE

    loaded = load_run_meta(tmp_path / "runs" / "007_coarse")
    assert loaded.id == "007"
    assert loaded.name == "coarse"
    assert loaded.geometry_type == "recta"
    assert loaded.status == "running"
    assert loaded.sub_runs[0].status == "running"
    assert loaded.dir_name == "007_coarse"


def test_load_run_meta_raises_on_missing_meta(tmp_path) -> None:
    """Loading run metadata from a directory without ``.run.yaml`` raises."""
    d = tmp_path / "empty_run"
    d.mkdir()
    with pytest.raises(ProjectError, match=".run.yaml"):
        load_run_meta(d)


# ---------------------------------------------------------------------------
# scan_workspace
# ---------------------------------------------------------------------------


def test_scan_workspace_finds_projects(tmp_path) -> None:
    """scan_workspace returns a name -> manifest map, ignoring non-projects."""
    init_project("one", workspace=tmp_path)
    init_project("two", geometry_type="recta", workspace=tmp_path)
    (tmp_path / "plain").mkdir()  # not a project — must be skipped

    projects = scan_workspace(tmp_path)

    assert set(projects) == {"one", "two"}
    assert projects["one"].geometry_type == "round"
    assert projects["two"].geometry_type == "recta"


def test_scan_workspace_returns_empty_for_missing_dir(tmp_path) -> None:
    """A non-existent workspace scans to an empty mapping."""
    assert scan_workspace(tmp_path / "does_not_exist") == {}


# ---------------------------------------------------------------------------
# find_project_root
# ---------------------------------------------------------------------------


def test_find_project_root_walks_up_from_nested(tmp_path) -> None:
    """find_project_root locates the project root from a deep subdirectory."""
    root = _make_project(tmp_path, name="nested")
    deep = root / RUNS_DIR / "001_baseline" / "round" / "some_output"
    deep.mkdir(parents=True)

    assert find_project_root(deep) == root
    # Starting at the project root itself also resolves to the same root
    assert find_project_root(root) == root


def test_find_project_root_returns_none_outside_project(tmp_path) -> None:
    """Directories outside any project yield ``None``."""
    assert find_project_root(tmp_path) is None


# ---------------------------------------------------------------------------
# create_new_run
# ---------------------------------------------------------------------------


def test_create_new_run_generates_directory(tmp_path) -> None:
    """create_new_run scaffolds a ``NNN_<name>`` run and updates the manifest."""
    root = _make_project(tmp_path, name="gen")

    run = create_new_run(root, name="fine")

    assert run.id == "002"
    assert run.name == "fine"
    new_dir = root / RUNS_DIR / "002_fine"
    assert new_dir.is_dir()
    assert (new_dir / RUN_META_FILE).is_file()
    assert (new_dir / "input_in.txt").is_file()
    assert (new_dir / "round").is_dir()

    manifest = load_project(root)
    assert len(manifest.runs) == 2
    assert manifest.latest_run is not None and manifest.latest_run.id == "002"


def test_create_new_run_assigns_sequential_ids(tmp_path) -> None:
    """Each new run gets the next zero-padded sequential ID."""
    root = _make_project(tmp_path, name="seq")

    r2 = create_new_run(root, name="fine")
    r3 = create_new_run(root, name="coarse")

    assert (r2.id, r3.id) == ("002", "003")
    assert (root / RUNS_DIR / "002_fine").is_dir()
    assert (root / RUNS_DIR / "003_coarse").is_dir()


def test_create_new_run_copies_from_specific_run(tmp_path) -> None:
    """``from_run`` copies input files from the named source run."""
    root = _make_project(tmp_path, name="cp")
    create_new_run(root, name="fine")  # -> 002_fine
    (root / RUNS_DIR / "002_fine" / "input_in.txt").write_text(
        "MAGIC-MARKER", encoding="utf-8"
    )

    run = create_new_run(root, name="copy", from_run="002")

    assert run.id == "003"
    copied = root / RUNS_DIR / "003_copy" / "input_in.txt"
    assert copied.is_file()
    assert copied.read_text(encoding="utf-8") == "MAGIC-MARKER"


def test_create_new_run_raises_without_existing_runs(tmp_path) -> None:
    """A project with no runs raises when no template/from_run is given."""
    d = tmp_path / "empty_proj"
    save_project(ProjectManifest(name="empty_proj"), d)

    with pytest.raises(ProjectError, match="No existing runs"):
        create_new_run(d, name="first")


# ---------------------------------------------------------------------------
# list_runs
# ---------------------------------------------------------------------------


def test_list_runs_sorted(tmp_path) -> None:
    """list_runs returns runs in sorted directory order."""
    root = _make_project(tmp_path, name="lr")
    create_new_run(root, name="coarse")
    create_new_run(root, name="fine")

    runs = list_runs(root)

    assert [r.id for r in runs] == ["001", "002", "003"]
    assert [r.name for r in runs] == ["baseline", "coarse", "fine"]


# ---------------------------------------------------------------------------
# Project detection
# ---------------------------------------------------------------------------


def test_is_echo2d_project_true_and_false(tmp_path) -> None:
    """A directory with a manifest is a project; others are not."""
    root = _make_project(tmp_path, name="e2")
    plain = tmp_path / "plain2"
    plain.mkdir()

    assert is_echo2d_project(root) is True
    assert is_echo2d_project(plain) is False
    assert is_echo2d_project(tmp_path / "nonexistent") is False


def test_is_legacy_project_true_and_false(tmp_path) -> None:
    """Legacy = has input_in.txt but no manifest; new-style or empty is not."""
    legacy = tmp_path / "legacy_old"
    legacy.mkdir()
    (legacy / "input_in.txt").write_text("data", encoding="utf-8")
    assert is_legacy_project(legacy) is True

    # New-style project with an extra input_in.txt is NOT legacy
    root = _make_project(tmp_path, name="modern")
    (root / "input_in.txt").write_text("x", encoding="utf-8")
    assert is_legacy_project(root) is False

    empty = tmp_path / "plain3"
    empty.mkdir()
    assert is_legacy_project(empty) is False


# ---------------------------------------------------------------------------
# migrate_project
# ---------------------------------------------------------------------------


def test_migrate_project_moves_legacy_files(tmp_path) -> None:
    """Legacy projects are wrapped into runs/001_legacy with a manifest."""
    legacy = tmp_path / "old_proj"
    legacy.mkdir()
    (legacy / "input_in.txt").write_text("INPUT", encoding="utf-8")
    (legacy / "round").mkdir()
    (legacy / "round" / "data.txt").write_text("R", encoding="utf-8")
    (legacy / "wakeL_1.txt").write_text("W", encoding="utf-8")

    manifest = migrate_project(legacy)

    assert (legacy / MANIFEST_FILE).is_file()
    assert manifest.name == "old_proj"

    run_dir = legacy / RUNS_DIR / "001_legacy"
    assert run_dir.is_dir()
    assert (run_dir / "input_in.txt").read_text(encoding="utf-8") == "INPUT"
    assert (run_dir / "round" / "data.txt").read_text(encoding="utf-8") == "R"
    assert (run_dir / "wakeL_1.txt").read_text(encoding="utf-8") == "W"
    assert (run_dir / RUN_META_FILE).is_file()

    # Output dirs were moved, not copied
    assert not (legacy / "round").exists()
    assert not (legacy / "wakeL_1.txt").exists()
    # input_in.txt is copied and kept at the root as well
    assert (legacy / "input_in.txt").is_file()

    assert manifest.runs[0].name == "legacy"
    assert manifest.runs[0].status == "completed"
    assert manifest.runs[0].geometry_type == "round"


def test_migrate_project_dry_run_does_not_modify(tmp_path) -> None:
    """dry_run previews the manifest without touching the filesystem."""
    legacy = tmp_path / "dry"
    legacy.mkdir()
    (legacy / "input_in.txt").write_text("INPUT", encoding="utf-8")
    (legacy / "round").mkdir()
    (legacy / "round" / "data.txt").write_text("R", encoding="utf-8")

    manifest = migrate_project(legacy, dry_run=True)

    assert manifest.name == "dry"
    assert manifest.runs[0].name == "legacy"
    assert not (legacy / MANIFEST_FILE).exists()
    assert not (legacy / RUNS_DIR).exists()
    assert (legacy / "round" / "data.txt").read_text(encoding="utf-8") == "R"
    assert (legacy / "input_in.txt").is_file()


def test_migrate_project_raises_on_non_legacy(tmp_path) -> None:
    """Migrating a non-legacy directory (or a new-style project) raises."""
    d = tmp_path / "not_legacy"
    d.mkdir()
    with pytest.raises(ProjectError, match="legacy"):
        migrate_project(d)

    root = _make_project(tmp_path, name="newstyle")
    with pytest.raises(ProjectError):
        migrate_project(root)
