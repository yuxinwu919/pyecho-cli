# Changelog

## [0.3.1] — 2026-08-08

### Bug Fixes
- Flat-geometry loss/kick used bare trapezoidal integrals instead of bunch-weighted convolution (100% error vs MATLAB). Fixed by using `process_recta_wake()` loss values via `_add_bunch_and_loss_factors`.
- Round dipole-only (mode 1 without mode 0) postprocessor crashed with "wakeL_00.txt not found". Fixed by auto-detecting available modes.
- Magn-only recta runs silently returned loss/kick = 0. Partial paths now call `_add_bunch_and_loss_factors`.
- Geometry detection used overly broad prefix match (`startswith("magn")` → now requires `"magn_"` or exact `"magn"`).

### New Features
- `echo2d config diff <file1> <file2>` — side-by-side parameter comparison
- `echo2d run sweep` — parameter scanning with optional geometry sweep (7 params: radius, half_gap, width, gap, thickness, length, epsilon_r)
- `echo2d run batch` — YAML-driven batch execution
- `echo2d postprocess summary` — multi-run comparison table
- `echo2d visualize geometry` — geometry structure plot
- `echo2d config set/get` — persistent user preferences (`~/.echo2d/config.yaml`)
- `echo2d run start --with-particles` — particle tracking mode
- Dual plotting backend: `pyqtgraph` (default, interactive Qt window) + `matplotlib` (fallback)
- Tab completion for project names and run IDs

### Testing & Quality
- 755 unit tests + 42 automated integration tests (pytest `-m integration`)
- 16/16 examples validated against MATLAB reference (0.000% match for all)
- Integration test suite: `pytest tests/ -m integration` runs ECHO2D + postprocessing
- Code review: 4 issues found and fixed (silent magn-only losses, geometry detection, N13 exclusion, test data routing)
- Particle tracking documentation (`docs/粒子跟踪.md`)
- Comprehensive integration test report (`tests/integration/results/REPORT.md`)

## [0.3.0] — 2026-08-07

### Breaking Changes
- flat→recta naming unification: FlatWakeResult→RectaWakeResult, FlatGeometry→RectaGeometry, process_flat_wake→process_recta_wake, plot_flat_wake→plot_recta_wake

### Architecture
- Split monolithic cli.py (4911 lines) into 14-module pyecho/cli/ subpackage
- Redesigned exception hierarchy: 14 exception types with structured context (file paths, field names, values)

### New Features
- echo2d postprocess report: HTML simulation report with embedded plots
- echo2d postprocess impedance: FFT-based Z(f) computation with CSV export
- echo2d visualize impedance: 2-panel impedance spectrum plot
- MATLAB script equivalents: PP_WakeL_Tm_Tq_Td, PP_WakeZY, A_SeeField

### Testing & Quality
- 552 unit tests (was 54 in v0.2.0)
- 81% code coverage (was ~25%)
- 0 mypy errors (was 109)
- GitHub Actions CI pipeline (Python 3.10-3.13, ubuntu + macos)
- Pre-commit hooks (ruff lint + format)
- TDD coverage boost: fields 7%→91%, particles 37%→99%, field 12%→99%

### Physics & Validation
- Accelerator physicist code review
- Fixed dipole kick factor sign error (was reporting -k_⊥)
- Panofsky-Wenzel theorem numerical verification
- Wake reciprocity and mode orthogonality validation
- MATLAB numerical benchmark tests (N1-N16 reference data)
- cosh/sinh mode normalization verified against PRSTAB 18, 104401 (2015)

### Bug Fixes
- HDF5: silent data loss from tuple-as-dict bug in _resolve_result
- Parser: missing bounds checks on all float/int conversions
- Runner: _current_process cleanup in finally block
- Config: even-mode warning for recta geometry, mesh resolution check

### UX Improvements
- Rich Table output for postprocessing results with color-coded loss/kick factors
- Live progress bar during ECHO2D execution
- Dependency check summary ratio in system check
- Workspace project count in welcome screen

## [0.2.0] — 2026-08-06

### Added
- **Field monitor postprocessing**: `postprocess field` with listing, info, point
  extraction, synthesis, 3-D surface plots, GIF/MP4 animation
- **Field monitor visualization**: `visualize field` with 2-D/3-D/animation modes
- **PointMonitor output**: MATLAB-compatible two-column (ct, Field/Q) format
- **Round geometry Ep handling**: automatic Ep×r → Ep division
- **WakeMonitor overlay**: `postprocess wake-monitor --plot` with final wakeL
- **Particle phase-space plots**: `postprocess particles --phase-space`
- **Mesh convergence automation**: `echo2d run converge` with loss-factor tracking
- **HDF5 export** now includes field monitors
- **Comprehensive test suite**: 84 tests covering all commands + round/recta
  end-to-end simulations (quick < 20s, full with solver)

### Changed
- Unified naming: flat → recta/rectangular in all user-facing strings
- Unified output file naming: wake_monopole.txt, wake_longitudinal.txt, etc.
- Unified label/tag format: "m=0 monopole", "m=1 dipole"
- Bumped version to 0.2.0

### Fixed
- Field monitor header parser: correct k_ct/h_ct/ct0 key mapping from ECHO2D format
- time_type detection: s-type has k_z, z-type has k_s (was swapped)
- Monitor filename zero-padding: Monitor_m09_N01.txt (was Monitor_m9_N1.txt)
- Field synthesis weight formula: sin(k·(x0+D/2))·sin(k·(x+D/2)) matching MATLAB
- Ep (E_phi) component detection in parser
- Template GeometryFile references matching actual filenames
- pcolormesh data layout: gouraud shading + contour overlay for smooth rendering
- stats key mismatch: compute_particle_statistics returns sigma_x not rms_x
- len(particles) used dict keys instead of particles["Np"]
- Empty subdir pre-creation shadowing parser auto-detection in example_cmd

## [0.1.0] — 2026-08-03

### Added
- Initial release: project management, configuration, simulation, wake post-processing
- Round and recta geometry support
- Project manifest (.echo2d.yaml) and workspace system
- 4 built-in examples: round-collimator, flat-absorber, tesla-cavity, pohang-dechirper
- Wake visualization (2-D line plots, comparisons, modal decomposition)
- HDF5 and CSV export
- System diagnostics (info, detect, check)
