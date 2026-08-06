"""Recta (rectangular) geometry wake post-processing.

Replicates the full MATLAB pipeline for recta-geometry wake computations
used in ECHO2D examples with rectangular structures (dechirpers, absorbers,
tapered collimators, etc.).

.. note::

   This module uses ``"recta"`` to match ECHO2D's ``GeometryType=recta``
   convention.  The CLI may display ``"flat"`` or ``"rectangular"`` as
   user-friendly aliases, but the internal geometry type string is always
   ``"recta"``.

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
* ``PP_WakeZY.m`` → :func:`compute_wake_zy` (2-D map over witness
  offsets; single-pair case via :func:`compute_wake_off_axis`)
* ``PP_WakeL_Tm_Tq_Td.m`` → :func:`compute_wake_tm_tq_td`
* ``IntegrTr.m`` → :func:`pyecho.mathlib.integration.integr_tr`
* ``LossShape.m`` → :func:`pyecho.mathlib.loss.loss_shape`

**Critical convention (different from round geometry!)**
    In recta geometry the effective transverse step is::

        dy = offset * hr         (NO +0.5!)

    This is fundamentally different from the round-geometry convention
    ``dy = (offset + 0.5) * hr``.

Unit conversions (recta geometry)
----------------------------------
.. note::
   The variable ``D`` denotes the **total width** of the rectangular
   structure, i.e. the ``Width`` parameter in ``input_in.txt``.
   :math:`k_x = \\pi m / D`.  This is only meaningful for ``GeometryType=recta``;
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
from pyecho.parser import find_wake_file

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def _clamp_mode_count(requested: int | None, available: int) -> int:
    """Return the number of coupling-matrix modes to process.

    Defaults to *available* (all rows present) when *requested* is
    ``None``; otherwise caps *requested* at the rows actually available.
    """
    if requested is None:
        return available
    return min(requested, available)


def _sum_squared_wake(
    matrix: np.ndarray,
    n_modes: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Return ``(Σᵢ kᵢ²·Wᵢ(s), k_values)`` for the first *n_modes* rows.

    Shared by the quadrupole/dipole wake computations, which sum the
    per-mode ``k²·W`` products before integration.
    """
    k_values = matrix[1:n_modes + 1, 0].copy()
    total: np.ndarray = np.zeros(matrix.shape[1] - 1, dtype=np.float64)
    for i in range(n_modes):
        total += k_values[i] ** 2 * matrix[i + 1, 1:]
    return total, k_values


def _check_matching_s(wcc: np.ndarray, wss: np.ndarray) -> None:
    """Raise :class:`ValueError` unless Wcc and Wss share the s-grid and width D.

    Both matrices must have the same number of columns, identical
    longitudinal coordinates in row 0, and the same structure width ``D``
    (cell ``[0, 0]``) so that per-mode rows can be summed element-wise and
    the wavenumbers ``k = π·m/D`` are consistent.  Differing *mode* counts
    are fine (only the common modes are used); differing *s*-grids or *D*
    are not.
    """
    if (
        wcc.shape[1] != wss.shape[1]
        or not np.allclose(wcc[0, 1:], wss[0, 1:])
        or not np.isclose(wcc[0, 0], wss[0, 0])
    ):
        raise ValueError(
            "Wcc and Wss must share the same longitudinal s-grid and "
            "structure width D (different column count, first data row, "
            "or D value)."
        )


def _truncation_error(
    n_modes: int,
    last_mode: np.ndarray,
    all_modes: np.ndarray,
) -> float:
    """MATLAB ``error_*`` truncation-error estimate, in percent.

    Reproduces ``Nm·Σ(last_mode²)/ΣΣ(all_modes²)·100`` from
    ``PP_WakeL_Tm_Tq_Td.m``.  Returns ``0.0`` when the summed modal energy
    vanishes (avoids a 0/0 NaN on axis).
    """
    denom = float(np.sum(all_modes * all_modes))
    if denom == 0.0:
        return 0.0
    numer = float(np.sum(last_mode * last_mode))
    return float(n_modes) * numer / denom * 100.0


def _assemble_coupling(
    data_dir: str | Path,
    n_modes: int,
    *,
    parity: str,
) -> np.ndarray:
    """Shared body of :func:`assemble_wcc` / :func:`assemble_wss`.

    Loads the raw ``wakeL_XX.txt`` odd modes and builds the
    ``(n_modes+1, ns+1)`` coupling matrix, normalising each mode by
    ``cosh²(dy·k)`` (``parity="cosh"``) or ``sinh²(dy·k)``
    (``parity="sinh"``).  For the ``sinh`` case with ``dy = 0``
    (centered beam) the mode rows are zero-filled, because ``sinh(0) = 0``
    would make the normalisation undefined (no dipole contribution on
    axis).
    """
    data_dir = Path(data_dir)

    fname_1 = find_wake_file(data_dir, 1)
    if fname_1 is None:
        raise FileNotFoundError(f"wakeL_01.txt not found in {data_dir}")

    data_1 = np.loadtxt(fname_1, comments="%")
    hr = data_1[0, 0]
    offset = int(data_1[0, 1])
    D = data_1[1, 0]

    # FLAT geometry: dy = offset * hr  (NO +0.5!)
    dy = offset * hr

    s = data_1[2:, 0].copy()
    ns = len(s)

    # Allocate the coupling matrix: (n_modes+1) rows × (ns+1) cols.
    # Row 0 = [D, s_0, ..., s_{ns-1}]; each mode row i starts with k_i.
    matrix: np.ndarray = np.zeros((n_modes + 1, ns + 1), dtype=np.float64)
    matrix[0, 1:] = s
    matrix[0, 0] = D

    denom_fn = np.cosh if parity == "cosh" else np.sinh

    for i in range(1, n_modes + 1):
        m = 2 * i - 1  # odd mode number
        k = np.pi / D * m
        matrix[i, 0] = k

        fname = find_wake_file(data_dir, m)
        if fname is None:
            logger.warning("wakeL_%02d.txt not found; zero-filling mode %d.", m, m)
            continue

        data = np.loadtxt(fname, comments="%")
        w_raw = data[2:, 1].copy()

        if parity == "sinh" and dy == 0.0:
            matrix[i, 1:] = 0.0
        else:
            matrix[i, 1:] = w_raw / denom_fn(dy * k) ** 2

    return matrix


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
    return _assemble_coupling(data_dir, n_modes, parity="cosh")


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
    return _assemble_coupling(data_dir, n_modes, parity="sinh")


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
    hs = float(s[1] - s[0])

    n_modes = _clamp_mode_count(n_modes, wcc.shape[0] - 1)

    # Sum over modes: Wlong ∝ Σ Wcc(i, s);  Wquad ∝ Σ k²·Wcc(i, s)
    WL = wcc[1:n_modes + 1, 1:].sum(axis=0)
    WQ_sum, k_vals = _sum_squared_wake(wcc, n_modes)

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

    # Process SS (sin-sin) → Wdipole.  The dipole uses the CC s-grid for
    # its integration step, so both matrices must share the same number of
    # longitudinal points.
    if wss.shape[1] != wcc.shape[1]:
        raise ValueError(
            "Wcc and Wss must have the same number of longitudinal points."
        )
    n_modes_ss = _clamp_mode_count(n_modes_ss, wss.shape[0] - 1)
    WD_sum, k_ss = _sum_squared_wake(wss, n_modes_ss)

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
# PP_WakeZY — off-axis wake at arbitrary (y0, y) and 2-D maps
# ---------------------------------------------------------------------------


def compute_wake_zy(
    wcc: np.ndarray,
    wss: np.ndarray,
    y_offsets: np.ndarray,
    y0: float,
    n_modes_cc: int | None = None,
    n_modes_ss: int | None = None,
) -> dict:
    """Compute off-axis Wz/Wy wakes on a 2-D ``(y, s)`` map.

    Replicates ``PostProcessor2D/Wakes/Flat/PP_WakeZY.m`` exactly, but for
    a *range* of witness offsets instead of a single one: ``y_offsets`` is a
    1-D array of witness transverse offsets (fixed source offset ``y0``), so
    each wake is returned as a 2-D array indexed by ``(witness_offset, s)``.
    Use :func:`compute_wake_off_axis` for the single-``(y0, y)`` case.

    For a source at offset *y0* and witnesses at offsets *y* (all in
    metres), the per-mode terms are::

        Fz(k, y, s) = Wcc(k, s)·cosh(k·y)·cosh(k·y₀)
                    + Wss(k, s)·sinh(k·y)·sinh(k·y₀)
        Fy(k, y, s) = k·[Wcc(k, s)·sinh(k·y)·cosh(k·y₀)
                       + Wss(k, s)·cosh(k·y)·sinh(k·y₀)]

    and the physical wakes are::

        Wz(y, s) = (2/D)·10⁻³ · Σₖ Fz(k, y, s)
        Wy(y, s) = −(2/D)·10⁻³ · IntegrTr(hₛ, Σₖ Fy(k, y, s))

    Parameters
    ----------
    wcc : np.ndarray
        Wcc matrix from :func:`assemble_wcc` (shape ``(n_modes+1, ns+1)``).
    wss : np.ndarray
        Wss matrix from :func:`assemble_wss` (same layout).
    y_offsets : np.ndarray
        1-D array of witness transverse offsets [m].
    y0 : float
        Source transverse offset [m].
    n_modes_cc : int, optional
        Number of cos-cos modes to use.  Defaults to all available.
    n_modes_ss : int, optional
        Number of sin-sin modes to use.  Defaults to all available.

    Returns
    -------
    dict
        Keys:
        - ``y_offsets``: np.ndarray (ny,) — witness offsets [m]
        - ``s``: np.ndarray (ns,) — longitudinal coordinate [m]
        - ``y0``: float — source offset [m]
        - ``Wz``: np.ndarray (ny, ns) — longitudinal wake [V/pC]
        - ``Wy``: np.ndarray (ny, ns) — transverse wake [V/pC]
        - ``D``: float — structure width [m]
        - ``k_cc``, ``k_ss``: np.ndarray — wavenumbers used [rad/m]

    Raises
    ------
    ValueError
        If ``y_offsets`` is not 1-D, Wcc/Wss s-grids differ, or fewer than
        one usable mode is present.
    """
    y_offsets = np.atleast_1d(np.asarray(y_offsets, dtype=np.float64))
    if y_offsets.ndim != 1:
        raise ValueError(f"y_offsets must be 1-D, got shape {y_offsets.shape}")

    _check_matching_s(wcc, wss)

    D = wcc[0, 0]
    s = wcc[0, 1:].copy()
    ns = len(s)
    hs = float(s[1] - s[0])
    ny = len(y_offsets)

    n_modes_cc = _clamp_mode_count(n_modes_cc, wcc.shape[0] - 1)
    n_modes_ss = _clamp_mode_count(n_modes_ss, wss.shape[0] - 1)

    # Use the smaller of the two mode counts, as both matrices are summed jointly
    n_modes = min(n_modes_cc, n_modes_ss)
    if n_modes <= 0:
        raise ValueError("At least one usable mode is required in Wcc and Wss.")

    Fz_sum: np.ndarray = np.zeros((ny, ns), dtype=np.float64)
    Fy_sum: np.ndarray = np.zeros((ny, ns), dtype=np.float64)

    for i in range(n_modes):
        k = wcc[i + 1, 0]            # wavenumber [rad/m]

        wcc_i = wcc[i + 1, 1:]       # Wcc(k, s)  for all s
        wss_i = wss[i + 1, 1:]       # Wss(k, s)  for all s

        cosh_ky = np.cosh(k * y_offsets)   # (ny,)
        sinh_ky = np.sinh(k * y_offsets)   # (ny,)
        chy0 = float(np.cosh(k * y0))
        shy0 = float(np.sinh(k * y0))

        # MATLAB:
        #   Fz = Wcc.*cosh(M*y)*cosh(M*y0) + Wss.*sinh(M*y)*sinh(M*y0)
        #   Fy = M*Wcc.*sinh(M*y)*cosh(M*y0) + M*Wss.*cosh(M*y)*sinh(M*y0)
        Fz_sum += (
            wcc_i[None, :] * (cosh_ky[:, None] * chy0)
            + wss_i[None, :] * (sinh_ky[:, None] * shy0)
        )
        Fy_sum += k * (
            wcc_i[None, :] * (sinh_ky[:, None] * chy0)
            + wss_i[None, :] * (cosh_ky[:, None] * shy0)
        )

    # Integrate Wy per witness offset, then scale: 2/D · 1e-3
    scale = 2.0 / D * 1e-3
    Wz_map = Fz_sum * scale
    Wy_int: np.ndarray = np.empty_like(Fy_sum)
    for j in range(ny):
        Wy_int[j, :] = integr_tr(hs, Fy_sum[j, :])
    Wy_map = -Wy_int * scale

    return {
        "y_offsets": y_offsets,
        "s": s,
        "y0": y0,
        "Wz": Wz_map,
        "Wy": Wy_map,
        "D": D,
        "k_cc": wcc[1:n_modes + 1, 0].copy(),
        "k_ss": wss[1:n_modes + 1, 0].copy(),
    }


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

    This is the single-``(y0, y)`` specialisation of :func:`compute_wake_zy`;
    its numerical results are identical to calling that function with
    ``y_offsets=[y]``.

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
    result = compute_wake_zy(
        wcc,
        wss,
        y_offsets=np.array([y], dtype=np.float64),
        y0=y0,
        n_modes_cc=n_modes_cc,
        n_modes_ss=n_modes_ss,
    )
    return {
        "s": result["s"],
        "Wz": result["Wz"][0],
        "Wy": result["Wy"][0],
        "D": result["D"],
        "k_cc": result["k_cc"],
        "k_ss": result["k_ss"],
    }


# ---------------------------------------------------------------------------
# PP_WakeL_Tm_Tq_Td — monopole / quadrupole / dipole wakes off axis
# ---------------------------------------------------------------------------


def compute_wake_tm_tq_td(
    wcc: np.ndarray,
    wss: np.ndarray,
    y0: float = 0.0,
    y: float = 0.0,
    n_modes_cc: int | None = None,
    n_modes_ss: int | None = None,
) -> dict:
    """Compute transverse monopole (Tm), quadrupole (Tq) and dipole (Td) wakes.

    Replicates ``PostProcessor2D/Wakes/Flat/PP_WakeL_Tm_Tq_Td.m`` exactly.
    For a beam (source) offset *y0* and a witness offset *y* (both in
    metres), the Wcc (cos-cos) and Wss (sin-sin) coupling matrices are
    combined into three physical transverse wakes plus the longitudinal
    (monopole) wake::

        Wlong(s) = (2/D)·10⁻³ · Σₖ [Wcc·cosh(k·y)·cosh(k·y₀)
                                    + Wss·sinh(k·y)·sinh(k·y₀)]

        Tm(s)    = −(2/D)·10⁻³ · IntegrTr(hₛ, Σₖ k·[Wcc·sinh(k·y)·cosh(k·y₀)
                                                 + Wss·cosh(k·y)·sinh(k·y₀)])

        Tq(s)    = −(2/D)·10⁻⁶ · IntegrTr(hₛ, Σₖ k²·[Wcc·cosh(k·y)·cosh(k·y₀)
                                                  + Wss·sinh(k·y)·sinh(k·y₀)])

        Td(s)    = −(2/D)·10⁻⁶ · IntegrTr(hₛ, Σₖ k²·[Wcc·sinh(k·y)·sinh(k·y₀)
                                                  + Wss·cosh(k·y)·cosh(k·y₀)])

    The names follow the MATLAB output file ``WakeLQD.txt``: ``Tm`` is the
    transverse wake labelled ``Wm`` there, ``Tq`` the quadrupole wake
    ``Wquad`` and ``Td`` the dipole wake ``Wdipole``.  On axis
    (``y = y0 = 0``) ``Tm`` vanishes while ``Tq``/``Td`` reduce to the
    on-axis quadrupole / dipole wakes of :func:`compute_wake_long_quad` /
    :func:`compute_wake_long_quad_dipole`.

    Parameters
    ----------
    wcc : np.ndarray
        Wcc matrix from :func:`assemble_wcc`.
    wss : np.ndarray
        Wss matrix from :func:`assemble_wss`.
    y0 : float, optional
        Source transverse offset [m].  Default 0 (on axis).
    y : float, optional
        Witness transverse offset [m].  Default 0 (on axis).
    n_modes_cc : int, optional
        Number of cos-cos modes to use.  Defaults to all available.
    n_modes_ss : int, optional
        Number of sin-sin modes to use.  Defaults to all available.

    Returns
    -------
    dict
        Keys:
        - ``s``: np.ndarray — longitudinal coordinate [m]
        - ``D``: float — structure width [m]
        - ``y0``, ``y``: float — the offsets used
        - ``Wlong``: np.ndarray — longitudinal (monopole) wake [V/pC]
        - ``Tm``: np.ndarray — transverse wake [V/pC]  (MATLAB ``Wm``)
        - ``Tq``: np.ndarray — quadrupole wake [V/pC/mm] (MATLAB ``Wquad``)
        - ``Td``: np.ndarray — dipole wake [V/pC/mm] (MATLAB ``Wdipole``)
        - ``Wm``, ``Wquad``, ``Wdipole``: aliases of Tm/Tq/Td (MATLAB names)
        - ``Fm``, ``FQ``, ``FD``: np.ndarray (n_modes, ns) — modal terms
        - ``k_cc``, ``k_ss``: np.ndarray — wavenumbers used [rad/m]
        - ``error_long``, ``error_m``, ``error_quad``, ``error_dipole``:
          float — truncation-error estimates in percent (MATLAB ``error_*``)

    Raises
    ------
    ValueError
        If Wcc/Wss s-grids differ or fewer than one usable mode is present.
    """
    _check_matching_s(wcc, wss)

    D = wcc[0, 0]
    s = wcc[0, 1:].copy()
    ns = len(s)
    hs = float(s[1] - s[0])

    n_modes_cc = _clamp_mode_count(n_modes_cc, wcc.shape[0] - 1)
    n_modes_ss = _clamp_mode_count(n_modes_ss, wss.shape[0] - 1)

    # Use the smaller of the two mode counts, as both matrices are summed jointly
    n_modes = min(n_modes_cc, n_modes_ss)
    if n_modes <= 0:
        raise ValueError("At least one usable mode is required in Wcc and Wss.")

    WL: np.ndarray = np.zeros(ns, dtype=np.float64)
    Wm_sum: np.ndarray = np.zeros(ns, dtype=np.float64)
    WQ_sum: np.ndarray = np.zeros(ns, dtype=np.float64)
    WD_sum: np.ndarray = np.zeros(ns, dtype=np.float64)
    Fm: np.ndarray = np.zeros((n_modes, ns), dtype=np.float64)
    FQ: np.ndarray = np.zeros((n_modes, ns), dtype=np.float64)
    FD: np.ndarray = np.zeros((n_modes, ns), dtype=np.float64)

    for i in range(n_modes):
        M = wcc[i + 1, 0]            # wavenumber [rad/m]

        wcc_i = wcc[i + 1, 1:]       # Wcc(k, s)  for all s
        wss_i = wss[i + 1, 1:]       # Wss(k, s)  for all s

        chy = float(np.cosh(M * y))
        shy = float(np.sinh(M * y))
        chy0 = float(np.cosh(M * y0))
        shy0 = float(np.sinh(M * y0))

        # MATLAB:
        #   dW  = Wcc.*cosh(M*y).*cosh(M*y0) + Wss.*sinh(M*y).*sinh(M*y0)
        #   ddy = Wcc.*sinh(M*y).*cosh(M*y0) + Wss.*cosh(M*y).*sinh(M*y0)
        dW = wcc_i * chy * chy0 + wss_i * shy * shy0
        ddy = wcc_i * shy * chy0 + wss_i * chy * shy0

        WL += dW

        Fm[i, :] = M * ddy
        Wm_sum += Fm[i, :]

        FQ[i, :] = M * M * dW
        WQ_sum += FQ[i, :]

        # MATLAB: FD = M²·(Wcc·sinh(M·y)·sinh(M·y0) + Wss·cosh(M·y)·cosh(M·y0))
        FD[i, :] = M * M * (wcc_i * shy * shy0 + wss_i * chy * chy0)
        WD_sum += FD[i, :]

    # Integrate transverse / quadrupole / dipole modal sums, then scale.
    Wm = -integr_tr(hs, Wm_sum) * (2.0 / D) * 1e-3   # V/pC
    WQ = -integr_tr(hs, WQ_sum) * (2.0 / D) * 1e-6   # V/pC/mm
    WD = -integr_tr(hs, WD_sum) * (2.0 / D) * 1e-6   # V/pC/mm
    Wlong = WL * (2.0 / D) * 1e-3                     # V/pC

    # Truncation-error estimates (percent) as in the MATLAB script.
    error_long = _truncation_error(n_modes, wcc[n_modes, 1:], wcc[1:, 1:])
    error_m = _truncation_error(n_modes, Fm[n_modes - 1, :], Fm)
    error_quad = _truncation_error(n_modes, FQ[n_modes - 1, :], FQ)
    error_dipole = _truncation_error(n_modes, FD[n_modes - 1, :], FD)

    return {
        "s": s,
        "D": D,
        "y0": y0,
        "y": y,
        "Wlong": Wlong,
        "Tm": Wm,
        "Tq": WQ,
        "Td": WD,
        "Wm": Wm,          # MATLAB output-column name
        "Wquad": WQ,       # MATLAB output-column name
        "Wdipole": WD,     # MATLAB output-column name
        "Fm": Fm,
        "FQ": FQ,
        "FD": FD,
        "k_cc": wcc[1:n_modes + 1, 0].copy(),
        "k_ss": wss[1:n_modes + 1, 0].copy(),
        "error_long": error_long,
        "error_m": error_m,
        "error_quad": error_quad,
        "error_dipole": error_dipole,
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


def process_recta_wake(
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
    else:
        result = compute_wake_long_quad(wcc, n_modes=n_modes_cc)
    result["wcc"] = wcc
    result["wss"] = wss

    # ── Load bunch profile & compute loss factors ──
    _add_bunch_and_loss_factors(magn_dir, result)

    return result
