"""Initial electromagnetic field generation for ECHO2D particle tracking.

Replicates the MATLAB workflow in ``GenerateInitialField.m``:

1. Deposit macro-particles onto a charge grid
2. Solve Poisson's equation for the electrostatic potential
3. Compute the electric field from the potential
4. Apply a Lorentz transformation to get the lab-frame fields
5. Write binary field files for ECHO2D

Usage::

    >>> from pyecho.preprocess.field import InitialFieldGenerator
    >>> gen = InitialFieldGenerator(
    ...     pipe_radius=0.01, mesh_length=52, step_z=2e-4, step_y=2e-4,
    ... )
    >>> field_file = gen.generate("particles.txt")
    >>> print(f"Field written to: {field_file}")
"""

from __future__ import annotations

import logging
import struct
from pathlib import Path
from typing import Any, cast

import numpy as np

from pyecho.errors import PreprocessError

logger = logging.getLogger(__name__)


class InitialFieldGenerator:
    """Generate initial electromagnetic field for ECHO2D particle tracking.

    Solves the Poisson equation on a 2-D cylindrical (r-z) mesh to
    obtain the electrostatic field of a given charge distribution,
    then applies a Lorentz boost to the lab frame.

    Parameters
    ----------
    pipe_radius : float
        Radius of the beam pipe [m].  Sets the transverse domain size.
    mesh_length : int
        Number of mesh lines in the longitudinal direction.
    step_z : float
        Longitudinal mesh step [m].
    step_y : float
        Transverse mesh step (radial step for round geometry) [m].

    Attributes
    ----------
    nz : int
        Longitudinal grid size (set during ``generate()``).
    nr : int
        Transverse grid size (set during ``generate()``).

    Notes
    -----
    The Poisson solver uses a simple finite-difference method with
    Dirichlet boundary conditions (φ = 0 on the pipe wall).  For
    axisymmetric geometry, the radial Laplacian includes the
    :math:`1/r \\partial_r` term.

    The Lorentz transformation assumes the bunch travels at *c* in
    the +z direction:

    .. math::

        E_z^{\\text{lab}} = E_z, \\quad
        E_r^{\\text{lab}} = \\gamma E_r, \\quad
        H_\\phi^{\\text{lab}} = \\gamma \\beta c E_r / Z_0
    """

    def __init__(
        self,
        pipe_radius: float,
        mesh_length: int,
        step_z: float,
        step_y: float,
    ) -> None:
        self.pipe_radius = pipe_radius
        self.mesh_length = mesh_length
        self.step_z = step_z
        self.step_y = step_y

        self.nz: int = 0
        self.nr: int = 0

    # ------------------------------------------------------------------
    # Main generation method
    # ------------------------------------------------------------------

    def generate(
        self,
        particle_file: str | Path,
        mesh_position_z: float = 0.0,
        current_filter: int = 1,
    ) -> str:
        """Generate initial field binary files for ECHO2D.

        Parameters
        ----------
        particle_file : str or Path
            Path to the ECHO2D-format particle file (ASCII, 6 columns:
            z, y, x', y', Pz, weight).
        mesh_position_z : float
            Longitudinal mesh centre position [m].
        current_filter : int
            Number of passes of a 2-point low-pass filter applied to
            the deposited current profile.  Default 1.

        Returns
        -------
        str
            Path to the generated field file (binary, ``.bin``).

        Raises
        ------
        PreprocessError
            If the particle file cannot be read or the solver fails.

        Notes
        -----
        The output binary file contains the three field components
        (Ez, Er, Hφ) stored as float32 arrays in column-major order,
        matching ECHO2D's expected format.
        """
        particle_file = Path(particle_file).resolve()
        if not particle_file.is_file():
            raise PreprocessError(
                f"Particle file not found: {particle_file}",
                input_file=particle_file,
            )

        logger.info(
            "Generating initial field: R=%.3e m, mesh=%d, hz=%.3e, hy=%.3e",
            self.pipe_radius, self.mesh_length, self.step_z, self.step_y,
        )

        # ---- 1. Read particle distribution ----
        particles = self._read_particles(particle_file)
        logger.info("Read %d macro-particles", len(particles))

        # ---- 2. Determine grid dimensions ----
        # Longitudinal: centred around mesh_position_z
        nz = self.mesh_length
        self.nz = nz
        nr = int(self.pipe_radius / self.step_y) + 1
        self.nr = nr

        z_min = mesh_position_z - (nz / 2) * self.step_z
        z_max = mesh_position_z + (nz / 2) * self.step_z

        logger.info("Grid: nz=%d, nr=%d", nz, nr)

        # ---- 3. Deposit charge onto grid ----
        charge_grid = self._deposit_charge(
            particles, nz, nr, self.step_z, self.step_y,
            z_min=z_min,
        )

        # Apply longitudinal filter
        if current_filter > 0:
            for _ in range(current_filter):
                charge_grid = self._low_pass_filter_z(charge_grid)

        # ---- 4. Solve Poisson equation ----
        potential = self._solve_poisson(charge_grid, nz, nr,
                                        self.step_z, self.step_y)

        # ---- 5. Compute electric field ----
        Ez, Er = self._compute_efield(potential, nz, nr,
                                      self.step_z, self.step_y)

        # ---- 6. Lorentz transform to lab frame ----
        from pyecho.mathlib import c, Z0

        gamma = 1.0 / np.sqrt(1.0 - 1.0**2)  # β ≈ 1 for ultra-relativistic
        # For β = 1, use large gamma approximation
        # In practice ECHO2D uses β=1 beam, so we treat gamma as large
        # and use: Er_lab ≈ Er (for β=1, the transverse field is
        # compressed in the lab frame but ECHO2D handles this internally)
        # Here we use the finite gamma for correctness
        beta = 0.999999  # effectively 1
        gamma = 1.0 / np.sqrt(1.0 - beta**2)

        Ez_lab = Ez
        Er_lab = gamma * Er
        Hphi_lab = gamma * beta * c * Er / Z0  # Hφ = (γβc/Z0) * Er

        # ---- 7. Write binary output ----
        output_path = particle_file.parent / f"{particle_file.stem}_field.bin"
        with open(output_path, "wb") as fp:
            # Write dimensions header
            fp.write(struct.pack("<ii", nz, nr))
            # Write field components as float32, column-major
            fp.write(Ez_lab.astype(np.float32).tobytes(order="F"))
            fp.write(Er_lab.astype(np.float32).tobytes(order="F"))
            fp.write(Hphi_lab.astype(np.float32).tobytes(order="F"))

        logger.info("Field file written: %s (%d bytes)",
                     output_path, output_path.stat().st_size)
        return str(output_path)

    # ------------------------------------------------------------------
    # Internal: particle I/O
    # ------------------------------------------------------------------

    def _read_particles(self, filepath: Path) -> np.ndarray:
        """Read ECHO2D-format particle file.

        Expected format (6 columns): z, y, x', y', Pz, weight
        """
        try:
            data = np.loadtxt(filepath, dtype=np.float64)
        except Exception as exc:
            raise PreprocessError(
                f"Failed to read particle file {filepath}: {exc}",
                input_file=filepath,
            ) from exc

        if data.ndim == 1:
            data = data.reshape(1, -1)
        if data.shape[1] < 6:
            raise PreprocessError(
                f"Particle file {filepath} has {data.shape[1]} columns; "
                "expected at least 6 (z, y, x', y', Pz, weight).",
                input_file=filepath,
            )
        return cast(np.ndarray, data)

    # ------------------------------------------------------------------
    # Internal: charge deposition (bilinear interpolation)
    # ------------------------------------------------------------------

    def _deposit_charge(
        self,
        particles: np.ndarray,
        nz: int,
        nr: int,
        hz: float,
        hr: float,
        z_min: float = 0.0,
    ) -> np.ndarray:
        """Deposit particles onto a 2-D (z, r) charge grid.

        Uses bilinear (area-weighting) interpolation, matching the
        algorithm in ``Particles2Charge.m``.

        Parameters
        ----------
        particles : np.ndarray
            Particle array with columns (z, y, x', y', Pz, weight).
        nz : int
            Number of grid points in z.
        nr : int
            Number of grid points in r.
        hz : float
            Grid spacing in z [m].
        hr : float
            Grid spacing in r [m].
        z_min : float
            Minimum z coordinate of the grid [m].

        Returns
        -------
        np.ndarray
            2-D charge density array of shape (nz, nr).
        """
        charge: np.ndarray = np.zeros((nz, nr), dtype=np.float64)

        z_coords = particles[:, 0]
        r_coords = np.sqrt(particles[:, 1]**2)  # y → r for round geometry
        weights = particles[:, 5]

        for i in range(len(particles)):
            z = z_coords[i]
            r = r_coords[i]
            w = weights[i]

            # Find grid cell indices
            iz = (z - z_min) / hz
            ir = r / hr

            iz0 = int(np.floor(iz))
            ir0 = int(np.floor(ir))

            if iz0 < 0 or iz0 >= nz - 1 or ir0 < 0 or ir0 >= nr - 1:
                continue

            # Bilinear weights
            dz = iz - iz0
            dr = ir - ir0

            w00 = (1.0 - dz) * (1.0 - dr) * w
            w10 = dz * (1.0 - dr) * w
            w01 = (1.0 - dz) * dr * w
            w11 = dz * dr * w

            charge[iz0, ir0] += w00
            charge[iz0 + 1, ir0] += w10
            charge[iz0, ir0 + 1] += w01
            charge[iz0 + 1, ir0 + 1] += w11

        # Normalise by cell volume
        cell_volume = hz * hr
        if cell_volume > 0:
            charge /= cell_volume

        return charge

    # ------------------------------------------------------------------
    # Internal: low-pass filter
    # ------------------------------------------------------------------

    def _low_pass_filter_z(self, data: np.ndarray) -> np.ndarray:
        """Apply a 2-point low-pass filter along the z-axis.

        Replaces each point with the average of itself and its
        neighbour: ``f[i] = 0.5 * (f[i] + f[i-1])``.
        """
        filtered: np.ndarray = data.copy()
        for i in range(1, data.shape[0]):
            filtered[i, :] = 0.5 * (data[i, :] + data[i - 1, :])
        return filtered

    # ------------------------------------------------------------------
    # Internal: Poisson solver (finite difference, axisymmetric)
    # ------------------------------------------------------------------

    def _solve_poisson(
        self,
        charge: np.ndarray,
        nz: int,
        nr: int,
        hz: float,
        hr: float,
    ) -> np.ndarray:
        """Solve the axisymmetric Poisson equation ∇²φ = -ρ/ε₀.

        Uses a Gauss-Seidel (successive over-relaxation) iterative
        solver with Dirichlet boundary conditions (φ = 0 on the outer
        radial boundary and at the z boundaries).

        The discrete Laplacian in axisymmetric cylindrical coordinates:

        .. math::

            \\frac{\\partial^2\\phi}{\\partial z^2}
            + \\frac{1}{r}\\frac{\\partial}{\\partial r}
            \\left(r\\frac{\\partial\\phi}{\\partial r}\\right)
            = -\\frac{\\rho}{\\varepsilon_0}
        """
        from pyecho.mathlib import eps0

        phi: np.ndarray = np.zeros((nz, nr), dtype=np.float64)
        omega = 1.8  # SOR relaxation parameter

        # Precompute r coordinates at cell centres
        r_vals = (np.arange(nr, dtype=np.float64) + 0.5) * hr
        # Avoid division by zero at r=0
        r_vals[0] = 0.5 * hr

        max_iter = 50000
        tol = 1e-10

        inv_eps0 = 1.0 / eps0

        for iteration in range(max_iter):
            phi_old = phi.copy()

            for i in range(1, nz - 1):
                for j in range(1, nr - 1):
                    # d²φ/dz²
                    d2z = (phi[i + 1, j] - 2.0 * phi[i, j] + phi[i - 1, j]) / (hz * hz)

                    # (1/r) d/dr (r dφ/dr)
                    r = r_vals[j]
                    rp = r_vals[j] + 0.5 * hr
                    rm = r_vals[j] - 0.5 * hr
                    if rm < 0:
                        rm = 0.0

                    d2r = (
                        rp * (phi[i, j + 1] - phi[i, j])
                        - rm * (phi[i, j] - phi[i, j - 1])
                    ) / (r * hr * hr)

                    # Source term
                    src = -charge[i, j] * inv_eps0

                    # SOR update
                    phi_new = (
                        (d2z + d2r - src) * (hz * hz * hr * hr)
                        / (2.0 * (hz * hz + hr * hr))
                        + phi[i, j]
                    )
                    phi[i, j] = (1.0 - omega) * phi[i, j] + omega * phi_new

            # Check convergence
            diff: float = np.max(np.abs(phi - phi_old))
            if diff < tol:
                logger.info("Poisson solver converged in %d iterations", iteration + 1)
                break
        else:
            logger.warning(
                "Poisson solver did not converge after %d iterations (max diff=%.3e)",
                max_iter, diff,
            )

        return phi

    # ------------------------------------------------------------------
    # Internal: electric field from potential
    # ------------------------------------------------------------------

    def _compute_efield(
        self,
        phi: np.ndarray,
        nz: int,
        nr: int,
        hz: float,
        hr: float,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Compute electric field E = -∇φ from the potential.

        Uses central finite differences in the interior and one-sided
        differences at the boundaries.

        Returns
        -------
        Ez : np.ndarray
            Longitudinal electric field (nz, nr).
        Er : np.ndarray
            Radial electric field (nz, nr).
        """
        Ez = np.zeros_like(phi)
        Er = np.zeros_like(phi)

        # Interior: central differences
        Ez[1:-1, :] = -(phi[2:, :] - phi[:-2, :]) / (2.0 * hz)
        Er[:, 1:-1] = -(phi[:, 2:] - phi[:, :-2]) / (2.0 * hr)

        # Boundaries: one-sided differences
        Ez[0, :] = -(phi[1, :] - phi[0, :]) / hz
        Ez[-1, :] = -(phi[-1, :] - phi[-2, :]) / hz

        Er[:, 0] = -(phi[:, 1] - phi[:, 0]) / hr
        Er[:, -1] = -(phi[:, -1] - phi[:, -2]) / hr

        return Ez, Er
