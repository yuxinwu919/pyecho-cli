"""Project and run management for ECHO2D CLI.

Defines the data models and utilities for the project management
framework (Phase 1 & 2).  A *project* is a directory containing a
``.echo2d.yaml`` manifest and one or more *runs* (self-contained
simulation snapshots).

Project layout (new format)::

    my_project/
    ├── .echo2d.yaml          # project manifest
    └── runs/
        ├── 001_baseline/
        │   ├── .run.yaml     # run metadata
        │   ├── input_in.txt
        │   ├── geometry.txt
        │   ├── magn/  or  round/
        │   ├── elec/          # recta only
        │   ├── processed/
        │   │   ├── wake/
        │   │   ├── field/
        │   │   └── particles/
        │   └── stdout_*.log
        └── 002_fine_mesh/
            └── ...

Phase 3 (planned):  Cross-project comparison, project-level results/
directory for convergence studies and parameter sweeps.  The manifest
system already stores enough metadata to support these features.

.. note::

    For the ``compare projects`` CLI command placeholder and planned
    behaviour, see :func:`pyecho.cli.compare_projects`.
"""

from __future__ import annotations

import logging
import os
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field

from pyecho._version import __version__

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Name of the project manifest file.
MANIFEST_FILE: str = ".echo2d.yaml"

#: Name of the per-run metadata file.
RUN_META_FILE: str = ".run.yaml"

#: Default workspace root (can be overridden via ``ECHO2D_WORKSPACE`` env var).
DEFAULT_WORKSPACE: str = "~/echo2d_projects"

#: Subdirectory where simulation runs live inside a project.
RUNS_DIR: str = "runs"

#: Subdirectory for post-processed results inside a run.
PROCESSED_DIR: str = "processed"

#: Schema version for forward-compatibility.
SCHEMA_VERSION: int = 1

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _get_workspace_root() -> Path:
    """Return the workspace root directory.

    Reads ``ECHO2D_WORKSPACE`` environment variable; falls back to
    ``~/echo2d_projects``.
    """
    env = os.environ.get("ECHO2D_WORKSPACE", "")
    if env:
        return Path(env).expanduser().resolve()
    return Path(DEFAULT_WORKSPACE).expanduser().resolve()


def _next_run_id(runs_dir: Path) -> str:
    """Return the next sequential run ID as a zero-padded string (e.g. ``"003"``).

    Scans *runs_dir* for existing ``NNN_*`` directories and returns the
    next available number.
    """
    if not runs_dir.exists():
        return "001"
    existing: set[int] = set()
    for child in runs_dir.iterdir():
        if child.is_dir():
            parts = child.name.split("_", 1)
            try:
                existing.add(int(parts[0]))
            except ValueError:
                pass
    n = 1
    while n in existing:
        n += 1
    return f"{n:03d}"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class SubRunInfo(BaseModel):
    """Metadata for a single ECHO2D sub-run (magn or elec)."""

    symmetry: str = "magn"
    status: str = "pending"        # pending | running | completed | failed
    duration_s: float = 0.0
    output_dir: str = ""           # relative path within the run, e.g. "magn/"


class ProcessedSummary(BaseModel):
    """Summary of post-processed wake results."""

    loss_long_VpC: float | None = None
    kick_quad_VpCmm: float | None = None
    kick_dipole_VpCmm: float | None = None
    peak_VpC: float | None = None


class RunManifest(BaseModel):
    """Metadata for a single simulation run, stored as ``.run.yaml``."""

    id: str                                            # e.g. "001"
    name: str = ""                                     # human label, e.g. "fine_mesh"
    schema_version: int = SCHEMA_VERSION
    created: str = Field(default_factory=lambda: datetime.now().isoformat())
    geometry_type: str = "round"                       # "round" or "recta"
    status: str = "pending"                            # pending | running | completed | failed
    sub_runs: list[SubRunInfo] = Field(default_factory=list)
    processed: ProcessedSummary = Field(default_factory=ProcessedSummary)

    @property
    def dir_name(self) -> str:
        """Directory name for this run, e.g. ``"001_baseline"``."""
        if self.name:
            return f"{self.id}_{self.name}"
        return self.id

    @property
    def total_duration_s(self) -> float:
        """Sum of all sub-run durations."""
        return sum(sr.duration_s for sr in self.sub_runs)


class ProjectManifest(BaseModel):
    """Project metadata, stored as ``.echo2d.yaml`` in the project root."""

    name: str
    schema_version: int = SCHEMA_VERSION
    created: str = Field(default_factory=lambda: datetime.now().isoformat())
    pyecho_version: str = __version__
    template: str = ""
    geometry_type: str = "round"
    runs: list[RunManifest] = Field(default_factory=list)

    @property
    def latest_run(self) -> RunManifest | None:
        """The most recently created run, or ``None``."""
        return self.runs[-1] if self.runs else None


# ---------------------------------------------------------------------------
# YAML I/O
# ---------------------------------------------------------------------------

def load_project(project_dir: str | Path) -> ProjectManifest:
    """Load a project manifest from *project_dir*.

    Parameters
    ----------
    project_dir : str or Path
        Path to the project root (must contain ``.echo2d.yaml``).

    Returns
    -------
    ProjectManifest

    Raises
    ------
    FileNotFoundError
        If the manifest file does not exist.
    ValueError
        If the file is malformed.
    """
    project_dir = Path(project_dir).resolve()
    manifest_path = project_dir / MANIFEST_FILE
    if not manifest_path.is_file():
        raise FileNotFoundError(
            f"No {MANIFEST_FILE} found in {project_dir}. "
            f"Is this an ECHO2D project?"
        )
    try:
        data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        return ProjectManifest(**data)
    except yaml.YAMLError as exc:
        raise ValueError(f"Failed to parse {manifest_path}: {exc}") from exc


def save_project(manifest: ProjectManifest, project_dir: str | Path) -> Path:
    """Write *manifest* to ``.echo2d.yaml`` in *project_dir*.

    Returns the path to the written file.
    """
    project_dir = Path(project_dir).resolve()
    project_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = project_dir / MANIFEST_FILE
    # Use pydantic's model_dump for clean serialisation
    data = manifest.model_dump(mode="json", exclude_defaults=False)
    manifest_path.write_text(
        yaml.safe_dump(data, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    return manifest_path


def save_run_meta(run: RunManifest, run_dir: str | Path) -> Path:
    """Write *run* metadata to ``.run.yaml`` in *run_dir*."""
    run_dir = Path(run_dir).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    meta_path = run_dir / RUN_META_FILE
    data = run.model_dump(mode="json", exclude_defaults=False)
    meta_path.write_text(
        yaml.safe_dump(data, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    return meta_path


def load_run_meta(run_dir: str | Path) -> RunManifest:
    """Load run metadata from *run_dir*."""
    run_dir = Path(run_dir).resolve()
    meta_path = run_dir / RUN_META_FILE
    if not meta_path.is_file():
        raise FileNotFoundError(f"No {RUN_META_FILE} in {run_dir}")
    try:
        data = yaml.safe_load(meta_path.read_text(encoding="utf-8"))
        return RunManifest(**data)
    except yaml.YAMLError as exc:
        raise ValueError(f"Failed to parse {meta_path}: {exc}") from exc


# ---------------------------------------------------------------------------
# High-level operations
# ---------------------------------------------------------------------------

def init_project(
    name: str,
    template: str = "",
    geometry_type: str = "round",
    workspace: str | Path | None = None,
) -> ProjectManifest:
    """Create a new ECHO2D project with the first run ready.

    Creates the project directory (in the workspace by default) and
    populates it with:
    - ``.echo2d.yaml`` project manifest
    - ``runs/001_baseline/`` with ``.run.yaml`` and stub files

    Parameters
    ----------
    name : str
        Project name (also used as directory name).
    template : str
        Template name passed to :class:`~pyecho.config.ECHO2DParams`.
    geometry_type : str
        ``"round"`` or ``"recta"``.
    workspace : str or Path, optional
        Custom workspace root.  If ``None``, uses the default
        (``ECHO2D_WORKSPACE`` env var or ``~/echo2d_projects``).

    Returns
    -------
    ProjectManifest
        The newly created project manifest.
    """
    # Resolve project root
    if workspace is not None:
        root = Path(workspace).expanduser().resolve() / name
    else:
        root = _get_workspace_root() / name

    if root.exists():
        raise FileExistsError(f"Project directory already exists: {root}")

    # Create directory structure
    runs_dir = root / RUNS_DIR
    runs_dir.mkdir(parents=True, exist_ok=True)

    # Create first run
    run_id = "001"
    run_name = "baseline"
    first_run_dir = runs_dir / f"{run_id}_{run_name}"
    first_run_dir.mkdir(parents=True, exist_ok=True)

    # Determine sub-runs based on geometry type
    if geometry_type == "recta":
        sub_runs = [
            SubRunInfo(symmetry="magn", output_dir="magn/"),
            SubRunInfo(symmetry="elec", output_dir="elec/"),
        ]
    else:
        sub_runs = [SubRunInfo(symmetry="magn", output_dir="round/")]

    # Create run manifest
    run_manifest = RunManifest(
        id=run_id,
        name=run_name,
        geometry_type=geometry_type,
        sub_runs=sub_runs,
        status="pending",
    )
    save_run_meta(run_manifest, first_run_dir)

    # Create sub-run output directories
    for sr in sub_runs:
        (first_run_dir / sr.output_dir).mkdir(parents=True, exist_ok=True)
    # Create processed/ directory skeleton
    for sub in ("wake", "field", "particles"):
        (first_run_dir / PROCESSED_DIR / sub).mkdir(parents=True, exist_ok=True)

    # Write stub input — user replaces this before running
    _write_stub_input(first_run_dir, template, geometry_type)

    # Create project manifest
    manifest = ProjectManifest(
        name=name,
        template=template,
        geometry_type=geometry_type,
        runs=[run_manifest],
    )
    save_project(manifest, root)

    # NOTE(tui): Future TUI may offer interactive template picker and
    # visual project structure browser.  The CLI is intentionally
    # minimal — auto-create with sensible defaults.
    logger.info("Initialized project '%s' at %s", name, root)
    return manifest


def scan_workspace(workspace: str | Path | None = None) -> dict[str, ProjectManifest]:
    """Scan a workspace directory for ECHO2D projects.

    A directory is considered a project if it contains a
    ``.echo2d.yaml`` file.

    Parameters
    ----------
    workspace : str or Path, optional
        Directory to scan.  If ``None``, uses the default workspace.

    Returns
    -------
    dict[str, ProjectManifest]
        Mapping of project name → manifest for all found projects.
    """
    root = Path(workspace).expanduser().resolve() if workspace else _get_workspace_root()
    projects: dict[str, ProjectManifest] = {}

    if not root.is_dir():
        return projects

    for entry in sorted(root.iterdir()):
        if entry.is_dir() and (entry / MANIFEST_FILE).is_file():
            try:
                manifest = load_project(entry)
                projects[manifest.name] = manifest
            except Exception as exc:
                logger.warning("Skipping %s: %s", entry.name, exc)

    return projects


# ---------------------------------------------------------------------------
# Run management (Phase 2)
# ---------------------------------------------------------------------------

def find_project_root(start: str | Path = ".") -> Path | None:
    """Walk up from *start* to find the nearest ``.echo2d.yaml``.

    Returns the project root directory, or ``None`` if not inside a
    project.
    """
    current = Path(start).resolve()
    for _ in range(20):  # safety limit
        if (current / MANIFEST_FILE).is_file():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


def create_new_run(
    project_dir: str | Path,
    name: str = "",
    from_run: str | None = None,
    template: str = "",
) -> RunManifest:
    """Create a new run directory in *project_dir*.

    Copies ``input_in.txt`` and geometry files from the source run
    (the latest by default, or a specific run if *from_run* is given).

    Parameters
    ----------
    project_dir : str or Path
        Project root directory.
    name : str
        Human-readable label for the run (e.g. ``"fine_mesh"``).
    from_run : str, optional
        Run ID to copy configuration from.  If ``None``, uses the
        latest run.
    template : str
        Template name for generating a fresh input file (overrides
        *from_run* if given).

    Returns
    -------
    RunManifest
        The newly created run manifest.
    """
    project_dir = Path(project_dir).resolve()
    manifest = load_project(project_dir)
    runs_dir = project_dir / RUNS_DIR
    runs_dir.mkdir(parents=True, exist_ok=True)

    # Determine run ID
    run_id = _next_run_id(runs_dir)
    run_name = name

    # Determine source for copying
    source_dir: Path | None = None
    if template:
        # Fresh from template — use project-level geometry type
        gt = manifest.geometry_type
    elif from_run:
        # Copy from a specific run
        for child in runs_dir.iterdir():
            if child.is_dir() and child.name.startswith(from_run):
                source_dir = child
                break
        if source_dir is None:
            raise ValueError(f"Run '{from_run}' not found in {project_dir}")
        gt = _detect_geometry_type_from_run(source_dir)
    else:
        # Copy from latest run
        latest = manifest.latest_run
        if latest is None:
            raise ValueError(f"No existing runs in {project_dir}. Use --template to create the first run.")
        # Find the actual directory
        for child in runs_dir.iterdir():
            if child.is_dir() and child.name.startswith(latest.id):
                source_dir = child
                break
        gt = manifest.geometry_type if source_dir is None else _detect_geometry_type_from_run(source_dir)

    # Create run directory
    dir_name = f"{run_id}_{run_name}" if run_name else run_id
    new_run_dir = runs_dir / dir_name
    new_run_dir.mkdir(parents=True, exist_ok=True)

    # Copy input files from source or generate from template
    if template:
        _write_stub_input(new_run_dir, template, gt)
    elif source_dir is not None:
        _copy_input_files(source_dir, new_run_dir)

    # Determine sub-runs
    if gt == "recta":
        sub_runs = [
            SubRunInfo(symmetry="magn", output_dir="magn/"),
            SubRunInfo(symmetry="elec", output_dir="elec/"),
        ]
    else:
        sub_runs = [SubRunInfo(symmetry="magn", output_dir="round/")]

    # Create output directories
    for sr in sub_runs:
        (new_run_dir / sr.output_dir.strip("/")).mkdir(parents=True, exist_ok=True)
    for sub in ("wake", "field", "particles"):
        (new_run_dir / PROCESSED_DIR / sub).mkdir(parents=True, exist_ok=True)

    # Write run metadata
    run = RunManifest(
        id=run_id,
        name=run_name,
        geometry_type=gt,
        sub_runs=sub_runs,
        status="pending",
    )
    save_run_meta(run, new_run_dir)

    # Update project manifest
    manifest.runs.append(run)
    save_project(manifest, project_dir)

    logger.info("Created run '%s' in %s", dir_name, project_dir)
    return run


def update_run_status(
    run_dir: str | Path,
    symmetry: str,
    status: str,
    duration_s: float = 0.0,
) -> None:
    """Update the status of a sub-run in ``.run.yaml``.

    Parameters
    ----------
    run_dir : str or Path
        Path to the run directory.
    symmetry : str
        Sub-run symmetry label (``"magn"`` or ``"elec"``).
    status : str
        New status: ``"completed"``, ``"failed"``, or ``"running"``.
    duration_s : float
        Wall-clock duration of the sub-run.
    """
    run_dir = Path(run_dir).resolve()
    meta = load_run_meta(run_dir)

    for sr in meta.sub_runs:
        if sr.symmetry == symmetry:
            sr.status = status
            sr.duration_s = duration_s
            break

    # Update overall status
    all_done = all(sr.status == "completed" for sr in meta.sub_runs)
    any_failed = any(sr.status == "failed" for sr in meta.sub_runs)
    if any_failed:
        meta.status = "failed"
    elif all_done:
        meta.status = "completed"
    elif any(sr.status == "running" for sr in meta.sub_runs):
        meta.status = "running"
    else:
        meta.status = "pending"

    save_run_meta(meta, run_dir)

    # Also update project-level run entry
    project_dir = find_project_root(run_dir)
    if project_dir is not None:
        try:
            proj = load_project(project_dir)
            for r in proj.runs:
                if r.id == meta.id and r.name == meta.name:
                    r.status = meta.status
                    r.sub_runs = meta.sub_runs
                    break
            save_project(proj, project_dir)
        except Exception:
            pass  # best-effort sync, don't break on project update failure


def _copy_input_files(source_dir: Path, dest_dir: Path) -> None:
    """Copy input files (*.txt) from *source_dir* to *dest_dir*."""
    for f in source_dir.glob("*.txt"):
        dest = dest_dir / f.name
        if not dest.exists():
            shutil.copy2(str(f), str(dest))
    # Also copy input_in.txt if present (it's .txt but make sure)
    input_src = source_dir / "input_in.txt"
    if input_src.is_file():
        shutil.copy2(str(input_src), str(dest_dir / "input_in.txt"))


def _detect_geometry_type_from_run(run_dir: Path) -> str:
    """Detect geometry type from a run directory by inspecting sub-dirs."""
    if (run_dir / "round").is_dir():
        return "round"
    if (run_dir / "magn").is_dir() or (run_dir / "elec").is_dir():
        return "recta"
    # Fallback: read .run.yaml
    try:
        meta = load_run_meta(run_dir)
        return meta.geometry_type
    except Exception:
        return "round"
    """Scan a workspace directory for ECHO2D projects.

    A directory is considered a project if it contains a
    ``.echo2d.yaml`` file.

    Parameters
    ----------
    workspace : str or Path, optional
        Directory to scan.  If ``None``, uses the default workspace.

    Returns
    -------
    dict[str, ProjectManifest]
        Mapping of project name → manifest for all found projects.
    """
    root = Path(workspace).expanduser().resolve() if workspace else _get_workspace_root()
    projects: dict[str, ProjectManifest] = {}

    if not root.is_dir():
        return projects

    for entry in sorted(root.iterdir()):
        if entry.is_dir() and (entry / MANIFEST_FILE).is_file():
            try:
                manifest = load_project(entry)
                projects[manifest.name] = manifest
            except Exception as exc:
                logger.warning("Skipping %s: %s", entry.name, exc)

    return projects


def is_echo2d_project(directory: str | Path) -> bool:
    """Return ``True`` if *directory* contains a ``.echo2d.yaml`` file."""
    return (Path(directory) / MANIFEST_FILE).is_file()


def is_legacy_project(directory: str | Path) -> bool:
    """Return ``True`` if *directory* looks like a legacy ECHO2D project.

    A legacy project has ``input_in.txt`` but no ``.echo2d.yaml``.
    """
    d = Path(directory)
    return (d / "input_in.txt").is_file() and not (d / MANIFEST_FILE).is_file()


def migrate_project(
    directory: str | Path,
    dry_run: bool = False,
) -> ProjectManifest:
    """Migrate a legacy project to the new format.

    - Creates ``.echo2d.yaml``
    - Moves existing ECHO2D output into ``runs/001_legacy/``
    - Detects round vs recta from directory contents

    Parameters
    ----------
    directory : str or Path
        Path to the legacy project root.
    dry_run : bool
        If ``True``, preview changes without modifying files.

    Returns
    -------
    ProjectManifest
        The migrated project manifest.
    """
    d = Path(directory).resolve()
    if not is_legacy_project(d):
        raise ValueError(f"{d} is not a recognisable legacy project")

    # Detect geometry type from existing output dirs
    has_round = (d / "round").is_dir()
    has_magn = (d / "magn").is_dir()
    has_elec = (d / "elec").is_dir()
    if has_round:
        geometry_type = "round"
        sub_runs = [SubRunInfo(symmetry="magn", output_dir="round/")]
    elif has_magn or has_elec:
        geometry_type = "recta"
        sub_runs = []
        if has_magn:
            sub_runs.append(SubRunInfo(symmetry="magn", output_dir="magn/"))
        if has_elec:
            sub_runs.append(SubRunInfo(symmetry="elec", output_dir="elec/"))
    else:
        geometry_type = "round"  # assume round if nothing detected
        sub_runs = []

    if dry_run:
        run = RunManifest(
            id="001", name="legacy", geometry_type=geometry_type,
            sub_runs=sub_runs, status="completed",
        )
        return ProjectManifest(name=d.name, template="", geometry_type=geometry_type, runs=[run])

    # Create runs/ directory
    runs_dir = d / RUNS_DIR
    runs_dir.mkdir(parents=True, exist_ok=True)

    legacy_run_dir = runs_dir / "001_legacy"
    if legacy_run_dir.exists():
        # find next available
        n = 2
        while (runs_dir / f"00{n}_legacy").exists():
            n += 1
        legacy_run_dir = runs_dir / f"00{n}_legacy"
    legacy_run_dir.mkdir(parents=True, exist_ok=True)

    # Move ECHO2D output directories
    for sr in sub_runs:
        src = d / sr.output_dir.strip("/")
        if src.is_dir():
            dst = legacy_run_dir / sr.output_dir.strip("/")
            if not dry_run:
                shutil.move(str(src), str(dst))

    # Move wake files that are in the root
    for pattern in ("wakeL_*.txt", "Wcc_*.txt", "Wss_*.txt", "Iz0.txt"):
        for f in d.glob(pattern):
            dst = legacy_run_dir / f.name
            if not dry_run:
                shutil.move(str(f), str(dst))

    # Copy input files
    for fname in ("input_in.txt",):
        src = d / fname
        if src.is_file():
            shutil.copy2(str(src), str(legacy_run_dir / fname))

    # Create processed/ skeleton
    for sub in ("wake", "field", "particles"):
        (legacy_run_dir / PROCESSED_DIR / sub).mkdir(parents=True, exist_ok=True)

    # Write run metadata
    run = RunManifest(
        id=legacy_run_dir.name.split("_", 1)[0],
        name="legacy",
        geometry_type=geometry_type,
        sub_runs=sub_runs,
        status="completed",
    )
    save_run_meta(run, legacy_run_dir)

    # Write project manifest
    manifest = ProjectManifest(
        name=d.name,
        template="",
        geometry_type=geometry_type,
        runs=[run],
    )
    save_project(manifest, d)

    return manifest


def list_runs(project_dir: str | Path) -> list[RunManifest]:
    """List all runs in a project by scanning the ``runs/`` directory.

    Falls back to reading ``.echo2d.yaml`` if the runs directory is
    empty or missing (supports projects created before the directory
    convention was enforced).
    """
    d = Path(project_dir).resolve()
    runs: list[RunManifest] = []

    runs_dir = d / RUNS_DIR
    if runs_dir.is_dir():
        for child in sorted(runs_dir.iterdir()):
            meta = child / RUN_META_FILE
            if child.is_dir() and meta.is_file():
                try:
                    runs.append(load_run_meta(child))
                except Exception:
                    pass

    # Fallback: read from project manifest
    if not runs:
        try:
            manifest = load_project(d)
            runs = manifest.runs
        except Exception:
            pass

    return runs


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _write_stub_input(run_dir: Path, template: str, geometry_type: str) -> None:
    """Write a stub ``input_in.txt`` for a new run.

    The user is expected to edit this file before running.
    """
    from pyecho.config import ECHO2DParams

    try:
        params = ECHO2DParams.from_template(template)
    except ValueError:
        # Template not found — write a minimal stub
        geo_file = "geometry.txt"
        if geometry_type == "recta":
            params = ECHO2DParams(GeometryType="recta", Width=0.07, GeometryFile=geo_file)
        else:
            params = ECHO2DParams(GeometryType="round", GeometryFile=geo_file)
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "input_in.txt").write_text(params.to_input_file(), encoding="utf-8")
