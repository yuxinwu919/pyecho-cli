"""High-level post-processing dispatcher.

Provides the :class:`PostProcessor` class that auto-detects the
geometry type (round vs flat) from the ECHO2D output directory
structure and applies the correct processing pipeline.

Usage::

    >>> from pyecho.postprocess import PostProcessor
    >>> pp = PostProcessor("path/to/output_dir")
    >>> wake = pp.process_wake_monopole()
    >>> print(f"Loss factor: {wake.loss_factor:.4f} V/pC")

    >>> # Flat geometry
    >>> pp2 = PostProcessor("path/to/flat_output")
    >>> result = pp2.process_all()
    >>> print(f"Wlong peak: {result['Wlong'].max():.2f} V/pC")
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from pyecho.errors import MissingOutputError, PostProcessError

if TYPE_CHECKING:
    from pyecho.datamodel import WakeResult, FlatWakeResult, SimulationResult
    from pyecho.parser import OutputLoader

logger = logging.getLogger(__name__)


class PostProcessor:
    """ECHO2D post-processor with automatic geometry detection.

    Analyses the output directory structure to determine whether the
    simulation used round (axisymmetric) or flat (rectangular) geometry,
    then dispatches to the appropriate wake processing sub-module.

    Parameters
    ----------
    loader_or_dir : OutputLoader or str or Path
        Either an :class:`OutputLoader` instance already pointing at
        the output directory, or a path (string or ``Path``) to the
        ECHO2D output directory (the parent of the ``round/``,
        ``magn/``, or ``elec/`` subdirectory).

    Attributes
    ----------
    loader : OutputLoader
        The underlying output file loader.
    geometry_type : str
        Detected geometry type: ``"round"``, ``"flat"`` (magn+elec),
        ``"magn"``, ``"elec"``, or ``"unknown"``.

    Examples
    --------
    >>> pp = PostProcessor("my_sim_output/")
    >>> if pp.geometry_type == "round":
    ...     wake = pp.process_wake_monopole()
    ...     dipole = pp.process_wake_dipole()
    ... else:
    ...     result = pp.process_all()
    """

    def __init__(
        self,
        loader_or_dir: "OutputLoader | str | Path",
    ) -> None:
        from pyecho.parser import OutputLoader

        if isinstance(loader_or_dir, OutputLoader):
            self.loader = loader_or_dir
        else:
            self.loader = OutputLoader(Path(loader_or_dir))

        self._effective_type: str = "unknown"
        self._has_magn: bool = False
        self._has_elec: bool = False
        self._magn_dir: Path | None = None
        self._elec_dir: Path | None = None
        self._detect_geometry()

    # ------------------------------------------------------------------
    # Geometry detection
    # ------------------------------------------------------------------

    def _detect_geometry(self) -> None:
        """Determine the effective geometry type and available subdirectories."""
        gt = self.loader.geometry_type

        # Check for magn/ and elec/ subdirectories with exact or prefix match
        magn_dir = None
        elec_dir = None
        for child in sorted(self.loader.dir.iterdir()):
            if not child.is_dir():
                continue
            name = child.name.lower()
            if (name == "magn" or name.startswith("magn")) and list(
                child.glob("wakeL_*.txt")
            ):
                magn_dir = child
            if (name == "elec" or name.startswith("elec")) and list(
                child.glob("wakeL_*.txt")
            ):
                elec_dir = child

        has_magn = magn_dir is not None
        has_elec = elec_dir is not None

        if has_magn or has_elec:
            self._effective_type = "recta"
        elif gt in ("round",):
            self._effective_type = "round"
        elif gt in ("magn", "elec"):
            # Loader found magn/elec subdirectory directly; treat as recta
            self._effective_type = "recta"
        else:
            # Try to infer from wakeL file presence
            data_dir = self.loader._resolve_data_dir()
            if list(data_dir.glob("wakeL_00.txt")):
                self._effective_type = "round"
            elif list(data_dir.glob("wakeL_01.txt")):
                # Could be either; check if Wcc exists or magn/elec dirs nearby
                if list(data_dir.glob("Wcc_odd.txt")) or has_magn or has_elec:
                    self._effective_type = "recta"
                else:
                    self._effective_type = "round"
            else:
                self._effective_type = "unknown"

        self._has_magn = has_magn
        self._has_elec = has_elec
        self._magn_dir = magn_dir
        self._elec_dir = elec_dir

    @property
    def geometry_type(self) -> str:
        """Effective geometry type used for processing."""
        return self._effective_type

    # ------------------------------------------------------------------
    # Round geometry processing
    # ------------------------------------------------------------------

    def process_wake_monopole(
        self,
        mode: int = 0,
        shift_sigma: bool = True,
    ) -> "WakeResult":
        """Process monopole (m=0) longitudinal wake.

        Only valid for round (axisymmetric) geometry.

        Parameters
        ----------
        mode : int
            Azimuthal mode number (0 for monopole).
        shift_sigma : bool
            If ``True``, shift the *s*-coordinate to centre the bunch.

        Returns
        -------
        WakeResult
            Processed wake with loss factor, RMS spread, and peak.

        Raises
        ------
        PostProcessError
            If the geometry is not round or wake file is missing.
        """
        if self._effective_type not in ("round",):
            raise PostProcessError(
                f"process_wake_monopole requires round geometry, "
                f"but detected type is '{self._effective_type}'."
            )

        from pyecho.postprocess.wakes.round import process_wake_monopole

        logger.info("Processing round monopole wake (m=%d)...", mode)
        return process_wake_monopole(self.loader, shift_sigma=shift_sigma)

    def process_wake_dipole(
        self,
        mode: int = 1,
    ) -> dict:
        """Process dipole (m=1) wake, including transverse component.

        Only valid for round (axisymmetric) geometry.

        Parameters
        ----------
        mode : int
            Azimuthal mode number (1 for dipole).

        Returns
        -------
        dict
            Keys: ``longitudinal`` (:class:`WakeResult`),
            ``transverse`` (:class:`WakeResult`), ``dy``, ``sigma``.

        Raises
        ------
        PostProcessError
            If the geometry is not round or wake file is missing.
        """
        if self._effective_type not in ("round",):
            raise PostProcessError(
                f"process_wake_dipole requires round geometry, "
                f"but detected type is '{self._effective_type}'."
            )

        from pyecho.postprocess.wakes.round import process_wake_dipole

        logger.info("Processing round dipole wake (m=%d)...", mode)
        return process_wake_dipole(self.loader)

    # ------------------------------------------------------------------
    # Flat geometry processing
    # ------------------------------------------------------------------

    def process_flat_wake(
        self,
        n_modes_cc: int = 0,
        n_modes_ss: int = 0,
    ) -> dict:
        """Process recta geometry wakes (Wlong, Wquad, Wdipole).

        Auto-detects the magn/ and elec/ subdirectories and the number
        of available odd modes.

        Parameters
        ----------
        n_modes_cc : int
            Number of cos-cos (magnetic) odd modes.  If ≤ 0, auto-detect
            from available ``wakeL_*.txt`` files.
        n_modes_ss : int
            Number of sin-sin (electric) odd modes.  If ≤ 0, auto-detect.

        Returns
        -------
        dict
            Keys: ``wcc``, ``wss``, ``s``, ``Wlong``, ``Wquad``,
            ``Wdipole``, ``D``, ``k_cc``, ``k_ss``.
            See :func:`pyecho.postprocess.wakes.flat.process_flat_wake`.

        Raises
        ------
        PostProcessError
            If no flat geometry data is found.
        """
        if self._effective_type not in ("recta",):
            raise PostProcessError(
                f"process_flat_wake requires recta geometry, "
                f"but detected type is '{self._effective_type}'."
            )

        from pyecho.postprocess.wakes.flat import (
            process_flat_wake,
            assemble_wcc,
            assemble_wss,
            compute_wake_long_quad,
            compute_wake_long_quad_dipole,
        )

        # --- Resolve magn/ directory -------------------------------------------
        magn_dir = self._magn_dir if self._magn_dir else self.loader.dir / "magn"
        if not magn_dir.is_dir():
            fallback = self.loader._resolve_data_dir()
            if fallback.name.lower() not in ("elec",):
                magn_dir = fallback
            else:
                # The data dir is elec/ — do NOT use it as magn (wrong norm).
                magn_dir = None

        # --- Resolve elec/ directory -------------------------------------------
        elec_dir = self._elec_dir if self._elec_dir else self.loader.dir / "elec"
        if not elec_dir.is_dir():
            # If the loader's data dir itself is elec/, use it directly.
            fallback = self.loader._resolve_data_dir()
            if fallback.name.lower() in ("elec",):
                elec_dir = fallback
            else:
                elec_dir = None

        # --- Neither available → error ----------------------------------------
        if magn_dir is None and elec_dir is None:
            raise MissingOutputError(
                "No magn/ or elec/ directory found. "
                "Recta geometry requires at least one symmetry condition output.",
                data_dir=self.loader.dir,
                missing_files=["magn/", "elec/"],
            )

        # --- Auto-detect n_modes -----------------------------------------------
        if n_modes_cc <= 0 and magn_dir is not None:
            n_modes_cc = self._count_odd_modes(magn_dir)
        if n_modes_ss <= 0 and elec_dir is not None:
            n_modes_ss = self._count_odd_modes(elec_dir)

        # --- Warnings for partial data -----------------------------------------
        if magn_dir is None:
            logger.warning(
                "No magn/ directory found — longitudinal and quadrupole wake "
                "will be zero. Run with SymmetryCondition=magn."
            )
        if elec_dir is None:
            logger.warning(
                "No elec/ directory found — dipole wake will be zero. "
                "Run with SymmetryCondition=elec."
            )

        # --- Dispatch ----------------------------------------------------------
        if magn_dir is not None and elec_dir is not None:
            # Full pipeline: both Wcc (magn) and Wss (elec)
            logger.info(
                "Processing flat wakes: magn=%s, elec=%s, "
                "n_modes_cc=%d, n_modes_ss=%d",
                magn_dir, elec_dir, n_modes_cc, n_modes_ss,
            )
            return process_flat_wake(
                magn_dir=magn_dir,
                elec_dir=elec_dir,
                n_modes_cc=n_modes_cc,
                n_modes_ss=n_modes_ss,
            )
        elif magn_dir is not None:
            # magn-only: Wlong + Wquad, zero Wdipole
            logger.info(
                "Processing flat wakes (magn-only): %s, n_modes=%d",
                magn_dir, n_modes_cc,
            )
            return self._partial_magn_only(magn_dir, n_modes_cc)
        else:
            # elec-only: Wdipole, zero Wlong/Wquad
            logger.info(
                "Processing flat wakes (elec-only): %s, n_modes=%d",
                elec_dir, n_modes_ss,
            )
            return self._partial_elec_only(elec_dir, n_modes_ss)

    def _partial_magn_only(self, magn_dir: Path, n_modes: int) -> dict:
        """Compute Wlong and Wquad from magn data only; Wdipole = 0."""
        import numpy as np
        from pyecho.postprocess.wakes.flat import (
            assemble_wcc, compute_wake_long_quad,
        )

        wcc = assemble_wcc(magn_dir, n_modes=n_modes)
        result = compute_wake_long_quad(wcc, n_modes=n_modes)
        result["wcc"] = wcc
        result["wss"] = None
        result["Wdipole"] = np.zeros_like(result["Wlong"])
        return result

    def _partial_elec_only(self, elec_dir: Path, n_modes: int) -> dict:
        """Compute Wdipole from elec data only; Wlong = Wquad = 0."""
        import numpy as np
        from pyecho.postprocess.wakes.flat import assemble_wss
        from pyecho.mathlib.integration import integr_tr

        wss = assemble_wss(elec_dir, n_modes=n_modes)
        s = wss[0, 1:].astype(np.float64)
        D = float(wss[0, 0])
        hs = float(s[1] - s[0])

        # Replicate compute_wake_long_quad_dipole Wdipole formula:
        #   Wdipole = -IntegrTr(hs, Σ k²·Wss) * 2/D * 1e-6  [V/pC/mm]
        k_sq = wss[1:, 0] ** 2
        WD_sum = np.sum(k_sq[:, None] * wss[1:, 1:], axis=0)
        Wdipole = -integr_tr(hs, WD_sum) * (2.0 / D) * 1e-6

        result = {
            "wcc": None,
            "wss": wss,
            "s": s,
            "Wlong": np.zeros_like(s),
            "Wquad": np.zeros_like(s),
            "Wdipole": Wdipole,
            "D": D,
        }
        return result

    @staticmethod
    def _count_odd_modes(data_dir: Path) -> int:
        """Count available odd-mode wakeL files in a directory.

        Scans for ``wakeL_01.txt``, ``wakeL_03.txt``, … and returns
        the number of consecutive odd modes found starting from 1.

        Parameters
        ----------
        data_dir : Path
            Directory to scan.

        Returns
        -------
        int
            Number of consecutive odd modes (minimum 1).
        """
        count = 0
        for m in range(1, 1000, 2):  # odd: 1, 3, 5, ...
            if (data_dir / f"wakeL_{m:02d}.txt").exists():
                count += 1
            else:
                break
        return max(count, 1)

    def process_off_axis(
        self,
        y0: float,
        y: float,
        n_modes_cc: int | None = None,
        n_modes_ss: int | None = None,
    ) -> dict:
        """Compute off-axis wake at arbitrary transverse offsets.

        Requires both magn/ and elec/ directories with wake data.
        Replicates MATLAB ``PP_WakeZY.m``.

        Parameters
        ----------
        y0 : float
            Source transverse offset [m].
        y : float
            Witness transverse offset [m].
        n_modes_cc : int, optional
            Number of cos-cos modes.  Defaults to all available.
        n_modes_ss : int, optional
            Number of sin-sin modes.  Defaults to all available.

        Returns
        -------
        dict
            Keys: ``s`` [m], ``Wz`` [V/pC], ``Wy`` [V/pC], ``D`` [m].

        Raises
        ------
        PostProcessError
            If both magn/ and elec/ data are not found.
        """
        if self._effective_type not in ("recta",):
            raise PostProcessError(
                "process_off_axis requires recta geometry (magn+elec)."
            )

        magn_dir = self._magn_dir or self.loader.dir / "magn"
        elec_dir = self._elec_dir or self.loader.dir / "elec"

        if not magn_dir.is_dir():
            magn_dir = self.loader._resolve_data_dir()
        if not elec_dir.is_dir():
            raise MissingOutputError(
                "process_off_axis requires elec/ directory with wakeL files.",
                data_dir=self.loader.dir,
                missing_files=["elec/"],
            )

        from pyecho.postprocess.wakes.flat import (
            assemble_wcc, assemble_wss, compute_wake_off_axis,
        )

        wcc = assemble_wcc(magn_dir, n_modes=n_modes_cc or 15)
        wss = assemble_wss(elec_dir, n_modes=n_modes_ss or 15)
        return compute_wake_off_axis(wcc, wss, y0, y, n_modes_cc, n_modes_ss)

    # ------------------------------------------------------------------
    # Field monitors
    # ------------------------------------------------------------------

    def process_field_monitor(
        self,
        mode: int = 0,
        monitor_id: int = 1,
        point_t: float | None = None,
        point_z: float | None = None,
        point_r: float | None = None,
    ) -> dict:
        """Extract field trace from a field monitor.

        Parameters
        ----------
        mode : int
            Mode number (mXX in filename).
        monitor_id : int
            Monitor index (NYY in filename).
        point_t : float, optional
            Fixed time (or *s*) coordinate.
        point_z : float, optional
            Fixed longitudinal coordinate.
        point_r : float, optional
            Fixed transverse coordinate.

        Returns
        -------
        dict
            See :func:`pyecho.postprocess.fields.process_field_monitor`.
        """
        monitor = self.loader.load_monitor(mode=mode, monitor_id=monitor_id)
        if monitor is None:
            raise MissingOutputError(
                f"Monitor m{mode}_N{monitor_id} not found.",
                data_dir=self.loader.dir,
            )

        from pyecho.postprocess.fields import process_field_monitor

        return process_field_monitor(
            monitor,
            point_t=point_t,
            point_z=point_z,
            point_r=point_r,
        )

    def synthesize_total_field(
        self,
        component: str = "Ez",
        monitor_id: int = 1,
        x0: float = 0.0,
        x: float = 0.0,
        n_modes: int = 35,
    ) -> np.ndarray:
        """Synthesise total field from modal monitor files.

        Only valid for flat geometry (requires magn/ directory with
        ``Monitor_mXX_NYY.txt`` files).

        Parameters
        ----------
        component : str
            Field component (``"Ez"``, ``"Ey"``, ``"Hx"``, etc.).
        monitor_id : int
            Monitor index.
        x0 : float
            Source transverse offset [m].
        x : float
            Observation transverse position [m].
        n_modes : int
            Number of odd modes.

        Returns
        -------
        np.ndarray
            Synthesised total field array.
        """
        magn_dir = self._magn_dir if self._magn_dir else self.loader.dir / "magn"
        if not magn_dir.is_dir():
            magn_dir = self.loader._resolve_data_dir()

        from pyecho.postprocess.fields import synthesize_total_field_from_loader

        return synthesize_total_field_from_loader(
            magn_dir=magn_dir,
            component=component,
            monitor_id=monitor_id,
            x0=x0,
            x=x,
            n_modes=n_modes,
        )

    # ------------------------------------------------------------------
    # Particles
    # ------------------------------------------------------------------

    def load_particles(self) -> dict:
        """Load and analyse ``particles.out``.

        Returns
        -------
        dict
            See :func:`pyecho.postprocess.particles.load_echo_particles`.
        """
        from pyecho.postprocess.particles import (
            load_echo_particles,
            compute_particle_statistics,
        )

        data_dir = self.loader._resolve_data_dir()
        filepath = data_dir / "particles.out"
        if not filepath.exists():
            raise MissingOutputError(
                f"particles.out not found in {data_dir}",
                data_dir=data_dir,
                missing_files=["particles.out"],
            )

        particles = load_echo_particles(filepath)
        stats = compute_particle_statistics(particles)
        return {"particles": particles, "statistics": stats}

    def convert_to_astra(
        self,
        astra_file: str | Path,
        total_charge: float | None = None,
        reference_energy_MeV: float = 100.0,
    ) -> int:
        """Convert ECHO particles to ASTRA format.

        Parameters
        ----------
        astra_file : str or Path
            Output ASTRA file path.
        total_charge : float, optional
            Total bunch charge [C].
        reference_energy_MeV : float
            Reference beam energy [MeV].

        Returns
        -------
        int
            Number of particles converted.
        """
        from pyecho.postprocess.particles import convert_echo_to_astra

        data_dir = self.loader._resolve_data_dir()
        echo_file = data_dir / "particles.out"
        if not echo_file.exists():
            raise MissingOutputError(
                f"particles.out not found in {data_dir}",
                data_dir=data_dir,
                missing_files=["particles.out"],
            )

        return convert_echo_to_astra(
            echo_file=echo_file,
            astra_file=astra_file,
            total_charge=total_charge,
            reference_energy_MeV=reference_energy_MeV,
        )

    # ------------------------------------------------------------------
    # Run all
    # ------------------------------------------------------------------

    def process_all(self) -> dict[str, Any]:
        """Run all applicable post-processing steps.

        Auto-detects geometry type and runs the appropriate pipeline:
        - Round: monopole + dipole wakes
        - Flat: Wcc + Wss assembly, Wlong/Wquad/Wdipole computation

        Returns
        -------
        dict
            A dictionary with all processed results.  Keys depend on
            the geometry type.

        Raises
        ------
        MissingOutputError
            If no ECHO2D output data is found.
        """
        if not self.loader.has_output():
            raise MissingOutputError(
                f"No ECHO2D output files found in {self.loader.dir}",
                data_dir=self.loader.dir,
            )

        results: dict[str, Any] = {
            "geometry_type": self._effective_type,
            "output_dir": str(self.loader.dir),
        }

        if self._effective_type == "round":
            logger.info("Running full round-geometry post-processing...")
            try:
                results["monopole"] = self.process_wake_monopole()
            except Exception as exc:
                logger.warning("Monopole processing failed: %s", exc)
                results["monopole"] = None

            try:
                results["dipole"] = self.process_wake_dipole()
            except Exception as exc:
                logger.warning("Dipole processing failed: %s", exc)
                results["dipole"] = None

        elif self._effective_type == "recta":
            logger.info("Running full recta-geometry post-processing...")
            results["recta_wake"] = self.process_flat_wake()

            # Try field synthesis if monitors exist
            monitors = self.loader.list_monitors()
            if monitors:
                logger.info("Found %d monitor files; synthesising total field...",
                            len(monitors))
                try:
                    results["total_field"] = self.synthesize_total_field()
                except Exception as exc:
                    logger.warning("Field synthesis failed: %s", exc)

        else:
            logger.warning(
                "Unknown geometry type '%s'; attempting round processing.",
                self._effective_type,
            )
            try:
                results["monopole"] = self.process_wake_monopole()
            except Exception:
                pass
            try:
                results["dipole"] = self.process_wake_dipole()
            except Exception:
                pass

        # Try particle processing if available
        data_dir = self.loader._resolve_data_dir()
        if (data_dir / "particles.out").exists():
            try:
                results["particles"] = self.load_particles()
            except Exception as exc:
                logger.warning("Particle processing failed: %s", exc)

        return results
