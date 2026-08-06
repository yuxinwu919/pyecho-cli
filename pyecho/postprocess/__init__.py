"""Post-processing subpackage for ECHO2D simulation results.

Provides a unified interface for all post-processing tasks:
wake potential computation (round & recta geometries), field monitor
analysis, and particle phase-space processing.

Submodules
----------
wakes/round : Round (axisymmetric) geometry wake processing
wakes/flat  : Recta (rectangular) geometry wake processing
fields      : Field monitor extraction & synthesis
particles   : Particle loading, statistics & format conversion
core        : :class:`PostProcessor` — high-level dispatcher

Basic usage::

    >>> from pyecho.postprocess import PostProcessor
    >>> pp = PostProcessor("path/to/output_dir")
    >>> result = pp.process_wake_monopole()
    >>> print(result.loss_factor)
"""

from pyecho.postprocess.core import PostProcessor
from pyecho.postprocess.fields import (
    extract_field_at_point,
    process_field_monitor,
    synthesize_total_field,
    synthesize_total_field_from_loader,
)
from pyecho.postprocess.particles import (
    compute_beam_moments,
    compute_particle_statistics,
    convert_echo_to_astra,
    load_echo_particles,
    load_field_bin,
    see_field,
)
from pyecho.postprocess.wakes import (
    assemble_wcc,
    assemble_wss,
    compute_wake_long_quad,
    compute_wake_long_quad_dipole,
    compute_wake_off_axis,
    compute_wake_tm_tq_td,
    compute_wake_zy,
    process_flat_wake,
    process_wake_dipole,
    process_wake_monopole,
)

__all__ = [
    # Core
    "PostProcessor",
    # Wakes — round
    "process_wake_monopole",
    "process_wake_dipole",
    # Wakes — flat
    "assemble_wcc",
    "assemble_wss",
    "compute_wake_long_quad",
    "compute_wake_long_quad_dipole",
    "compute_wake_zy",
    "compute_wake_off_axis",
    "compute_wake_tm_tq_td",
    "process_flat_wake",
    # Fields
    "extract_field_at_point",
    "process_field_monitor",
    "synthesize_total_field",
    "synthesize_total_field_from_loader",
    # Particles
    "load_echo_particles",
    "compute_beam_moments",
    "convert_echo_to_astra",
    "compute_particle_statistics",
    "load_field_bin",
    "see_field",
]
