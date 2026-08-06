# CLAUDE.md

ECHO2D-CLI (pyecho-cli) development guide for Claude.

## Project Identity

- **Package**: `pyecho` (PyPI: `pyecho-cli`)
- **CLI Entry**: `echo2d` → `pyecho.cli:app`
- **Version**: 0.2.0 (Beta)
- **Python**: ≥ 3.10
- **Purpose**: Python CLI toolkit wrapping the ECHO2D electromagnetic wakefield solver

## Architecture

```
pyecho/
├── cli/                    # CLI layer (Typer + Rich)
│   ├── __init__.py          # App definition, sub-app registration
│   ├── _helpers.py          # Shared helper functions (~860 lines)
│   ├── _examples.py         # Example template definitions
│   ├── main_callback.py     # Root callback + welcome screen
│   ├── project.py           # project_app commands
│   ├── geometry.py          # geometry_app commands
│   ├── config.py            # config_app commands
│   ├── run.py               # run_app commands
│   ├── postprocess.py       # postprocess_app commands
│   ├── visualize.py         # visualize_app commands
│   ├── export.py            # export_app commands
│   ├── compare.py           # compare_app commands
│   ├── system.py            # system_app commands
│   ├── example.py           # Built-in example runner
│   └── workspace.py         # Workspace viewer
├── config.py               # ECHO2DParams (Pydantic v2 model)
├── datamodel.py            # Data classes (ModeResult, SimulationResult, etc.)
├── runner.py               # ECHO2DRunner, BatchRunner
├── parser.py               # OutputLoader (parses ECHO2D output files)
├── project.py              # Project management (workspace, manifests)
├── geometry.py             # Geometry description models
├── converge.py             # Mesh convergence automation
├── visualize.py            # Plotting functions (matplotlib)
├── errors.py               # Exception hierarchy
├── api.py                  # High-level API (quick_simulate, etc.)
├── io/
│   └── hdf5.py             # HDF5 export
├── mathlib/                # Numerical utilities
│   ├── convolution.py
│   ├── fft.py
│   ├── gauss.py
│   ├── integration.py
│   └── loss.py
├── postprocess/
│   ├── core.py             # PostProcessor orchestrator
│   ├── fields.py           # Field monitor post-processing
│   ├── particles.py        # Particle tracking analysis
│   └── wakes/
│       ├── round.py        # Round geometry wake processing
│       └── flat.py         # Rectangular geometry wake processing
├── preprocess/
│   ├── bunch.py            # Bunch profile generation
│   ├── field.py            # Initial field generation
│   └── particles.py        # Particle distribution processing
└── templates/              # Built-in geometry templates
```

## Key Patterns

### CLI Architecture
- Each Typer sub-app (`project_app`, `run_app`, etc.) is defined in `cli/__init__.py`
- Command functions register on sub-apps via decorators in their respective modules
- `__init__.py` imports all command modules at the bottom to register commands
- All command handlers must import from `pyecho.cli` for the sub-app reference

### Error Handling
- Base: `PyEchoError`
- Specialized: `ConfigError`, `GeometryError`, `RunnerError`, `ParserError`, `PostProcessError`
- Runner-specific: `ExecutableNotFoundError`, `SimulationTimeoutError`, `SimulationCrashedError`
- CLI commands catch exceptions and display user-friendly messages via Rich console

### Configuration
- `ECHO2DParams` is a Pydantic v2 model with all ECHO2D `input_in.txt` parameters
- Supports serialization via `to_input_file()` and parsing via `from_input_file()`
- Field monitors use `FieldMonitorConfig` sub-model
- Templates stored in `pyecho/templates/`

### Simulation Flow
1. `ECHO2DRunner` auto-detects platform-specific executable
2. Writes `input_in.txt` from `ECHO2DParams`
3. Copies geometry file to work directory
4. Launches ECHO2D subprocess with `OMP_NUM_THREADS`
5. Parses progress from stdout
6. Collects results via `OutputLoader`

## Development Commands

```bash
# Install editable
pip install -e ".[dev]"

# Run tests
pytest tests/

# Run comprehensive test (quick mode, <20s)
python tests/comprehensive_test/scripts/run_full_test.py --quick

# Run single command test
echo2d project init test_proj -t round_collimator
echo2d system check
```

## Upstream Dependency

The ECHO2D solver is vendored at `ECHO2D_v3_5/`:
- `Codes/` — platform-specific binaries (MacOS_ARM_OpenMP, Linux, Windows)
- `Doc/ECHO_manual.md` — solver manual (reference for parameter semantics)
- `Examples/` — upstream example input decks
- `MatLib4ECHO/` — MATLAB post-processing reference
- `PostProcessor2D/` — MATLAB post-processing scripts (reference for Python implementation)

## Constraints

- ECHO2D solver is Windows-native; macOS/Linux binaries are experimental
- MPI support not yet implemented (OpenMP only)
- Rectangular geometry requires two runs (magn + elec symmetry)
- ECHO2D solver is non-commercial use only (separate license)
- The project targets Python 3.10+ with `from __future__ import annotations`

## Code Quality Rules

1. Use `from __future__ import annotations` in all modules
2. Import `Annotated` and `Optional` from `typing` when used in function signatures
3. Prefer specific exceptions over bare `except Exception` in library code
4. CLI command handlers may use broad exception handling for user-facing errors
5. Always use `Path` objects for file system operations
6. Use Rich for all terminal output (Console, Panel, Table, etc.)
7. Pydantic v2 syntax for models (field_validator, model_validator)
