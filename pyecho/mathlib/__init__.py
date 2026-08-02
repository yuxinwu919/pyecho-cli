"""Mathematical utilities for ECHO2D post-processing.

Provides physical constants (matching MatLib4ECHO/PhysConsts.m) and
numerical functions for integration, FFT, loss calculation, and
convolution.

Submodules
----------
gauss         : Gaussian (normal) distribution
integration   : Trapezoidal integration & difference operators
fft           : Wake ↔ impedance Fourier transforms
loss          : Loss factor & RMS spread calculations
convolution   : Impedance × bunch convolution (ZaZb)
"""

from pyecho.mathlib.gauss import gauss
from pyecho.mathlib.integration import diff_l, int0, integr_tr
from pyecho.mathlib.fft import impedance2wake, wake2impedance
from pyecho.mathlib.loss import long_loss2, long_loss2_cm, loss_shape
from pyecho.mathlib.convolution import za_zb

# Physical constants (from PhysConsts.m)
from scipy import constants as _scipy_constants

#: Speed of light in vacuum [m/s].
c: float = _scipy_constants.c  # 2.99792458e8

#: Elementary charge [C].
e: float = _scipy_constants.e  # 1.602176634e-19

#: Electron rest mass [kg].
me: float = _scipy_constants.m_e  # 9.1093837015e-31

#: Vacuum permittivity [F/m].
eps0: float = _scipy_constants.epsilon_0  # 8.8541878128e-12

#: Vacuum permeability [H/m].
mu0: float = _scipy_constants.mu_0  # 1.25663706212e-6

#: Characteristic impedance of vacuum [Ω].
Z0: float = float(
    _scipy_constants.physical_constants[
        "characteristic impedance of vacuum"
    ][0]
)  # ~376.73

#: SI factor 4πε₀.
SI: float = 4.0 * _scipy_constants.pi * eps0

#: Alfvén current [A].
IA: float = me * c**3 / e * SI

__all__ = [
    # Functions
    "gauss",
    "integr_tr",
    "diff_l",
    "int0",
    "wake2impedance",
    "impedance2wake",
    "loss_shape",
    "long_loss2",
    "long_loss2_cm",
    "za_zb",
    # Constants
    "c",
    "e",
    "me",
    "eps0",
    "mu0",
    "Z0",
    "SI",
    "IA",
    "E00",
    "Esi2gauss",
    "grad",
    "h_plank",
]

# ---- Additional physical constants (PhysConsts.m) ----

#: Electron rest energy [eV].  E00 = m_e·c² / e
E00: float = me * c**2 / e  # ~510998.95 eV

#: Conversion factor: 1 Gauss → SI.  (1 G = 1e-4 T)
Esi2gauss: float = 1e-4 / (c * 1e-8)

#: Degree → radian conversion factor.
grad: float = _scipy_constants.pi / 180.0

#: Planck constant divided by elementary charge [eV·s].
h_plank: float = 4.135667516e-15
