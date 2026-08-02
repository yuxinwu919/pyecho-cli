"""Impedance × bunch-spectrum convolution → wake.

Implements the frequency-domain convolution method used in
``MatLib4ECHO/ZaZb.m``: the impedance *Za*(*f*) is multiplied by
the Fourier transform of the bunch profile *Zb*(*f*), and the
product is inverse-transformed to obtain the wake potential.

.. math::

    W(s) = -\\mathrm{IFT}\\{ Za(f) \\cdot \\mathrm{FT}\\{ \\lambda(s) \\} \\}
"""

from __future__ import annotations

import numpy as np
from numpy.polynomial import Polynomial

from pyecho.mathlib.fft import wake2impedance, impedance2wake


#: Speed of light [m/s] — must match the value used in :mod:`pyecho.mathlib.fft`.
_C_LIGHT: float = 2.99792458e8


def za_zb(
    xb: np.ndarray,
    bunch: np.ndarray,
    Za0: np.ndarray,
) -> np.ndarray:
    """Convolve impedance with bunch spectrum to obtain the wake.

    Equivalent to ``MatLib4ECHO/ZaZb.m``.

    Algorithm
    ---------
    1. Double the grid size (zero-pad) to avoid circular convolution
       artefacts.
    2. Interpolate the impedance *Za0*(*f*) onto the FFT frequency grid.
       *Za0* is a 3‑column array: ``[f, Re(Za), Im(Za)]``.
    3. Compute *Zb*(*f*) = FFT{*λ*(*s*) · *c*}.
    4. Multiply: *Z*(*f*) = *Za*(*f*) · *Zb*(*f*), enforcing conjugate
       symmetry so the inverse transform is real.
    5. Inverse FFT → *W*(*s*), return the first half (physical domain).

    Parameters
    ----------
    xb : np.ndarray
        1-D longitudinal coordinate of the bunch [m], uniformly spaced.
    bunch : np.ndarray
        1-D bunch charge-density profile λ(*s*), same length as *xb*.
    Za0 : np.ndarray
        (*N_z*, 3) impedance table: column 0 = *f* [Hz],
        column 1 = Re(*Za*) [Ω], column 2 = Im(*Za*) [Ω].

    Returns
    -------
    res : np.ndarray
        (*N_b*, 1) wake potential −*W*(*s*) [V/C] (negative sign
        matches the MATLAB output convention).
    """
    nb = len(xb)
    ds = xb[1] - xb[0]
    n = 2 * nb  # double-length grid for linear (non-circular) convolution

    # --- frequency grid (same as wake2impedance) ---
    dt = ds / _C_LIGHT
    f = np.arange(n, dtype=np.float64) / (dt * n)

    # --- interpolate impedance onto the FFT frequency grid ---
    f2k = 2.0 * np.pi / _C_LIGHT  # f → k conversion

    # Remove duplicate frequencies (unique returns sorted)
    f0_raw = Za0[:, 0]
    f0_unique, i0 = np.unique(f0_raw, return_index=True)
    f0_k = f0_unique / f2k  # convert Hz → rad/m

    # Linear interpolation of real and imaginary parts
    re_z = _interp1_linear(f0_k, Za0[i0, 1], f[:nb], fill_value=0.0)
    im_z = _interp1_linear(f0_k, Za0[i0, 2], f[:nb], fill_value=0.0)
    Za = re_z + 1j * im_z

    # --- extend bunch to double length with zero-padding ---
    xb1 = xb[0] + np.arange(n) * ds
    bunch1 = np.zeros(n, dtype=np.float64)
    bunch1[:nb] = bunch

    # --- FFT of bunch (scaled by c) ---
    _, Zb = wake2impedance(xb1, bunch1 * _C_LIGHT)

    # --- multiply Za · Zb, enforce conjugate symmetry ---
    Z = np.zeros(n, dtype=np.complex128)
    Z[:nb] = Za * Zb[:nb]
    # Mirror with conjugation for real-valued inverse
    Z[nb:] = np.conj(Z[:nb][::-1])

    # --- inverse FFT → wake ---
    _, wa = impedance2wake(f, Z)

    # Return first half, negated (MATLAB convention)
    res = -wa[:nb].reshape(-1, 1)
    return res


def _interp1_linear(
    x: np.ndarray,
    y: np.ndarray,
    xi: np.ndarray,
    fill_value: float = 0.0,
) -> np.ndarray:
    """1-D linear interpolation matching MATLAB ``interp1(..., 'linear', 0)``.

    Parameters
    ----------
    x : np.ndarray
        Source abscissae (must be sorted).
    y : np.ndarray
        Source ordinates.
    xi : np.ndarray
        Target abscissae.
    fill_value : float
        Value to use for out-of-bounds queries.

    Returns
    -------
    np.ndarray
        Interpolated values at *xi*.
    """
    result = np.full_like(xi, fill_value, dtype=np.float64)

    # Find insertion indices
    idx = np.searchsorted(x, xi)

    # Interior points: idx in [1, len(x)-1]
    interior = (idx > 0) & (idx < len(x))
    i_int = idx[interior]
    x_left = x[i_int - 1]
    x_right = x[i_int]
    y_left = y[i_int - 1]
    y_right = y[i_int]
    t = (xi[interior] - x_left) / (x_right - x_left)
    result[interior] = y_left + t * (y_right - y_left)

    # Exact hits on the left endpoint
    exact = idx == 0
    result[exact & (xi == x[0])] = y[0]

    # Exact hits on the right endpoint
    exact_end = idx == len(x)
    result[exact_end & (xi == x[-1])] = y[-1]

    return result
