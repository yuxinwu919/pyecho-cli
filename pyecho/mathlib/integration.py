"""Numerical integration / differentiation utilities.

Provides the three core operators used throughout the ECHO2D MATLAB
post-processing library:

* :func:`integr_tr` — cumulative trapezoidal integration (IntegrTr.m)
* :func:`diff_l`     — custom alternating-sign difference operator (DiffL.m)
* :func:`int0`       — non-uniform trapezoidal integration (Int0.m)

All functions are written to produce **identical numerical results**
to their MATLAB counterparts, including edge-case handling.
"""

from __future__ import annotations

import numpy as np


def integr_tr(h: float, x: np.ndarray) -> np.ndarray:
    """Cumulative trapezoidal integration on a uniform grid.

    Equivalent to ``MatLib4ECHO/IntegrTr.m``.

    For an array *x* of length *n*, returns *y* where::

        y[0] = 0
        y[k] = h · Σ_{i=1}^{k} ½ (x[i] + x[i-1])    for k ≥ 1

    This is the cumulative integral of a piecewise-linear interpolant.

    Parameters
    ----------
    h : float
        Uniform grid spacing.
    x : np.ndarray
        1-D array of function values.

    Returns
    -------
    np.ndarray
        Cumulative integral, same length as *x*.
    """
    n = len(x)
    y: np.ndarray = np.empty(n, dtype=np.float64)
    y[0] = 0.0
    for i in range(1, n):
        y[i] = y[i - 1] + 0.5 * (x[i] + x[i - 1])
    y *= h
    return y


def diff_l(h: float, x: np.ndarray) -> np.ndarray:
    """Custom alternating-sign difference operator.

    Equivalent to ``MatLib4ECHO/DiffL.m``.

    Defined recursively as::

        y[0] = 0
        y[k] = [2·(x[k] − x[k−1]) − y[k−1]] / h    for k ≥ 1

    The operator produces an output whose sign alternates with each
    successive difference, i.e.::

        y[k] = (2/h) · Σ_{j=1}^{k} (−1)^{k−j} · (x[j] − x[j−1])

    Parameters
    ----------
    h : float
        Uniform grid spacing.
    x : np.ndarray
        1-D array of function values.

    Returns
    -------
    np.ndarray
        Differentiated array, same length as *x*.
    """
    n = len(x)
    y: np.ndarray = np.empty(n, dtype=np.float64)
    y[0] = 0.0
    for i in range(1, n):
        y[i] = 2.0 * (x[i] - x[i - 1]) - y[i - 1]
    y /= h
    return y


def int0(x: np.ndarray, y: np.ndarray) -> float:
    """Non-uniform trapezoidal integration.

    Equivalent to ``MatLib4ECHO/Int0.m``.

    Computes the definite integral of *y* with respect to *x* using
    the trapezoidal rule on a (possibly) non-uniform grid::

        I = ½ y₀ (x₁ − x₀)                       ← first half-interval
          + Σ_{i=1}^{n−2} yᵢ · ½ (xᵢ₊₁ − xᵢ₋₁)   ← interior full bins
          + ½ yₙ₋₁ (xₙ₋₁ − xₙ₋₂)                 ← last half-interval

    Parameters
    ----------
    x : np.ndarray
        1-D array of abscissae (monotonically increasing).
    y : np.ndarray
        1-D array of ordinates, same length as *x*.

    Returns
    -------
    float
        Approximate definite integral.
    """
    n = len(x)
    result = y[0] * 0.5 * (x[1] - x[0])
    for i in range(1, n - 1):
        dx = 0.5 * (x[i + 1] - x[i - 1])
        result += y[i] * dx
    result += y[n - 1] * 0.5 * (x[n - 1] - x[n - 2])
    return float(result)
