"""Geometry builder and parser for ECHO2D.

ECHO2D uses a simple ASCII geometry format to describe rotationally
symmetric (round) and rectangular (flat) structures.  This module
provides programmatic builders and a file parser.

Geometry File Format
--------------------
The ECHO2D geometry file (``.txt``) has the following structure::

    % Number of materials
    <N_materials>
    % Number of elements in material <i> with conductive walls, permittivity, mu, conductivity
    <N_segments> <epsilon> <mu> <sigma>
    % Segments of lines and ellipses with conductivity
    <type> <region> <z1_segment> <z2_segment> ... (10 columns)

See the ECHO manual for the full specification.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from pyecho.errors import GeometryError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API — geometry builders
# ---------------------------------------------------------------------------

class RoundGeometry:
    """Build a rotationally symmetric (round) ECHO2D geometry.

    Coordinates are specified in **centimeters** (the ECHO2D convention
    for geometry files).  The builder accumulates pipe and step
    segments and writes a valid ``.txt`` geometry file.

    Usage::

        >>> geo = RoundGeometry()
        >>> geo.pipe(radius=1.0, length=10.0)  # 1 cm radius, 10 cm long
        >>> geo.step(radius=2.0, length=5.0)    # expand to 2 cm
        >>> geo.save("my_geometry.txt")
    """

    # Orientation constants (ECHO2D manual section 4.3.1)
    CLOCKWISE = 0
    COUNTERCLOCKWISE = 1

    def __init__(self) -> None:
        self.segments: list[dict[str, Any]] = []
        self.materials: list[dict[str, Any]] = [
            {"epsilon": 1, "mu": 1, "sigma": 0, "segments": []}
        ]
        self._current_z: float = 0.0
        self._current_radius: float = 0.0

    def pipe(
        self,
        radius: float,
        length: float,
        z_start: float | None = None,
    ) -> RoundGeometry:
        """Add a straight pipe section.

        Parameters
        ----------
        radius : float
            Pipe radius in cm.
        length : float
            Pipe length in cm.
        z_start : float, optional
            Starting z-coordinate in cm.  If ``None``, continues from
            the previous segment's end.

        Returns
        -------
        RoundGeometry
            Self for method chaining.
        """
        if z_start is None:
            z_start = self._current_z

        z_end = z_start + length
        self.segments.append({
            "z1": z_start,
            "r1": radius,
            "z2": z_end,
            "r2": radius,
            "d": self.COUNTERCLOCKWISE,
            "k": 0.0,
        })
        self.materials[0]["segments"].append(len(self.segments) - 1)
        self._current_z = z_end
        self._current_radius = radius
        return self

    def step(
        self,
        radius: float,
        length: float,
    ) -> RoundGeometry:
        """Add a radial step (connects from previous segment's end).

        Parameters
        ----------
        radius : float
            New radius in cm (after step).
        length : float
            Length of the stepped section in cm.

        Returns
        -------
        RoundGeometry
            Self for method chaining.
        """
        z_start = self._current_z
        z_end = z_start + length

        # If radius changes, we need a vertical segment first,
        # then a horizontal segment.
        if abs(radius - self._current_radius) > 1e-12:
            # Vertical wall (at constant z = z_start)
            self.segments.append({
                "z1": z_start,
                "r1": self._current_radius,
                "z2": z_start,
                "r2": radius,
                "d": self.COUNTERCLOCKWISE,
                "k": 0.0,
            })
            self.materials[0]["segments"].append(len(self.segments) - 1)
            self._current_radius = radius

        # Horizontal pipe
        self.segments.append({
            "z1": z_start,
            "r1": radius,
            "z2": z_end,
            "r2": radius,
            "d": self.COUNTERCLOCKWISE,
            "k": 0.0,
        })
        self.materials[0]["segments"].append(len(self.segments) - 1)
        self._current_z = z_end
        return self

    def taper(
        self,
        r_start: float,
        r_end: float,
        length: float,
    ) -> RoundGeometry:
        """Add a linearly tapered section.

        Parameters
        ----------
        r_start : float
            Starting radius in cm.
        r_end : float
            Ending radius in cm.
        length : float
            Taper length in cm.

        Returns
        -------
        RoundGeometry
            Self for method chaining.
        """
        z_start = self._current_z
        z_end = z_start + length

        self.segments.append({
            "z1": z_start,
            "r1": r_start,
            "z2": z_end,
            "r2": r_end,
            "d": self.COUNTERCLOCKWISE,
            "k": 0.0,
        })
        self.materials[0]["segments"].append(len(self.segments) - 1)
        self._current_z = z_end
        self._current_radius = r_end
        return self

    def save(self, filepath: str | Path) -> None:
        """Write the geometry to an ECHO2D ``.txt`` file.

        Parameters
        ----------
        filepath : str or Path
            Destination file path.

        Raises
        ------
        GeometryError
            If no segments have been added.
        """
        if not self.segments:
            raise GeometryError("Cannot save empty geometry (no segments).")

        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        lines: list[str] = []
        lines.append("% Number of materials")
        lines.append(f"{len(self.materials)}")

        for mat in self.materials:
            seg_indices = mat.get("segments", [])
            n_seg = len(seg_indices)
            eps = mat.get("epsilon", 1)
            mu = mat.get("mu", 1)
            sigma = mat.get("sigma", 0)
            lines.append(
                "% Number of elements in material with conductive walls, "
                "permittivity, mu, conductivity"
            )
            lines.append(f"{n_seg} {eps} {mu} {sigma}")

            lines.append("% Segments of lines and elipses with conductivity")
            for idx in seg_indices:
                seg = self.segments[idx]
                # ECHO2D 10-column segment format (manual section 4.3.1):
                # z1 r1 z2 r2 z3 r3 z4 r4 d k
                # - (z1,r1): start point, (z2,r2): end point
                # - (z3,r3,z4,r4): ellipse bounding box (0,0,0,0 for lines)
                # - d: orientation (0=clockwise, 1=counterclockwise)
                # - k: wall conductivity [S/m] (only for first material)
                line_str = (
                    f"{seg['z1']}\t{seg['r1']}\t"
                    f"{seg['z2']}\t{seg['r2']}\t"
                    f"0\t0\t0\t0\t"
                    f"{seg['d']}\t{seg['k']}"
                )
                lines.append(line_str)

        filepath.write_text("\n".join(lines) + "\n", encoding="utf-8")
        logger.info("Geometry saved to %s (%d segments)", filepath, len(self.segments))


class RectaGeometry:
    """Build a rectangular (flat) ECHO2D geometry.

    Similar API to :class:`RoundGeometry` but uses *y* (vertical)
    coordinate instead of *r* (radial).  Coordinates are in cm.

    Usage::

        >>> geo = RectaGeometry()
        >>> geo.pipe(half_gap=0.5, length=10.0)
        >>> geo.save("flat_geometry.txt")
    """

    # Orientation constants (ECHO2D manual section 4.3.1)
    CLOCKWISE = 0
    COUNTERCLOCKWISE = 1

    def __init__(self) -> None:
        self.segments: list[dict[str, Any]] = []
        self.materials: list[dict[str, Any]] = [
            {"epsilon": 1, "mu": 1, "sigma": 0, "segments": []}
        ]
        self._current_z: float = 0.0
        self._current_y: float = 0.0

    def pipe(
        self,
        half_gap: float,
        length: float,
        z_start: float | None = None,
    ) -> RectaGeometry:
        """Add a straight rectangular pipe section.

        Parameters
        ----------
        half_gap : float
            Half-gap (y-coordinate of the top wall) in cm.
        length : float
            Pipe length in cm.
        z_start : float, optional
            Starting z in cm.

        Returns
        -------
        RectaGeometry
            Self for method chaining.
        """
        if z_start is None:
            z_start = self._current_z

        z_end = z_start + length
        self.segments.append({
            "z1": z_start,
            "y1": half_gap,
            "z2": z_end,
            "y2": half_gap,
            "d": self.COUNTERCLOCKWISE,
            "k": 0.0,
        })
        self.materials[0]["segments"].append(len(self.segments) - 1)
        self._current_z = z_end
        self._current_y = half_gap
        return self

    def step(
        self,
        half_gap: float,
        length: float,
    ) -> RectaGeometry:
        """Add a vertical step in the rectangular geometry.

        Parameters
        ----------
        half_gap : float
            New half-gap in cm.
        length : float
            Length of the stepped section in cm.

        Returns
        -------
        RectaGeometry
            Self for method chaining.
        """
        z_start = self._current_z
        z_end = z_start + length

        if abs(half_gap - self._current_y) > 1e-12:
            self.segments.append({
                "z1": z_start,
                "y1": self._current_y,
                "z2": z_start,
                "y2": half_gap,
                "d": self.COUNTERCLOCKWISE,
                "k": 0.0,
            })
            self.materials[0]["segments"].append(len(self.segments) - 1)
            self._current_y = half_gap

        self.segments.append({
            "z1": z_start,
            "y1": half_gap,
            "z2": z_end,
            "y2": half_gap,
            "d": self.COUNTERCLOCKWISE,
            "k": 0.0,
        })
        self.materials[0]["segments"].append(len(self.segments) - 1)
        self._current_z = z_end
        return self

    def taper(
        self,
        y_start: float,
        y_end: float,
        length: float,
    ) -> RectaGeometry:
        """Add a linearly tapered section.

        Parameters
        ----------
        y_start : float
            Starting half-gap in cm.
        y_end : float
            Ending half-gap in cm.
        length : float
            Taper length in cm.

        Returns
        -------
        RectaGeometry
            Self for method chaining.
        """
        z_start = self._current_z
        z_end = z_start + length

        self.segments.append({
            "z1": z_start,
            "y1": y_start,
            "z2": z_end,
            "y2": y_end,
            "d": self.COUNTERCLOCKWISE,
            "k": 0.0,
        })
        self.materials[0]["segments"].append(len(self.segments) - 1)
        self._current_z = z_end
        self._current_y = y_end
        return self

    def save(self, filepath: str | Path) -> None:
        """Write the geometry to an ECHO2D ``.txt`` file.

        Parameters
        ----------
        filepath : str or Path
            Destination file path.
        """
        if not self.segments:
            raise GeometryError("Cannot save empty flat geometry (no segments).")

        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        lines: list[str] = []
        lines.append("% Number of materials")
        lines.append(f"{len(self.materials)}")

        for mat in self.materials:
            seg_indices = mat.get("segments", [])
            n_seg = len(seg_indices)
            eps = mat.get("epsilon", 1)
            mu = mat.get("mu", 1)
            sigma = mat.get("sigma", 0)
            lines.append(
                "% Number of elements in material with conductive walls, "
                "permittivity, mu, conductivity"
            )
            lines.append(f"{n_seg} {eps} {mu} {sigma}")

            lines.append("% Segments of lines and ellipses with conductivity")
            for idx in seg_indices:
                seg = self.segments[idx]
                # ECHO2D 10-column segment format (manual section 4.3.1):
                # z1 y1 z2 y2 z3 y3 z4 y4 d k
                # (flat geometry uses y instead of r)
                line_str = (
                    f"{seg['z1']}\t{seg['y1']}\t"
                    f"{seg['z2']}\t{seg['y2']}\t"
                    f"0\t0\t0\t0\t"
                    f"{seg['d']}\t{seg['k']}"
                )
                lines.append(line_str)

        filepath.write_text("\n".join(lines) + "\n", encoding="utf-8")
        logger.info(
            "Flat geometry saved to %s (%d segments)", filepath, len(self.segments)
        )


# ---------------------------------------------------------------------------
# Public API — geometry file parser
# ---------------------------------------------------------------------------

def load_geometry(filepath: str | Path) -> dict:
    """Parse an ECHO2D geometry ``.txt`` file.

    The ECHO2D geometry file uses exactly 10 tab-separated columns per
    segment line (manual section 4.3.1)::

        z1  r1  z2  r2  z3  r3  z4  r4  d  k

    where:
    - (z1, r1) = start point coordinates [cm]
    - (z2, r2) = end point coordinates [cm]
    - (z3, r3), (z4, r4) = ellipse bounding box corners (0 for lines)
    - d = orientation (0 = clockwise, 1 = counterclockwise)
    - k = wall conductivity [S/m] (non-zero only for first material)

    For flat (rectangular) geometry, replace r → y.

    Parameters
    ----------
    filepath : str or Path
        Path to the geometry file.

    Returns
    -------
    dict
        Keys:
        - ``materials``: list of material dicts with ``epsilon``, ``mu``,
          ``sigma``, ``segments``.
        - ``segments``: list of segment dicts with ``z1``, ``r1``, ``z2``,
          ``r2``, ``z3``, ``r3``, ``z4``, ``r4``, ``d``, ``k``.

    Raises
    ------
    GeometryError
        If the file cannot be parsed.
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise GeometryError(f"Geometry file not found: {filepath}")

    try:
        lines = filepath.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise GeometryError(f"Cannot read geometry file {filepath}: {exc}") from exc

    # Filter out % header lines (separators, not comments) and empty lines
    data_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("%"):
            continue
        data_lines.append(stripped)

    if not data_lines:
        raise GeometryError(f"Empty geometry file: {filepath}")

    result: dict[str, Any] = {"materials": [], "segments": []}
    idx = 0

    try:
        n_materials = int(data_lines[idx].split()[0])
        idx += 1
    except (IndexError, ValueError) as exc:
        raise GeometryError(
            f"Invalid number of materials in {filepath}"
        ) from exc

    global_seg_idx = 0
    for _ in range(n_materials):
        if idx >= len(data_lines):
            raise GeometryError(
                f"Truncated geometry file {filepath}: "
                f"expected material data at line {idx + 1}"
            )

        # Line: N_segments epsilon mu sigma
        # (header text varies but numeric column order is always the same)
        parts = data_lines[idx].split()
        if len(parts) < 4:
            raise GeometryError(
                f"Invalid material header at line {idx + 1} in {filepath}"
            )
        n_seg = int(parts[0])
        eps = float(parts[1])
        mu = float(parts[2])
        sigma = float(parts[3])
        idx += 1

        mat_segments: list[int] = []
        for _ in range(n_seg):
            if idx >= len(data_lines):
                raise GeometryError(
                    f"Truncated geometry: expected segment at line {idx + 1}"
                )
            parts = data_lines[idx].split()
            if len(parts) < 10:
                raise GeometryError(
                    f"Invalid segment at line {idx + 1}: "
                    f"need 10 columns, got {len(parts)}"
                )
            # ECHO2D 10-column format (manual section 4.3.1):
            # z1 r1 z2 r2 z3 r3 z4 r4 d k
            seg = {
                "z1": float(parts[0]),
                "r1": float(parts[1]),
                "z2": float(parts[2]),
                "r2": float(parts[3]),
                "z3": float(parts[4]),
                "r3": float(parts[5]),
                "z4": float(parts[6]),
                "r4": float(parts[7]),
                "d": int(parts[8]),
                "k": float(parts[9]),
            }
            result["segments"].append(seg)
            mat_segments.append(global_seg_idx)
            global_seg_idx += 1
            idx += 1

        result["materials"].append({
            "epsilon": eps,
            "mu": mu,
            "sigma": sigma,
            "segments": mat_segments,
        })

    return result
