"""I/O subpackage for importing and exporting ECHO2D simulation data.

Provides structured serialisation of simulation results to HDF5 and
other portable formats.

Basic usage::

    >>> from pyecho.io.hdf5 import export_hdf5, load_hdf5
    >>> export_hdf5(result, "simulation.h5")
    >>> data = load_hdf5("simulation.h5")
"""

from pyecho.io.hdf5 import export_hdf5, load_hdf5

__all__ = [
    "export_hdf5",
    "load_hdf5",
]
