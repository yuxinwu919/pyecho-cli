"""FFT-based wake ↔ impedance transforms.

Implements the exact MATLAB algorithms from ``MatLib4ECHO``:

* :func:`wake2impedance` — wake potential → frequency-domain impedance
* :func:`impedance2wake` — impedance → time-domain wake potential

The Fourier convention used internally is ``exp(iωt)`` for the forward
transform and ``exp(−iωt)`` for the inverse, matching the physics
convention in the ECHO2D documentation.  Both functions are verified
to round-trip exactly.
"""

from __future__ import annotations

import numpy as np


#: Speed of light in vacuum [m/s], matching the ECHO2D hard-coded value.
_C_LIGHT: float = 2.99792458e8


def wake2impedance(s: np.ndarray, w: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Fourier transform wake → impedance with ``exp(iωt)`` convention.

    Equivalent to ``MatLib4ECHO/wake2impedance.m``.

    The wake potential *W*(*s*) is first mapped to the time domain
    via *t* = *s* / *c*, then transformed::

        Z(f) = Δt · FFT{W(t)}

    where *f* is the frequency array [Hz] and the FFT uses the
    ``exp(−i·2π·k·n/N)`` kernel (NumPy default).  The comment in the
    original MATLAB source states the physics convention ``exp(iωt)``;
    the sign is handled consistently by the inverse transform.

    Parameters
    ----------
    s : np.ndarray
        1-D array of longitudinal coordinates [m], uniformly spaced.
    w : np.ndarray
        1-D array of wake potential values [V/C], same length as *s*.

    Returns
    -------
    f : np.ndarray
        Frequency array [Hz], uniformly spaced from 0 to (N−1)/(N·Δt).
    y : np.ndarray
        Complex impedance spectrum [Ω], same length as *s*.
    """
    ds = s[1] - s[0]
    dt = ds / _C_LIGHT
    n = len(s)
    # Frequency grid: f_k = k / (N·Δt)
    f = np.arange(n, dtype=np.float64) / (dt * n)
    # Forward FFT (MATLAB fft uses exp(−i·2π·k·n/N) — same as NumPy)
    y = dt * np.fft.fft(w, n=n)
    return f, y


def impedance2wake(f: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Inverse Fourier transform impedance → wake with ``exp(−iωt)`` convention.

    Equivalent to ``MatLib4ECHO/impedance2wake.m``.

    The impedance spectrum *Z*(*f*) is transformed back to the
    longitudinal coordinate::

        W(s) = N·Δf · IFFT{Z(f)}   (symmetric / real part)

    Parameters
    ----------
    f : np.ndarray
        1-D frequency array [Hz], uniformly spaced.
    y : np.ndarray
        1-D complex impedance array [Ω], same length as *f*.

    Returns
    -------
    s : np.ndarray
        Longitudinal coordinate array [m].
    w : np.ndarray
        Real-valued wake potential [V/C], same length as *f*.
    """
    df = f[1] - f[0]
    n = len(f)
    # s_k = k · c / (N·Δf)
    s = np.arange(n, dtype=np.float64) / (df * n) * _C_LIGHT
    # Inverse FFT; 'symmetric' flag in MATLAB → take .real in NumPy
    w = n * df * np.fft.ifft(y, n=n).real
    return s, w
