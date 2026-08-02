"""Preprocessing subpackage for ECHO2D simulation setup.

Provides tools for initial field generation, particle format conversion,
and charge deposition — all tasks needed to prepare input data before
running an ECHO2D simulation.

Submodules
----------
field     : Initial electromagnetic field generation (Poisson solver)
particles : ASTRA ↔ ECHO2D particle format converters, line current
            profile generation, and charge grid deposition

Basic usage::

    >>> from pyecho.preprocess.field import InitialFieldGenerator
    >>> gen = InitialFieldGenerator(pipe_radius=0.01, mesh_length=52,
    ...                             step_z=2e-4, step_y=2e-4)
    >>> field_file = gen.generate("particles.txt", mesh_position_z=0.0)

    >>> from pyecho.preprocess.particles import ASTRAConverter
    >>> ASTRAConverter.astra_to_echo("input.astra", "output.echo")
"""

from pyecho.preprocess.field import InitialFieldGenerator
from pyecho.preprocess.particles import (
    ASTRAConverter,
    create_line_current,
    particles_to_charge,
)

__all__ = [
    "InitialFieldGenerator",
    "ASTRAConverter",
    "create_line_current",
    "particles_to_charge",
]
