"""Wake potential post-processing subpackage.

Submodules
----------
round : Round geometry (axisymmetric) wake processing.
    - :func:`process_wake_monopole` — PP_Wake_Monopole.m
    - :func:`process_wake_dipole`   — PP_Wake_Dipole.m
recta : Recta (rectangular) geometry wake processing.
    - :func:`assemble_wcc`          — PP_Wcc.m
    - :func:`assemble_wss`          — PP_Wss.m
    - :func:`compute_wake_long_quad` — PP_WakeLQ.m
    - :func:`compute_wake_long_quad_dipole` — PP_WakeLQD.m
    - :func:`compute_wake_zy`       — PP_WakeZY.m (2-D (y, s) map)
    - :func:`compute_wake_off_axis` — PP_WakeZY.m (single (y0, y))
    - :func:`compute_wake_tm_tq_td` — PP_WakeL_Tm_Tq_Td.m
    - :func:`process_recta_wake`      — full pipeline
"""

from pyecho.postprocess.wakes.recta import (
    assemble_wcc,
    assemble_wss,
    compute_wake_long_quad,
    compute_wake_long_quad_dipole,
    compute_wake_off_axis,
    compute_wake_tm_tq_td,
    compute_wake_zy,
    process_recta_wake,
)
from pyecho.postprocess.wakes.round import (
    process_wake_dipole,
    process_wake_monopole,
)

__all__ = [
    # Round
    "process_wake_monopole",
    "process_wake_dipole",
    # Recta
    "assemble_wcc",
    "assemble_wss",
    "compute_wake_long_quad",
    "compute_wake_long_quad_dipole",
    "compute_wake_zy",
    "compute_wake_off_axis",
    "compute_wake_tm_tq_td",
    "process_recta_wake",
]
