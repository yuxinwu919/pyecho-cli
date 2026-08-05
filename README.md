# pyecho-cli

Python CLI toolkit for the [ECHO2D](https://echo4d.de) electromagnetic wakefield solver.

Computes wake potentials and impedances of charged particle bunches in accelerator
vacuum chambers — both rotationally symmetric (round) and rectangular (recta)
geometries.

## Quick Start

```bash
pip install -e .
echo2d --help
echo2d system check          # verify installation
echo2d example list           # see built-in examples
echo2d example round-collimator  # run N1 with one command
```

## Features

- **Project management** — workspace, `.echo2d.yaml` manifests, multi-run tracking
- **Configuration** — generate / validate / show `input_in.txt` from templates
- **Simulation** — launch ECHO2D solver with progress bars, symmetry auto-handling
- **Post-processing** — wake potentials (monopole/dipole/LQ/LQD), field monitors,
  particle tracking, WakeMonitor, beam moments
- **Visualization** — 2-D / 3-D field plots, animations, wake comparisons, modal
  decomposition
- **Export** — HDF5, CSV
- **Convergence** — automated mesh-refinement study

## Command Overview

```
echo2d
├── project      init / list / info / templates / migrate
├── config       generate / validate / show
├── geometry     create (pipe/dlw/corrugated) / validate / show / info
├── run          new / start / list / info / single / converge
├── postprocess  wake / field / particles / wake-monitor / beam-moments / all
├── visualize    wake / compare / modes / field
├── export       hdf5 / csv
├── compare      runs
├── system       info / detect / check
├── example      round-collimator / flat-absorber / tesla-cavity / pohang-dechirper
└── workspace
```

## Typical Workflow

```bash
# 1. Create a project
echo2d project init my_collimator -t round_collimator
cd my_collimator

# 2. Review and edit configuration
echo2d config show runs/001_baseline/input_in.txt
# ... edit runs/001_baseline/input_in.txt ...

# 3. Run simulation
echo2d run start --threads 4

# 4. Post-process
echo2d postprocess wake runs/001_baseline

# 5. Visualize
echo2d visualize wake runs/001_baseline/processed/wake/wake_monopole.txt
```

For recta (rectangular) geometry, the solver runs twice (magn + elec symmetry),
and `postprocess wake` assembles Wcc/Wss to produce Wlong/Wquad/Wdipole.

## Field Monitors

```bash
# List available monitors
echo2d postprocess field . --list

# Extract point trace (MATLAB-compatible PointMonitor.txt)
echo2d postprocess field . -m 1 -n 2 -c Ez --extract-point "0.03,0.0015"

# Synthesize total field from modal monitors (recta geometry)
echo2d postprocess field . --synthesize -c Ez --n-modes 15 --x0 0.025 --x 0.025

# 3-D surface plot
echo2d visualize field . -m 1 -n 1 --3d

# Time-series animation
echo2d postprocess field . -m 1 -n 1 --animate field.gif --fps 10
```

## Mesh Convergence

```bash
echo2d run converge -p my_project -m "2.0 1.0 0.5" -j 4
```

Runs ECHO2D at three mesh resolutions and checks loss-factor convergence (<5%).

## Requirements

- Python ≥ 3.10
- ECHO2D solver binary (auto-detected from `ECHO2D_v3_5/Codes/`)
- Dependencies: numpy, scipy, matplotlib, pydantic, pyyaml, h5py, typer, rich

## Install for Development

```bash
pip install -e ".[dev]"
pytest
python tests/comprehensive_test/scripts/run_full_test.py --quick
```

## References

- ECHO2D solver: [https://echo4d.de](https://echo4d.de)
- ECHO Manual: `ECHO2D_v3_5/Doc/ECHO_manual.md`
- Igor Zagorodnov, "Calculation of wakefields in 2D rectangular structures",
  Phys. Rev. STAB 18, 104401 (2015)

## License

MIT — see LICENSE file.  The wrapped ECHO2D solver is copyright Igor Zagorodnov
(https://echo4d.de) with its own terms for non-commercial use.
