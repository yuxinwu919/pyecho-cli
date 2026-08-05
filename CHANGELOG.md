# Changelog

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
