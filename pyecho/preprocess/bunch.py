"""Custom bunch profile generation and validation.

ECHO2D supports three beam definitions via the ``InPartFile`` parameter
(ECHO Manual §4.3.3):

1. ``-`` — Default Gaussian pencil bunch (rms length from ``BunchSigma``)
2. ``*.txt`` — Pencil beam with arbitrary longitudinal profile
3. ``*.bin`` — 3-D particle distribution

This module handles option 2: generating and validating arbitrary
longitudinal bunch profiles in the ECHO2D ASCII format.

File format (ECHO Manual §4.3.3)::

    % s[m] charge [normalized]
    s_0  rho(s_0)
    s_1  rho(s_1)
    ...
    s_N  rho(s_N)

- ``s`` — longitudinal coordinate [m], positive from head to tail, uniform step
- ``rho(s)`` — bunch charge density in arbitrary units (normalized)
- The s-coordinate should be positive and increase from head (leading)
  to tail (trailing) of the bunch.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


def generate_gaussian(
    sigma: float = 0.001,
    n_points: int = 500,
    n_sigma: float = 6.0,
    s_min: float = 0.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Generate a Gaussian longitudinal bunch profile.

    Parameters
    ----------
    sigma : float
        RMS bunch length [m].
    n_points : int
        Number of grid points.
    n_sigma : float
        Total width in units of sigma (centered in the window).
    s_min : float
        Starting s-coordinate [m].

    Returns
    -------
    s : np.ndarray
        Longitudinal coordinate [m] (uniform step, positive, head→tail).
    rho : np.ndarray
        Gaussian charge density (normalized to peak=1).
    """
    s_center = n_sigma / 2.0 * sigma
    s = np.linspace(s_min, n_sigma * sigma, n_points)
    rho = np.exp(-0.5 * ((s - s_center) / sigma) ** 2)
    return s, rho


def generate_flattop(
    sigma: float = 0.001,
    rise: float = 0.0001,
    flat_length: float = 0.002,
    n_points: int = 500,
    s_min: float = 0.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Generate a flattop longitudinal bunch profile.

    Creates a bunch with Gaussian rising/falling edges and a flat central
    region.  The total RMS length is approximately ``sigma``.

    Parameters
    ----------
    sigma : float
        Target RMS bunch length [m] (approximate).
    rise : float
        Rise/fall length (Gaussian sigma for edges) [m].
    flat_length : float
        Length of the flat central region [m].
    n_points : int
        Number of grid points.
    s_min : float
        Starting s-coordinate [m].

    Returns
    -------
    s : np.ndarray
        Longitudinal coordinate [m].
    rho : np.ndarray
        Flattop charge density (normalized to peak=1).
    """
    total = 2 * 3.0 * rise + flat_length
    s = np.linspace(s_min, total, n_points)

    # Rising edge (Gaussian)
    rise_center = 3.0 * rise
    # Flat region
    flat_start = rise_center + 1.5 * rise
    flat_end = flat_start + flat_length
    # Falling edge (Gaussian)
    fall_center = flat_end + 1.5 * rise

    rho: np.ndarray = np.zeros(n_points, dtype=np.float64)
    for i, si in enumerate(s):
        if si < flat_start:
            rho[i] = np.exp(-0.5 * ((si - rise_center) / rise) ** 2)
        elif si <= flat_end:
            rho[i] = 1.0
        else:
            rho[i] = np.exp(-0.5 * ((si - fall_center) / rise) ** 2)

    return s, rho


def save_bunch_profile(
    out_path: str | Path,
    s: np.ndarray,
    rho: np.ndarray,
) -> Path:
    """Save a bunch profile in ECHO2D-compatible format.

    Parameters
    ----------
    out_path : str or Path
        Output file path (``*.txt``).
    s : np.ndarray
        Longitudinal coordinate [m].
    rho : np.ndarray
        Bunch charge density (arbitrary units).

    Returns
    -------
    Path
        Path to the saved file.
    """
    out_path = Path(out_path)
    data = np.column_stack([s, rho])
    header = "% s[m] charge [normalized]"
    np.savetxt(str(out_path), data, header=header, fmt="%.8e")
    logger.info("Bunch profile saved to %s (%d points)", out_path, len(s))
    return out_path


def validate_bunch_profile(filepath: str | Path) -> dict:
    """Validate an ECHO2D bunch profile file.

    Checks:
    - File exists and is readable
    - At least 2 data points
    - s-coordinate is positive and increases monotonically
    - Uniform s-step (within 1% tolerance)
    - Charge density is non-negative

    Parameters
    ----------
    filepath : str or Path
        Path to the bunch profile file.

    Returns
    -------
    dict
        Keys: ``valid`` (bool), ``n_points`` (int), ``s_range`` (tuple),
        ``s_step`` (float), ``peak`` (float), ``issues`` (list[str]).
    """
    filepath = Path(filepath)
    issues: list[str] = []

    if not filepath.is_file():
        return {"valid": False, "n_points": 0, "issues": [f"File not found: {filepath}"]}

    try:
        data = np.loadtxt(filepath, comments=["%", "#"])
    except Exception as exc:
        return {"valid": False, "n_points": 0, "issues": [f"Parse error: {exc}"]}

    if data.ndim != 2 or data.shape[1] < 2:
        issues.append("Expected 2 columns (s, charge)")
        return {"valid": False, "n_points": data.shape[0] if data.ndim == 2 else 0, "issues": issues}

    s = data[:, 0]
    rho = data[:, 1]

    if len(s) < 2:
        issues.append("At least 2 data points required")

    if np.any(s < 0):
        issues.append("s-coordinate should be positive (head→tail)")

    if not np.all(np.diff(s) > 0):
        issues.append("s-coordinate must increase monotonically")

    # Check uniform step
    ds = np.diff(s)
    if len(ds) > 1:
        rel_std = np.std(ds) / np.mean(ds)
        if rel_std > 0.01:
            issues.append(f"s-step not uniform (rel stddev={rel_std:.4f})")

    if np.any(rho < 0):
        issues.append("Charge density has negative values")

    return {
        "valid": len(issues) == 0,
        "n_points": len(s),
        "s_range": (float(s[0]), float(s[-1])),
        "s_step": float(np.mean(ds)) if len(ds) > 0 else 0.0,
        "peak": float(np.max(rho)),
        "issues": issues,
    }
