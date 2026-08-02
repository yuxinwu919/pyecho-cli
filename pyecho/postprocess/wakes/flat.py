"""Flat (rectangular) geometry wake post-processing.

Replicates the full MATLAB pipeline for flat-geometry wake computations
used in ECHO2D examples with rectangular structures (dechirpers, etc.).

Pipeline overview
------------------
1. **PP_Wcc** / **PP_Wss** — assemble coupling matrices from individual
   ``wakeL_XX.txt`` files for odd modes (m = 1, 3, 5, …).  Each raw mode
   is normalised by cosh²(dy·k) or sinh²(dy·k) as appropriate.
2. **PP_WakeLQ** — sum over cos-cos modes to obtain the longitudinal
   (monopole) and quadrupole wake potentials.
3. **PP_WakeLQD** — same as PP_WakeLQ, but also processes sin-sin modes
   for the dipole wake.

Key MATLAB → Python equivalences
---------------------------------
* ``PP_Wcc.m`` → :func:`assemble_wcc`
* ``PP_Wss.m`` → :func:`assemble_wss`
* ``PP_WakeLQ.m`` → :func:`compute_wake_long_quad`
* ``PP_WakeLQD.m`` → :func:`compute_wake_long_quad_dipole`
* ``IntegrTr.m`` → :func:`pyecho.mathlib.integration.integr_tr`
* ``LossShape.m`` → :func:`pyecho.mathlib.loss.loss_shape`

**Critical convention (different from round geometry!)**
    In flat geometry the effective transverse step is::

        dy = offset * hr         (NO +0.5!)

    This is fundamentally different from the round-geometry convention
    ``dy = (offset + 0.5) * hr``.

Unit conversions (flat geometry)
---------------------------------
.. note::
   The variable ``D`` denotes the **total width** of the rectangular
   structure, i.e. the ``Width`` parameter in ``input_in.txt``.
   $k_x = \\pi m / D$.  This is only meaningful for ``GeometryType=recta``;
   for round geometry the radius is defined by the geometry file itself.

* Raw ``wakeL_XX.txt``: m·V/nC → V/pC via ×1e-3
* Wcc/Wss stored in V/pC·m (after cosh²/sinh² normalisation)
* Wlong: Σ Wcc × 2/D × 1e-3 → V/pC
* Wquad: −IntegrTr(Σ k²·Wcc) × 2/D × 1e-6 → V/pC/mm
* Wdipole: −IntegrTr(Σ k²·Wss) × 2/D × 1e-6 → V/pC/mm

References
----------
* ``MatLib4ECHO/IntegrTr.m``, ``MatLib4ECHO/LossShape.m``
* ``Examples/N6_PohangDechirper/PostProcessor2D/PP_Wcc.m``
* ``Examples/N6_PohangDechirper/PostProcessor2D/PP_Wss.m``
* ``Examples/N6_PohangDechirper/PostProcessor2D/PP_WakeLQ.m``
* ``Examples/N6_PohangDechirper/PostProcessor2D/PP_WakeLQD.m``
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from pyecho.mathlib.integration import integr_tr
from pyecho.mathlib.loss import loss_shape

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Raw → V/pC conversion factor.
_RAW_TO_PC: float = 1e-3


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def _load_odd_mode_wakes(
    data_dir: Path,
    n_modes: int,
) -> tuple[np.ndarray, dict]:
    """Load raw wakeL files for odd modes 1, 3, 5, ..., (2*n_modes-1).

    Parameters
    ----------
    data_dir : Path
        Directory containing ``wakeL_XX.txt`` files.
    n_modes : int
        Number of odd modes to load.

    Returns
    -------
    s : np.ndarray
        1-D longitudinal coordinate [m] (same for all modes).
    raw_wakes : dict[int, np.ndarray]
        Mapping ``{mode_number: W_raw_array}``.
    """
    raw_wakes: dict[int, np.ndarray] = {}
    s_global: np.ndarray | None = None

    for i in range(1, n_modes + 1):
        m = 2 * i - 1  # odd: 1, 3, 5, ...
        fname = data_dir / f"wakeL_{m:02d}.txt"
        if not fname.exists():
            logger.warning("wakeL_%02d.txt not found; stopping at mode %d.", m, m - 2)
            break

        data = np.loadtxt(fname)
        # First two rows are header: [hr, offset], [D, sigma]
        # D = total structure width [m] (= Width in input_in.txt, recta only)
        # Remaining rows: [s, W_raw]
        if s_global is None:
            s_global = data[2:, 0].copy()
        raw_wakes[m] = data[2:, 1].copy()

    if s_global is None:
        raise FileNotFoundError(f"No wakeL files found in {data_dir}")

    return s_global, raw_wakes


# ---------------------------------------------------------------------------
# PP_Wcc — cos-cos coupling matrix
# ---------------------------------------------------------------------------


def assemble_wcc(
    data_dir: str | Path,
    n_modes: int = 15,
) -> np.ndarray:
    """Assemble the Wcc (cos-cos) coupling matrix for flat geometry.

    Replicates ``PP_Wcc.m`` exactly.

    The matrix has shape ``(n_modes+1, ns+1)``:
        - Row 0: ``[D, s_0, s_1, ..., s_{ns-1}]``  (D = total width [m] = Width)
        - Row i (i≥1): ``[k_i, Wcc_i(s_0), ..., Wcc_i(s_{ns-1})]``

    where :math:`k_i = \\pi \\cdot m_i / D` and
    :math:`W_{\\mathrm{cc},i}(s) = W_{\\mathrm{raw},i}(s) / \\cosh^2(dy \\cdot k_i)`.

    Parameters
    ----------
    data_dir : str or Path
        Directory containing ``wakeL_XX.txt`` files (the ``magn/`` subdirectory).
    n_modes : int
        Number of odd modes (m = 1, 3, ..., 2*n_modes-1).  Default 15.

    Returns
    -------
    np.ndarray
        Wcc matrix as described above.
    """
    data_dir = Path(data_dir)

    # Load the first mode to get hr, offset, D, sigma, and s-grid
    # D = total structure width [m] (= Width in input_in.txt, recta only)
    fname_1 = data_dir / "wakeL_01.txt"
    if not fname_1.exists():
        raise FileNotFoundError(f"wakeL_01.txt not found in {data_dir}")

    data_1 = np.loadtxt(fname_1, comments="%")
    hr = data_1[0, 0]
    offset = int(data_1[0, 1])
    D = data_1[1, 0]
    sigma = data_1[1, 1]

    # FLAT geometry: dy = offset * hr  (NO +0.5!)
    dy = offset * hr

    s = data_1[2:, 0].copy()
    ns = len(s)

    # Allocate Wcc matrix: (n_modes+1) rows × (ns+1) cols
    Wcc = np.zeros((n_modes + 1, ns + 1), dtype=np.float64)
    Wcc[0, 1:] = s          # row 0, cols 1+ = s-grid
    Wcc[0, 0] = D           # row 0, col 0 = structure width

    for i in range(1, n_modes + 1):
        m = 2 * i - 1  # odd mode number
        k = np.pi / D * m
        Wcc[i, 0] = k

        fname = data_dir / f"wakeL_{m:02d}.txt"
        if not fname.exists():
            logger.warning("wakeL_%02d.txt not found; zero-filling mode %d.", m, m)
            continue

        data = np.loadtxt(fname, comments="%")
        w_raw = data[2:, 1].copy()

        # Normalize: W / cosh(dy * k)²
        denom = np.cosh(dy * k) ** 2
        Wcc[i, 1:] = w_raw / denom

    return Wcc


# ---------------------------------------------------------------------------
# PP_Wss — sin-sin coupling matrix
# ---------------------------------------------------------------------------


def assemble_wss(
    data_dir: str | Path,
    n_modes: int = 15,
) -> np.ndarray:
    """Assemble the Wss (sin-sin) coupling matrix for flat geometry.

    Replicates ``PP_Wss.m`` exactly.

    Same layout as :func:`assemble_wcc`, but normalises by
    :math:`\\sinh^2(dy \\cdot k_i)` instead of :math:`\\cosh^2`.

    Parameters
    ----------
    data_dir : str or Path
        Directory containing ``wakeL_XX.txt`` files (the ``elec/`` subdirectory).
    n_modes : int
        Number of odd modes.  Default 15.

    Returns
    -------
    np.ndarray
        Wss matrix, same format as Wcc.
    """
    data_dir = Path(data_dir)

    fname_1 = data_dir / "wakeL_01.txt"
    if not fname_1.exists():
        raise FileNotFoundError(f"wakeL_01.txt not found in {data_dir}")

    data_1 = np.loadtxt(fname_1, comments="%")
    hr = data_1[0, 0]
    offset = int(data_1[0, 1])
    D = data_1[1, 0]

    # FLAT geometry: dy = offset * hr
    dy = offset * hr

    s = data_1[2:, 0].copy()
    ns = len(s)

    Wss = np.zeros((n_modes + 1, ns + 1), dtype=np.float64)
    Wss[0, 1:] = s
    Wss[0, 0] = D

    for i in range(1, n_modes + 1):
        m = 2 * i - 1
        k = np.pi / D * m
        Wss[i, 0] = k

        fname = data_dir / f"wakeL_{m:02d}.txt"
        if not fname.exists():
            logger.warning("wakeL_%02d.txt not found; zero-filling mode %d.", m, m)
            continue

        data = np.loadtxt(fname, comments="%")
        w_raw = data[2:, 1].copy()

        # Normalize: W / sinh(dy * k)²
        # When dy=0 (centered beam), sinh(0)=0 → Wss is undefined;
        # return zeros (no dipole contribution at axis).
        if dy == 0.0:
            Wss[i, 1:] = 0.0
        else:
            denom = np.sinh(dy * k) ** 2
            Wss[i, 1:] = w_raw / denom

    return Wss


# ---------------------------------------------------------------------------
# PP_WakeLQ — longitudinal & quadrupole wakes
# ---------------------------------------------------------------------------


def compute_wake_long_quad(
    wcc: np.ndarray,
    n_modes: int | None = None,
) -> dict:
    """Compute Wlong and Wquad from the Wcc coupling matrix.

    Replicates ``PP_WakeLQ.m`` exactly.

    Algorithm
    ---------
    .. math::

        W_{\\mathrm{long}}(s) &= \\frac{2}{D} \\cdot 10^{-3}
            \\sum_{i=1}^{N_m} W_{\\mathrm{cc},i}(s) \\\\[4pt]
        F_Q(k_i, s) &= k_i^2 \\cdot W_{\\mathrm{cc},i}(s) \\\\[4pt]
        \\Sigma_Q(s) &= \\sum_{i=1}^{N_m} F_Q(k_i, s) \\\\[4pt]
        W_{\\mathrm{quad}}(s) &= -\\frac{2}{D} \\cdot 10^{-6}
            \\cdot \\mathrm{IntegrTr}\\bigl(h_s, \\Sigma_Q\\bigr)

    Parameters
    ----------
    wcc : np.ndarray
        Wcc matrix from :func:`assemble_wcc`.
        Shape ``(n_modes+1, ns+1)``.
    n_modes : int, optional
        Number of modes to use.  Defaults to all available modes.

    Returns
    -------
    dict
        Keys:
        - ``s``: np.ndarray — longitudinal coordinate [m]
        - ``Wlong``: np.ndarray — monopole wake [V/pC]
        - ``Wquad``: np.ndarray — quadrupole wake [V/pC/mm]
        - ``D``: float — structure width [m]
        - ``k_values``: np.ndarray — mode wavenumbers [rad/m]
    """
    D = wcc[0, 0]
    s = wcc[0, 1:].copy()
    ns = len(s)
    hs = float(s[1] - s[0])

    # Number of modes
    Nm_avail = wcc.shape[0] - 1  # rows after header
    if n_modes is None:
        n_modes = Nm_avail
    else:
        n_modes = min(n_modes, Nm_avail)

    # Sum over modes
    WL = np.zeros(ns, dtype=np.float64)
    WQ_sum = np.zeros(ns, dtype=np.float64)

    k_vals = wcc[1:n_modes + 1, 0].copy()

    for i in range(n_modes):
        k = k_vals[i]
        w_mode = wcc[i + 1, 1:]        # Wcc(i, s) for all s
        WL += w_mode
        WQ_sum += k * k * w_mode       # k² * Wcc(i, s)

    # Convert to physical units
    Wlong = WL * (2.0 / D) * 1e-3       # V/pC
    Wquad_raw = integr_tr(hs, WQ_sum)   # cumulative integral
    Wquad = -Wquad_raw * (2.0 / D) * 1e-6  # V/pC/mm

    return {
        "s": s,
        "Wlong": Wlong,
        "Wquad": Wquad,
        "D": D,
        "k_values": k_vals,
    }


# ---------------------------------------------------------------------------
# PP_WakeLQD — longitudinal, quadrupole & dipole wakes
# ---------------------------------------------------------------------------


def compute_wake_long_quad_dipole(
    wcc: np.ndarray,
    wss: np.ndarray,
    n_modes_cc: int | None = None,
    n_modes_ss: int | None = None,
) -> dict:
    """Compute Wlong, Wquad, and Wdipole from Wcc and Wss matrices.

    Replicates ``PP_WakeLQD.m`` exactly.

    Same as :func:`compute_wake_long_quad` for Wcc → Wlong, Wquad,
    plus Wdipole computed from the Wss matrix::

        W_{\\mathrm{dipole}}(s) = -\\frac{2}{D} \\cdot 10^{-6}
            \\cdot \\mathrm{IntegrTr}\\bigl(h_s,
            \\sum_i k_i^2 \\cdot W_{\\mathrm{ss},i}(s)\\bigr)

    Parameters
    ----------
    wcc : np.ndarray
        Wcc matrix from :func:`assemble_wcc`.
    wss : np.ndarray
        Wss matrix from :func:`assemble_wss`.
    n_modes_cc : int, optional
        Number of cos-cos modes.
    n_modes_ss : int, optional
        Number of sin-sin modes.

    Returns
    -------
    dict
        Keys: ``s``, ``Wlong``, ``Wquad``, ``Wdipole``, ``D``,
        ``k_cc``, ``k_ss``.
    """
    # Process CC (cos-cos) → Wlong, Wquad
    result_cc = compute_wake_long_quad(wcc, n_modes=n_modes_cc)
    s = result_cc["s"]
    D = result_cc["D"]
    hs = float(s[1] - s[0])

    # Process SS (sin-sin) → Wdipole
    Nm_ss_avail = wss.shape[0] - 1
    if n_modes_ss is None:
        n_modes_ss = Nm_ss_avail
    else:
        n_modes_ss = min(n_modes_ss, Nm_ss_avail)

    WD_sum = np.zeros(len(s), dtype=np.float64)
    k_ss = wss[1:n_modes_ss + 1, 0].copy()

    for i in range(n_modes_ss):
        k = k_ss[i]
        w_mode = wss[i + 1, 1:]
        WD_sum += k * k * w_mode

    Wdipole_raw = integr_tr(hs, WD_sum)
    Wdipole = -Wdipole_raw * (2.0 / D) * 1e-6  # V/pC/mm

    return {
        "s": s,
        "Wlong": result_cc["Wlong"],
        "Wquad": result_cc["Wquad"],
        "Wdipole": Wdipole,
        "D": D,
        "k_cc": result_cc["k_values"],
        "k_ss": k_ss,
    }


# ---------------------------------------------------------------------------
# PP_WakeZY — off-axis wake at arbitrary (y0, y)
# ---------------------------------------------------------------------------


def compute_wake_off_axis(
    wcc: np.ndarray,
    wss: np.ndarray,
    y0: float,
    y: float,
    n_modes_cc: int | None = None,
    n_modes_ss: int | None = None,
) -> dict:
    """Compute off-axis longitudinal (Wz) and transverse (Wy) wakes.

    Replicates ``PP_WakeZY.m`` exactly.  For a source at offset *y0*
    and a witness at offset *y* (both in metres), the wake potentials
    are built from the coupling matrices::

        Wz(s) = (2/D)·10⁻³ Σ [Wcc·cosh(k·y)·cosh(k·y₀)
                             + Wss·sinh(k·y)·sinh(k·y₀)]
        Wy(s) = −(2/D)·10⁻³·IntegrTr(hₛ, Σ k·[Wcc·sinh(k·y)·cosh(k·y₀)
                                               + Wss·cosh(k·y)·sinh(k·y₀)])

    Parameters
    ----------
    wcc : np.ndarray
        Wcc matrix from :func:`assemble_wcc`.
    wss : np.ndarray
        Wss matrix from :func:`assemble_wss`.
    y0 : float
        Source transverse offset [m].
    y : float
        Witness transverse offset [m].
    n_modes_cc : int, optional
        Number of cos-cos modes to use.  Defaults to all.
    n_modes_ss : int, optional
        Number of sin-sin modes to use.  Defaults to all.

    Returns
    -------
    dict
        Keys: ``s`` (np.ndarray [m]), ``Wz`` [V/pC],
        ``Wy`` [V/pC], ``D`` [m], ``k_cc``, ``k_ss``.
    """
    D = wcc[0, 0]
    s = wcc[0, 1:].copy()
    ns = len(s)
    hs = float(s[1] - s[0])

    # Cos-cos modes
    Nm_cc_avail = wcc.shape[0] - 1
    if n_modes_cc is None:
        n_modes_cc = Nm_cc_avail
    else:
        n_modes_cc = min(n_modes_cc, Nm_cc_avail)

    # Sin-sin modes
    Nm_ss_avail = wss.shape[0] - 1
    if n_modes_ss is None:
        n_modes_ss = Nm_ss_avail
    else:
        n_modes_ss = min(n_modes_ss, Nm_ss_avail)

    Wz = np.zeros(ns, dtype=np.float64)
    Wy_sum = np.zeros(ns, dtype=np.float64)

    # Use the smaller of the two mode counts, as both matrices are summed jointly
    n_modes = min(n_modes_cc, n_modes_ss)

    for i in range(n_modes):
        k = wcc[i + 1, 0]  # wavenumber [rad/m]

        wcc_i = wcc[i + 1, 1:]   # Wcc(k, s)  for all s
        wss_i = wss[i + 1, 1:]   # Wss(k, s)  for all s

        chy = np.cosh(k * y)
        shy = np.sinh(k * y)
        chy0 = np.cosh(k * y0)
        shy0 = np.sinh(k * y0)

        # MATLAB:
        #   Fz = Wcc.*cosh(M*y)*cosh(M*y0) + Wss.*sinh(M*y)*sinh(M*y0)
        #   Fy = M*Wcc.*sinh(M*y)*cosh(M*y0) + M*Wss.*cosh(M*y)*sinh(M*y0)
        Fz = wcc_i * chy * chy0 + wss_i * shy * shy0
        Fy = k * (wcc_i * shy * chy0 + wss_i * chy * shy0)

        Wz += Fz
        Wy_sum += Fy

    # Integrate Wy: Wy = -IntegrTr(h, Wy_sum)
    Wy_int = integr_tr(hs, Wy_sum)
    Wy = -Wy_int

    # Scale: Wz *= 2/D * 1e-3;  Wy *= 2/D * 1e-3
    scale = 2.0 / D * 1e-3
    Wz *= scale
    Wy *= scale

    return {
        "s": s,
        "Wz": Wz,
        "Wy": Wy,
        "D": D,
        "k_cc": wcc[1:n_modes + 1, 0].copy(),
        "k_ss": wss[1:n_modes + 1, 0].copy(),
    }


# ---------------------------------------------------------------------------
# Bunch profile & loss factors (flat geometry)
# ---------------------------------------------------------------------------


def _add_bunch_and_loss_factors(
    data_dir: Path,
    result: dict,
) -> None:
    """Load Iz0.txt bunch profile and compute loss/kick factors.

    Adds the following keys to *result* in-place:
    - ``bunch``: np.ndarray — bunch profile on the wake s-grid
    - ``loss_long``: float — loss factor for Wlong [V/pC]
    - ``loss_quad``: float (if Wquad present) — kick factor [V/pC/mm]
    - ``loss_dipole``: float (if Wdipole present) — kick factor [V/pC/mm]

    Parameters
    ----------
    data_dir : Path
        Directory containing ``Iz0.txt`` (the ``magn/`` or ``elec/`` directory).
    result : dict
        Output from :func:`compute_wake_long_quad` or
        :func:`compute_wake_long_quad_dipole`.  Must contain at least
        ``s`` and ``Wlong``.  Modified in-place.
    """
    iz_path = data_dir / "Iz0.txt"
    if not iz_path.exists():
        logger.debug("Iz0.txt not found in %s; skipping bunch & loss.", data_dir)
        result["bunch"] = None
        return

    # Load offset from wakeL_01.txt
    wl_path = data_dir / "wakeL_01.txt"
    if not wl_path.exists():
        logger.debug("wakeL_01.txt not found; skipping bunch.")
        result["bunch"] = None
        return

    wl_data = np.loadtxt(wl_path, comments="%")
    offset = int(wl_data[0, 1])

    # Load Iz0.txt
    iz_data = np.loadtxt(iz_path)
    s_iz = iz_data[:, 0]                    # s-coordinate
    Iz_2d = iz_data[:, 1:]                  # current profiles (strip s-col)

    # FLAT geometry: dy = offset * hr  (NO +0.5!)
    # Bunch column: Iz(:, offset+3) in MATLAB 1-indexed
    #   → Iz_2d[:, offset+1] in 0-indexed (s-col stripped)
    col_idx = int(offset) + 1
    if col_idx >= Iz_2d.shape[1]:
        logger.warning("offset+1 (=%d) exceeds Iz0 columns (%d); using last column.",
                       col_idx, Iz_2d.shape[1])
        col_idx = Iz_2d.shape[1] - 1
    bunch_raw = Iz_2d[:, col_idx] * 1e9

    # Interpolate to wake s-grid
    s_wake = result["s"]
    bunch_on_s = np.interp(s_wake, s_iz, bunch_raw, left=0.0, right=0.0)
    result["bunch"] = bunch_on_s

    # Compute loss / kick factors
    from pyecho.mathlib.loss import loss_shape

    if "Wlong" in result and result["Wlong"] is not None:
        loss, _spread, _peak = loss_shape(
            np.column_stack([s_wake, bunch_on_s]),
            np.column_stack([s_wake, result["Wlong"]]),
        )
        result["loss_long"] = loss

    if "Wquad" in result and result["Wquad"] is not None:
        # MATLAB: [lossQ,spreadQ]=LossShape([s' B'],[s' -WQ'])
        loss, _spread, _peak = loss_shape(
            np.column_stack([s_wake, bunch_on_s]),
            np.column_stack([s_wake, -result["Wquad"]]),
        )
        result["loss_quad"] = loss

    if "Wdipole" in result and result["Wdipole"] is not None:
        # MATLAB: [lossD,spreadD]=LossShape([s' B'],[s' -WD'])
        loss, _spread, _peak = loss_shape(
            np.column_stack([s_wake, bunch_on_s]),
            np.column_stack([s_wake, -result["Wdipole"]]),
        )
        result["loss_dipole"] = loss


# ---------------------------------------------------------------------------
# High-level flat wake processor
# ---------------------------------------------------------------------------


def process_flat_wake(
    magn_dir: str | Path,
    elec_dir: str | Path | None = None,
    n_modes_cc: int = 15,
    n_modes_ss: int = 15,
    compute_dipole: bool = True,
) -> dict:
    """Full flat-geometry wake processing pipeline.

    Convenience function that runs :func:`assemble_wcc`, optionally
    :func:`assemble_wss`, and :func:`compute_wake_long_quad` (or
    :func:`compute_wake_long_quad_dipole`).

    Parameters
    ----------
    magn_dir : str or Path
        Directory with ``wakeL_XX.txt`` for magnetic (cos-cos) modes.
    elec_dir : str or Path, optional
        Directory with ``wakeL_XX.txt`` for electric (sin-sin) modes.
        If ``None``, only Wcc processing is done.
    n_modes_cc : int
        Number of cos-cos modes.
    n_modes_ss : int
        Number of sin-sin modes.
    compute_dipole : bool
        If ``True`` and *elec_dir* is provided, also compute Wdipole.

    Returns
    -------
    dict
        Keys: ``wcc``, ``wss`` (if applicable), ``s``, ``Wlong``,
        ``Wquad``, ``Wdipole`` (if applicable).
    """
    magn_dir = Path(magn_dir)
    logger.info("Assembling Wcc from %s (%d modes)", magn_dir, n_modes_cc)
    wcc = assemble_wcc(magn_dir, n_modes=n_modes_cc)

    wss = None
    if elec_dir is not None:
        elec_dir = Path(elec_dir)
        logger.info("Assembling Wss from %s (%d modes)", elec_dir, n_modes_ss)
        wss = assemble_wss(elec_dir, n_modes=n_modes_ss)

    if wss is not None and compute_dipole:
        result = compute_wake_long_quad_dipole(
            wcc, wss,
            n_modes_cc=n_modes_cc,
            n_modes_ss=n_modes_ss,
        )
        result["wcc"] = wcc
        result["wss"] = wss
    else:
        result = compute_wake_long_quad(wcc, n_modes=n_modes_cc)
        result["wcc"] = wcc
        result["wss"] = wss

    # ── Load bunch profile & compute loss factors ──
    _add_bunch_and_loss_factors(magn_dir, result)

    return result
