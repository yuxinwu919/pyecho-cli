"""Round-geometry wake post-processing.

Replicates ``MatLib4ECHO`` and the example scripts
``Examples/*/PostProcessor2D/PP_Wake_Monopole.m`` and
``PP_Wake_Dipole.m`` with **numerically identical** results.

Key MATLAB → Python equivalences
---------------------------------
* ``wakeL_00.txt`` / ``wakeL_01.txt`` → :func:`parse_wake_file`
* ``IntegrTr.m`` → :func:`pyecho.mathlib.integration.integr_tr`
* ``LossShape.m`` → :func:`pyecho.mathlib.loss.loss_shape`
* ``bunch(:,2) = Iz(:,offset+3)*1e9`` → column extraction & interpolation

Critical convention
--------------------
In round geometry, the effective transverse step is::

    dy = (offset + 0.5) * hr                       (NOT simply offset * hr!)

This +0.5 shift is essential to reproduce the MATLAB output exactly.

References
----------
* ``MatLib4ECHO/LossShape.m``
* ``MatLib4ECHO/IntegrTr.m``
* ``Examples/N1_RoundCollimatorLong/PostProcessor2D/PP_Wake_Monopole.m``
* ``Examples/N1_RoundCollimatorLong/PostProcessor2D/PP_Wake_Dipole.m``
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from pyecho.mathlib.integration import integr_tr
from pyecho.mathlib.loss import loss_shape

if TYPE_CHECKING:
    from pyecho.datamodel import WakeResult
    from pyecho.parser import OutputLoader

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Raw → V/pC conversion factor (m·V/nC → V/pC).
_RAW_TO_PC: float = 1e-3


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def process_wake_monopole(
    loader: OutputLoader,
    shift_sigma: bool = True,
) -> WakeResult:
    """Process monopole (m=0) longitudinal wake from round geometry.

    Replicates ``PP_Wake_Monopole.m`` exactly.

    Algorithm
    ---------
    1. Load ``wakeL_00.txt`` → hr, offset, D, sigma, s, W_raw
    2. Load ``Iz0.txt`` → bunch profile on radial mesh
    3. :math:`dy = (\\mathrm{offset} + 0.5) \\cdot hr`
    4. :math:`W = W_\\mathrm{raw} \\times 10^{-3}`  (m·V/nC → V/pC)
    5. Extract bunch at radial index ``offset+3``, scale ×1e9
    6. Interpolate bunch to wake *s*-grid (linear, zero fill)
    7. Compute loss factor κ and RMS spread via ``LossShape``
    8. Shift *s* so that bunch centre is at s ≈ 0

    Parameters
    ----------
    loader : OutputLoader
        An :class:`OutputLoader` pointed at the ECHO2D output directory
        (the parent of the ``round/`` subdirectory).
    shift_sigma : bool
        If ``True`` (default), shift the *s*-coordinate by
        :math:`5\\sigma - 0.5\\cdot h_s` so the bunch head is near zero.
        This matches the MATLAB convention used for plotting.

    Returns
    -------
    WakeResult
        Processed wake with attributes ``s``, ``W``, ``bunch``,
        ``loss_factor``, ``rms_spread``, ``peak``.
    """
    from pyecho.datamodel import WakeResult

    # ---- 1. Load wake file ----
    s, W_raw, hr, offset, D, sigma = loader.load_wake(mode=0)

    # ---- 2. Load bunch current profile ----
    currents = loader.load_currents()
    if currents is None:
        logger.warning("No Iz0.txt found; bunch profile will be zero.")
        bunch_on_s = np.zeros_like(s)
    else:
        s_iz, Iz_2d = currents
        # MATLAB: bunch(:,1) = Iz(:,1);  bunch(:,2) = Iz(:,offset+3)*1e9
        bunch_s_coord = s_iz  # column 1
        # MATLAB: Iz(:, offset+3)  (1-indexed, col 1 = s)
        # current_2d = data[:, 1:] strips s-column, so:
        #   data[:, offset+2] (0-indexed) = current_2d[:, offset+1]
        col_idx = int(offset) + 1
        if col_idx >= Iz_2d.shape[1]:
            logger.warning(
                "offset+1 (=%d) exceeds Iz0 columns (%d); using last column.",
                col_idx, Iz_2d.shape[1],
            )
            col_idx = Iz_2d.shape[1] - 1
        bunch_raw = Iz_2d[:, col_idx] * 1e9

        # ---- 3. Interpolate bunch to wake s-grid (linear, zero fill) ----
        bunch_on_s = np.interp(s, bunch_s_coord, bunch_raw, left=0.0, right=0.0)

    # ---- 4. Unit conversion ----
    W = W_raw * _RAW_TO_PC  # m·V/nC → V/pC

    # ---- 5. Loss factor & spread ----
    # LossShape expects (N,2) arrays: [s, value]
    loss, spread, peak = loss_shape(
        np.column_stack([s, bunch_on_s]),
        np.column_stack([s, W]),
    )

    # ---- 6. Shift s-coordinate (MATLAB convention) ----
    hs = float(s[1] - s[0])
    if shift_sigma:
        shift = 5.0 * sigma - 0.5 * hs
        s_shifted = s - shift  # keep in [m]; plot_wake_round converts to [mm]
    else:
        s_shifted = s

    ns = len(s)
    return WakeResult(
        s=s_shifted,
        W=W,
        bunch=bunch_on_s,
        loss_factor=loss,
        rms_spread=spread,
        peak=peak,
        label="monopole",
        units="V/pC",
    )


def process_wake_dipole(
    loader: OutputLoader,
) -> dict:
    """Process dipole (m=1) wake from round geometry.

    Replicates ``PP_Wake_Dipole.m`` exactly.

    Returns both longitudinal and transverse wake potentials.

    Algorithm
    ---------
    1. Load ``wakeL_01.txt`` → hr, offset, D, sigma, s, W_raw
    2. :math:`dy = (\\mathrm{offset} + 0.5) \\cdot hr`
    3. :math:`W_\\mathrm{long} = W_\\mathrm{raw} \\times 10^{-3} / dy^2`
    4. :math:`W_\\mathrm{trans} = -\\mathrm{IntegrTr}(h_s, W_\\mathrm{long})`
    5. Compute loss (longitudinal) and kick (transverse)

    Parameters
    ----------
    loader : OutputLoader
        An :class:`OutputLoader` pointed at the ECHO2D output directory.

    Returns
    -------
    dict
        Keys:
        - ``longitudinal``: :class:`WakeResult` — longitudinal wake
        - ``transverse``: :class:`WakeResult` — transverse wake
        - ``dy``: float — effective transverse step [m]
        - ``sigma``: float — bunch RMS length [m]
    """
    from pyecho.datamodel import WakeResult

    # ---- 1. Load wake file ----
    s, W_raw, hr, offset, D, sigma = loader.load_wake(mode=1)

    # ---- 2. Effective transverse step ----
    dy = (offset + 0.5) * hr

    # ---- 3. Load bunch ----
    currents = loader.load_currents()
    if currents is None:
        bunch_on_s = np.zeros_like(s)
    else:
        s_iz, Iz_2d = currents
        # MATLAB: Iz(:, offset+3)  (1-indexed, col 1 = s)
        # current_2d = data[:, 1:] strips s-column, so:
        #   data[:, offset+2] (0-indexed) = current_2d[:, offset+1]
        col_idx = int(offset) + 1
        if col_idx >= Iz_2d.shape[1]:
            logger.warning(
                "offset+1 (=%d) exceeds Iz0 columns (%d); using last column.",
                col_idx, Iz_2d.shape[1],
            )
            col_idx = Iz_2d.shape[1] - 1
        bunch_raw = Iz_2d[:, col_idx] * 1e9
        bunch_on_s = np.interp(s, s_iz, bunch_raw, left=0.0, right=0.0)

    # ---- 4. Longitudinal wake: normalize by dy² ----
    W_long = W_raw * _RAW_TO_PC / (dy * dy)  # V/pC/m² → V/pC per offset²

    # ---- 5. Transverse wake via cumulative trapezoidal integration ----
    hs = float(s[1] - s[0])
    W_trans_raw = integr_tr(hs, W_long)
    W_trans = -W_trans_raw  # negate (MATLAB convention)

    # ---- 6. Loss (longitudinal) and kick (transverse) ----
    loss, spread, _peak_long = loss_shape(
        np.column_stack([s, bunch_on_s]),
        np.column_stack([s, W_long]),
    )
    kick, rms_kick, _peak_trans = loss_shape(
        np.column_stack([s, bunch_on_s]),
        np.column_stack([s, W_trans]),
    )

    # ---- 7. Shift s ----
    shift = 5.0 * sigma - 0.5 * hs
    s_shifted = s - shift  # keep in [m]; plot_wake_round converts to [mm]

    result_long = WakeResult(
        s=s_shifted,
        W=W_long,
        bunch=bunch_on_s,
        loss_factor=loss,
        rms_spread=spread,
        peak=float(np.max(np.abs(W_long))),
        label="dipole",
        units="V/pC/m²",
    )
    result_trans = WakeResult(
        s=s_shifted,
        W=W_trans,
        bunch=bunch_on_s,
        loss_factor=kick,
        rms_spread=rms_kick,
        peak=float(np.max(np.abs(W_trans))),
        label="dipole-kick",
        units="V/pC/m",
    )

    return {
        "longitudinal": result_long,
        "transverse": result_trans,
        "dy": dy,
        "sigma": sigma,
    }
