"""Wake potential post-processing subpackage.

Submodules
----------
round : Round geometry (axisymmetric) wake processing.
    - :func:`process_wake_monopole` — PP_Wake_Monopole.m
    - :func:`process_wake_dipole`   — PP_Wake_Dipole.m
flat  : Flat (rectangular) geometry wake processing.
    - :func:`assemble_wcc`          — PP_Wcc.m
    - :func:`assemble_wss`          — PP_Wss.m
    - :func:`compute_wake_long_quad` — PP_WakeLQ.m
    - :func:`compute_wake_long_quad_dipole` — PP_WakeLQD.m
    - :func:`process_flat_wake`      — full pipeline
"""

from pyecho.postprocess.wakes.round import (
    process_wake_monopole,
    process_wake_dipole,
)
from pyecho.postprocess.wakes.flat import (
    assemble_wcc,
    assemble_wss,
    compute_wake_long_quad,
    compute_wake_long_quad_dipole,
    process_flat_wake,
)

__all__ = [
    # Round
    "process_wake_monopole",
    "process_wake_dipole",
    # Flat
    "assemble_wcc",
    "assemble_wss",
    "compute_wake_long_quad",
    "compute_wake_long_quad_dipole",
    "process_flat_wake",
]
