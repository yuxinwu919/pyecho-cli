"""Gaussian function — equivalent to MatLib4ECHO/gauss.m."""

import numpy as np
from typing import cast


def gauss(x: np.ndarray, sigma: float) -> np.ndarray:
    """Normalised Gaussian (normal distribution PDF).

    .. math::

        g(x) = \\frac{1}{\\sigma \\sqrt{2\\pi}}
               \\exp\\!\\left(-\\frac{x^2}{2\\sigma^2}\\right)

    This is the exact Python equivalent of ``MatLib4ECHO/gauss.m``.
    The integral over all :math:`x` equals 1.

    Parameters
    ----------
    x : np.ndarray
        Evaluation points (same units as *sigma*).
    sigma : float
        Standard deviation (RMS width).

    Returns
    -------
    np.ndarray
        Gaussian values at each *x*, same shape as *x*.
    """
    return cast(
        np.ndarray,
        np.exp(-(x ** 2) / (2.0 * sigma * sigma)) / (sigma * np.sqrt(2.0 * np.pi)),
    )
