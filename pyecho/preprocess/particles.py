"""Particle preprocessing utilities for ECHO2D simulations.

Provides converters between the ASTRA and ECHO2D particle formats,
charge-deposition algorithms, and line-current profile generators.

ECHO2D Particle Format
----------------------
ECHO2D uses a text-based particle format with 6 columns::

    z   y   x'  y'  Pz  weight

- ``z`` [m] — longitudinal coordinate
- ``y`` [m] — transverse coordinate (radial for round, vertical for flat)
- ``x'`` — horizontal divergence (momentum ratio)
- ``y'`` — vertical divergence (momentum ratio)
- ``Pz`` — longitudinal momentum [eV/c]
- ``weight`` — macro-particle weight

ASTRA Particle Format
---------------------
ASTRA uses a similar format but with momenta stored in eV/c directly::

    x   y   z   px   py   pz   clock   charge   ...

Conversion between the formats involves scaling momenta by :math:`m_e c`
and reordering coordinates.

Usage::

    >>> from pyecho.preprocess.particles import (
    ...     ASTRAConverter, create_line_current, particles_to_charge
    ... )
    >>> ASTRAConverter.astra_to_echo("distribution.astra", "particles.echo")
    >>> create_line_current(sigma=0.001, output_file="line_current.txt")
    >>> rho = particles_to_charge(z0, nz, nr, hz, hr, particles)
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from pyecho.errors import PyEchoError
from pyecho.mathlib import c, e, me

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ASTRA ↔ ECHO2D converter
# ---------------------------------------------------------------------------

class ASTRAConverter:
    """Convert between ASTRA and ECHO2D particle distribution formats.

    ASTRA format:  x, y, z, px, py, pz, clock, charge, ...
    (momenta in eV/c; coordinates in m)

    ECHO2D format: z, y, x', y', Pz, weight
    (Pz in eV/c; coordinates in m; weighted macro-particles)

    The conversion uses:

    .. math::

        x' = p_x / p_z, \\quad
        y' = p_y / p_z, \\quad
        P_z = p_z \\; (\\text{eV/c})
    """

    @staticmethod
    def astra_to_echo(
        astra_file: str | Path,
        echo_file: str | Path,
        z_offset: float = -0.01,
    ) -> None:
        """Convert an ASTRA particle distribution to ECHO2D format.

        Parameters
        ----------
        astra_file : str or Path
            Path to the input ASTRA particle file.
        echo_file : str or Path
            Path for the output ECHO2D particle file.
        z_offset : float
            Offset applied to the z coordinate [m].
            Default ``-0.01`` places the bunch 1 cm before the
            nominal reference.

        Raises
        ------
        PyEchoError
            If the ASTRA file cannot be read or has insufficient columns.

        Notes
        -----
        The converter assumes ASTRA columns are::

            x, y, z, px, py, pz, clock, charge, index, status

        Only the first 6 columns (x, y, z, px, py, pz) are required.
        If ``charge`` is present (column 8), it is used as the
        macro-particle weight; otherwise unit weight is assigned.
        """
        astra_file = Path(astra_file).resolve()
        echo_file = Path(echo_file).resolve()

        if not astra_file.is_file():
            raise PyEchoError(f"ASTRA file not found: {astra_file}")

        logger.info("Converting ASTRA → ECHO2D: %s → %s",
                     astra_file.name, echo_file.name)

        # Read ASTRA data
        try:
            data = np.loadtxt(astra_file, dtype=np.float64)
        except Exception as exc:
            raise PyEchoError(
                f"Failed to read ASTRA file {astra_file}: {exc}"
            ) from exc

        if data.ndim == 1:
            data = data.reshape(1, -1)
        n_cols = data.shape[1]
        if n_cols < 6:
            raise PyEchoError(
                f"ASTRA file {astra_file} has {n_cols} columns; "
                "expected at least 6 (x, y, z, px, py, pz)."
            )

        # Extract columns
        x = data[:, 0]
        y = data[:, 1]
        z = data[:, 2] + z_offset
        px = data[:, 3]  # eV/c
        py = data[:, 4]  # eV/c
        pz = data[:, 5]  # eV/c

        # Compute divergences: x' = px / pz, y' = py / pz
        # Guard against pz == 0
        pz_safe = np.where(np.abs(pz) > 1e-30, pz, 1e-30)
        xp = px / pz_safe
        yp = py / pz_safe

        # Weight: use charge column if available, else 1.0
        if n_cols >= 8:
            weight = data[:, 7]
            # Normalise so total charge = 1
            total_weight = np.sum(np.abs(weight))
            if total_weight > 0:
                weight = weight / total_weight
        else:
            weight = np.ones(len(data), dtype=np.float64)

        # Write ECHO2D format: z, y, x', y', Pz, weight
        echo_data = np.column_stack([z, y, xp, yp, pz, weight])

        echo_file.parent.mkdir(parents=True, exist_ok=True)
        np.savetxt(
            echo_file, echo_data,
            fmt="%.15e",
            delimiter=" ",
            header="z y x' y' Pz weight (converted from ASTRA)",
        )

        logger.info("Converted %d particles to ECHO2D format", len(data))

    @staticmethod
    def echo_to_astra(
        echo_file: str | Path,
        astra_file: str | Path,
    ) -> None:
        """Convert an ECHO2D particle output to ASTRA format.

        Parameters
        ----------
        echo_file : str or Path
            Path to the input ECHO2D particle file.
        astra_file : str or Path
            Path for the output ASTRA particle file.

        Raises
        ------
        PyEchoError
            If the ECHO2D file cannot be read.
        """
        echo_file = Path(echo_file).resolve()
        astra_file = Path(astra_file).resolve()

        if not echo_file.is_file():
            raise PyEchoError(f"ECHO2D file not found: {echo_file}")

        logger.info("Converting ECHO2D → ASTRA: %s → %s",
                     echo_file.name, astra_file.name)

        try:
            data = np.loadtxt(echo_file, dtype=np.float64)
        except Exception as exc:
            raise PyEchoError(
                f"Failed to read ECHO2D file {echo_file}: {exc}"
            ) from exc

        if data.ndim == 1:
            data = data.reshape(1, -1)

        # ECHO2D columns: z, y, x', y', Pz, weight
        z = data[:, 0]
        y = data[:, 1]
        xp = data[:, 2]
        yp = data[:, 3]
        pz = data[:, 4]
        weight = data[:, 5] if data.shape[1] >= 6 else np.ones(len(data))

        # Reconstruct momenta
        px = xp * pz
        py = yp * pz

        # ASTRA format: x, y, z, px, py, pz, clock, charge, index, status
        # We don't have x coordinate from ECHO2D (round geometry),
        # so set x = 0
        x = np.zeros_like(z)
        clock = np.zeros_like(z)
        index = np.arange(1, len(data) + 1, dtype=np.float64)
        status = np.ones(len(data), dtype=np.float64)

        astra_data = np.column_stack([
            x, y, z, px, py, pz, clock, weight, index, status,
        ])

        astra_file.parent.mkdir(parents=True, exist_ok=True)
        np.savetxt(
            astra_file, astra_data,
            fmt="%.15e",
            delimiter=" ",
            header="x y z px py pz clock charge index status (converted from ECHO2D)",
        )

        logger.info("Converted %d particles to ASTRA format", len(data))


# ---------------------------------------------------------------------------
# ECHO2D beam profile format (manual section 4.3.3)
# ---------------------------------------------------------------------------

def create_beam_profile(
    s_vals: np.ndarray,
    rho_vals: np.ndarray,
    output_file: str | Path,
) -> str:
    """Create an ECHO2D arbitrary beam profile file.

    Format (manual section 4.3.3)::

        % s[m] charge [normalized]
        s0  ρ(s0)
        s1  ρ(s1)
        ...

    Where *s* is the longitudinal coordinate along the bunch (positive,
    increasing from head to tail), and *ρ(s)* is the bunch shape in
    arbitrary units.  The shape is projected onto the mesh interval
    ``[0, StepZ * MeshLength]``.

    Parameters
    ----------
    s_vals : np.ndarray
        1-D array of *s* coordinates [m], uniform step, positive,
        monotonically increasing.
    rho_vals : np.ndarray
        1-D array of charge density values (same length as *s_vals*).
    output_file : str or Path
        Destination path for the profile file.

    Returns
    -------
    str
        Absolute path to the written file.

    Raises
    ------
    PyEchoError
        If the arrays have different lengths or *s_vals* are not
        monotonically increasing.
    """
    if len(s_vals) != len(rho_vals):
        raise PyEchoError(
            f"s_vals and rho_vals must have same length, "
            f"got {len(s_vals)} vs {len(rho_vals)}"
        )
    if len(s_vals) < 2:
        raise PyEchoError("Need at least 2 data points for beam profile")

    output_file = Path(output_file).resolve()
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as fp:
        fp.write("%  s[m]  \t charge [normalized]\n")
        for s, rho in zip(s_vals, rho_vals):
            fp.write(f"{s:.6e}\t {rho:.6e}\n")

    logger.info(
        "Beam profile written: %s (%d points, s ∈ [%.3e, %.3e] m)",
        output_file, len(s_vals), s_vals[0], s_vals[-1],
    )
    return str(output_file)


def parse_beam_profile(filepath: str | Path) -> tuple[np.ndarray, np.ndarray]:
    """Parse an ECHO2D arbitrary beam profile ``.txt`` file.

    Parameters
    ----------
    filepath : str or Path
        Path to the beam profile file.

    Returns
    -------
    tuple[np.ndarray, np.ndarray]
        ``(s_vals, rho_vals)`` — *s* coordinates [m] and charge
        density values.

    Raises
    ------
    PyEchoError
        If the file cannot be parsed.
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise PyEchoError(f"Beam profile file not found: {filepath}")

    try:
        lines = filepath.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise PyEchoError(f"Cannot read beam profile {filepath}: {exc}") from exc

    s_vals: list[float] = []
    rho_vals: list[float] = []

    for line in lines:
        stripped = line.strip()
        # Skip header comment line and empty lines
        if not stripped or stripped.startswith("%"):
            continue
        tokens = stripped.split()
        if len(tokens) >= 2:
            try:
                s_vals.append(float(tokens[0]))
                rho_vals.append(float(tokens[1]))
            except ValueError:
                continue  # skip non-numeric lines

    if len(s_vals) < 2:
        raise PyEchoError(
            f"Beam profile {filepath} has fewer than 2 valid data points"
        )

    return np.array(s_vals, dtype=np.float64), np.array(rho_vals, dtype=np.float64)


# ---------------------------------------------------------------------------
# Line current profile generator
# ---------------------------------------------------------------------------

def create_line_current(
    sigma: float,
    output_file: str | Path,
    n_points: int = 200,
) -> str:
    """Create a Gaussian line current profile file for ECHO2D.

    ECHO2D's ``InPartFile`` can accept a pre-computed line current
    profile instead of using the internal Gaussian generator.  The
    file has the format::

        z0  hz  nz
        I(z0, t0)
        I(z0 + hz, t0)
        ...

    Parameters
    ----------
    sigma : float
        RMS bunch length [m].
    output_file : str or Path
        Destination path for the line current file.
    n_points : int
        Number of points in the profile.  Default 200 gives good
        resolution for typical bunch lengths.

    Returns
    -------
    str
        Absolute path to the written file.

    Notes
    -----
    The profile is a normalised Gaussian:

    .. math::

        \\lambda(z) = \\frac{1}{\\sqrt{2\\pi}\\sigma}
        \\exp\\left(-\\frac{z^2}{2\\sigma^2}\\right)
    """
    from pyecho.mathlib.gauss import gauss

    output_file = Path(output_file).resolve()
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Generate grid
    z_range = 5.0 * sigma
    z0 = -z_range
    hz = 2.0 * z_range / (n_points - 1)

    z_vals = np.linspace(z0, z0 + (n_points - 1) * hz, n_points)
    profile = gauss(z_vals, sigma)

    # Write file
    with open(output_file, "w", encoding="utf-8") as fp:
        fp.write(f"{z0:.15e}  {hz:.15e}  {n_points}\n")
        for val in profile:
            fp.write(f"{val:.15e}\n")

    logger.info("Line current profile written: %s (%d points, σ=%.3e m)",
                 output_file, n_points, sigma)
    return str(output_file)


# ---------------------------------------------------------------------------
# Charge deposition (Particles2Charge.m)
# ---------------------------------------------------------------------------

def particles_to_charge(
    z_mesh_head: float,
    nz: int,
    nr: int,
    hz: float,
    hr: float,
    particles: np.ndarray,
) -> np.ndarray:
    """Deposit particles onto a 2-D charge grid using bilinear interpolation.

    Replicates the algorithm in ``Particles2Charge.m`` exactly,
    including the normalisation and boundary handling.

    Parameters
    ----------
    z_mesh_head : float
        Longitudinal position of the moving mesh head [m].
    nz : int
        Number of mesh points in the longitudinal direction.
    nr : int
        Number of mesh points in the transverse (radial) direction.
    hz : float
        Longitudinal mesh step [m].
    hr : float
        Transverse (radial) mesh step [m].
    particles : np.ndarray
        2-D array of macro-particles with shape ``(N, 6)``.
        Columns: ``[z, y, x', y', Pz, weight]``.

    Returns
    -------
    np.ndarray
        2-D charge density array of shape ``(nz, nr)`` in arbitrary
        units (not normalised by ε₀).

    Notes
    -----
    This is a standalone function (not a method) to match the MATLAB
    implementation and allow direct use in scripts.

    The charge grid indices are computed as:

    - ``iz = floor((z - z_mesh_head) / hz)``
    - ``ir = floor(abs(y) / hr)``

    Particles outside the grid are silently skipped.

    Examples
    --------
    >>> particles = np.loadtxt("bunch.txt")
    >>> rho = particles_to_charge(0.0, 52, 100, 2e-4, 2e-4, particles)
    >>> print(f"Total deposited charge: {rho.sum():.4e}")
    """
    charge = np.zeros((nz, nr), dtype=np.float64)

    z_coords = particles[:, 0]
    y_coords = particles[:, 1]  # radial coordinate for round geometry
    weights = particles[:, 5]

    for i in range(len(particles)):
        z = z_coords[i]
        r = abs(y_coords[i])
        w = weights[i]

        # Find grid indices
        iz_f = (z - z_mesh_head) / hz
        ir_f = r / hr

        iz0 = int(np.floor(iz_f))
        ir0 = int(np.floor(ir_f))

        # Check bounds
        if iz0 < 0 or iz0 >= nz - 1:
            continue
        if ir0 < 0 or ir0 >= nr - 1:
            continue

        # Bilinear interpolation weights
        dz = iz_f - iz0
        dr = ir_f - ir0

        w00 = (1.0 - dz) * (1.0 - dr) * w
        w10 = dz * (1.0 - dr) * w
        w01 = (1.0 - dz) * dr * w
        w11 = dz * dr * w

        # Accumulate
        charge[iz0, ir0] += w00
        charge[iz0 + 1, ir0] += w10
        charge[iz0, ir0 + 1] += w01
        charge[iz0 + 1, ir0 + 1] += w11

    # Normalise by cell volume (matching Particles2Charge.m)
    cell_volume = hz * hr
    if cell_volume > 0:
        charge /= cell_volume

    return charge
