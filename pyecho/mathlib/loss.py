"""Wake loss factor and RMS spread calculations.

Provides the two loss-calculation functions from MatLib4ECHO:

* :func:`loss_shape` — loss factor, RMS spread, and peak from
  arbitrary bunch and wake profiles (LossShape.m).
* :func:`long_loss2` — same quantities using an internal Gaussian
  bunch (LongLoss2.m).  **Note:** the *s* coordinate and *sigma*
  are in **cm** in the MATLAB original; this Python version uses
  **metres** consistently.  A wrapper :func:`long_loss2_cm` is
  provided for backwards compatibility.
"""

from __future__ import annotations

import numpy as np

from pyecho.mathlib.gauss import gauss


def loss_shape(
    bunch: np.ndarray,
    wake: np.ndarray,
) -> tuple[float, float, float]:
    """Compute loss factor, RMS spread, and peak wake.

    Equivalent to ``MatLib4ECHO/LossShape.m``.

    Both inputs are expected as two-column arrays where the first
    column is the longitudinal coordinate *s* [m] and the second
    column is the function value.

    The loss factor is defined as::

        κ = −∫ λ(s) · W(s) ds          (Riemann sum, uniform step)

    The RMS spread is::

        σ_κ = √[ ∫ λ(s) · (W(s) + κ)² ds ]

    If the bunch array is shorter than the wake array it is zero-padded.

    Parameters
    ----------
    bunch : np.ndarray
        (*N_b*, 2) array: column 0 = *s* [m], column 1 = λ(*s*).
    wake : np.ndarray
        (*N_w*, 2) array: column 0 = *s* [m], column 1 = *W*(*s*) [V/pC].

    Returns
    -------
    loss : float
        Loss factor κ [V/pC].
    spread : float
        RMS spread of the wake around −κ [V/pC].
    peak : float
        Maximum absolute value of *W*(*s*) [V/pC].
    """
    w = wake[:, 1]
    n = len(w)

    # Zero-pad bunch to match wake length
    bi2: np.ndarray = np.zeros(n, dtype=np.float64)
    nb = len(bunch[:, 1])
    bi2[:nb] = bunch[:, 1]

    h = wake[1, 0] - wake[0, 0]
    loss = -np.dot(bi2, w) * h
    spread = np.sqrt(np.dot(bi2, (w + loss) ** 2) * h)
    peak: float = np.max(np.abs(w))
    return float(loss), float(spread), float(peak)


def long_loss2(
    s: np.ndarray,
    w: np.ndarray,
    sigma: float,
) -> tuple[float, float, np.ndarray]:
    """Loss factor and spread using an internal Gaussian bunch.

    Equivalent to ``MatLib4ECHO/LongLoss2.m``.

    .. warning::
       In the MATLAB original, *s* and *sigma* are in **cm**.
       This Python version expects **metres**.  Use
       :func:`long_loss2_cm` if you need centimetre inputs.

    Parameters
    ----------
    s : np.ndarray
        1-D longitudinal coordinate [m], uniformly spaced.
    w : np.ndarray
        1-D wake potential [V/pC], same length as *s*.
    sigma : float
        Bunch RMS length [m].

    Returns
    -------
    loss : float
        Loss factor κ [V/pC].
    spread : float
        RMS spread [V/pC].
    bunch : np.ndarray
        Gaussian bunch profile evaluated on *s*.
    """
    h = s[1] - s[0]
    bunch = gauss(s, sigma)
    loss = -np.dot(bunch, w) * h
    spread = np.sqrt(np.dot(bunch, (w + loss) ** 2) * h)
    return float(loss), float(spread), bunch


def long_loss2_cm(
    s_cm: np.ndarray,
    w: np.ndarray,
    sigma_cm: float,
) -> tuple[float, float, np.ndarray]:
    """Loss factor and spread — centimetre interface (MATLAB compatible).

    This wrapper converts centimetre inputs to metres, calls
    :func:`long_loss2`, and returns the bunch profile on the
    original centimetre grid.

    Parameters
    ----------
    s_cm : np.ndarray
        1-D longitudinal coordinate [cm].
    w : np.ndarray
        1-D wake potential [V/pC].
    sigma_cm : float
        Bunch RMS length [cm].

    Returns
    -------
    loss : float
        Loss factor κ [V/pC].
    spread : float
        RMS spread [V/pC].
    bunch : np.ndarray
        Gaussian bunch profile, same length as *s_cm*.
    """
    s_m = s_cm * 1e-2
    sigma_m = sigma_cm * 1e-2
    loss, spread, bunch = long_loss2(s_m, w, sigma_m)
    return loss, spread, bunch
