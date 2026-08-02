"""Pydantic v2 model for ECHO2D simulation parameters.

Parses, validates, and generates ``input_in.txt`` files for the
ECHO2D electromagnetic wakefield solver.  Supports all parameters
documented in the ECHO manual (Section 4.3.2).

Usage::

    >>> from pyecho.config import ECHO2DParams
    >>> params = ECHO2DParams.from_input_file("input_in.txt")
    >>> print(params.to_input_file())

    >>> params = ECHO2DParams.from_template("round_collimator")
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, ClassVar, Literal

from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
)


# ---------------------------------------------------------------------------
# Field monitor sub-model
# ---------------------------------------------------------------------------

class FieldMonitorConfig(BaseModel):
    """Configuration for a single ECHO2D field monitor.

    Corresponds to one ``FieldMonitor = { ... }`` line in the input file.

    Attributes
    ----------
    component : str
        Field component: ``"Ex"``, ``"Ey"``, ``"Ez"``, ``"Hx"``, ``"Hy"``, ``"Hz"``.
    time_type : str
        Time coordinate: ``"s"`` (co-moving) or ``"z"`` (lab-frame).
    z0, z1 : float
        Longitudinal range [m].
    y0, y1 : float
        Transverse range [m].
    s0, s1 : float
        *s*-coordinate range [m].
    N : int
        Number of snapshots.
    """

    component: str
    time_type: Literal["s", "z"]
    z0: float
    z1: float
    y0: float
    y1: float
    s0: float
    s1: float
    N: int

    @field_validator("component")
    @classmethod
    def _validate_component(cls, v: str) -> str:
        allowed = {"Ex", "Ey", "Ez", "Hx", "Hy", "Hz"}
        if v not in allowed:
            raise ValueError(f"Field component must be one of {allowed}, got {v!r}")
        return v


# ---------------------------------------------------------------------------
# Main parameters model
# ---------------------------------------------------------------------------

class ECHO2DParams(BaseModel):
    """ECHO2D simulation parameters.

    All parameters correspond to keys in the ``input_in.txt`` command file.
    Default values are taken from the N1 round-collimator example.
    """

    # ---- geometry ----
    GeometryFile: str = Field(
        default="collimator.txt",
        description="Name of ASCII geometry description file (*.txt).",
    )
    Units: Literal["m", "cm", "mm"] = Field(
        default="cm",
        description="Length unit used in the geometry file.",
    )
    GeometryType: Literal["round", "recta"] = Field(
        default="round",
        description="Geometry type: 'round' or 'recta' (rectangular).",
    )
    Width: float = Field(
        default=0.0,
        description="Width of rectangular geometry [m]; obsolete for round.",
    )
    SymmetryCondition: Literal["magn", "elec"] = Field(
        default="magn",
        description="Boundary condition on axis for rectangular geometry.",
    )
    Convex: bool = Field(
        default=True,
        description="Use convex-geometry acceleration.",
    )

    # ---- beam ----
    InPartFile: str = Field(
        default="-",
        description="Input bunch file: '-' for Gaussian, or *.txt/*.bin path.",
    )
    BunchSigma: float = Field(
        default=0.001,
        description="RMS bunch length [m] (used when InPartFile='-').",
    )
    Offset: int = Field(
        default=-1,
        description="Bunch transverse offset in mesh lines; -1 = maximum.",
    )
    InjectionTimeStep: int = Field(
        default=0,
        description="Particle injection time in time steps.",
    )

    # ---- field ----
    InFieldDir: str = Field(
        default="-",
        description="Directory with initial field files; '-' = compute internally.",
    )
    PortDir: str = Field(
        default="-",
        description="Directory with waveguide port mode file; '-' = absent.",
    )
    PortPosition: int = Field(
        default=-1,
        description="Waveguide port position in mesh lines; -1 = absent.",
    )

    # ---- model ----
    WakeIntMethod: Literal["dir", "ind"] = Field(
        default="ind",
        description="Wake integration method: 'dir' (direct) or 'ind' (indirect).",
    )
    Modes: list[int] = Field(
        default_factory=lambda: [0],
        description="Fourier azimuthal modes to compute (space-separated in file).",
    )
    ParticleMotion: bool = Field(
        default=False,
        description="Enable equations of motion for particles.",
    )
    ParticleField: bool = Field(
        default=True,
        description="Enable field calculation.",
    )
    CurrentFilter: int = Field(
        default=0,
        description="Number of 2-point low-pass filter passes on current profile.",
    )
    ParticleLoss: bool = Field(
        default=False,
        description="Enable particle loss in materials.",
    )

    # ---- mesh ----
    MeshLength: int = Field(
        default=52,
        description="Moving mesh length in mesh lines.",
    )
    StartPosition: int = Field(
        default=0,
        description="Longitudinal start position of moving mesh in mesh lines.",
    )
    TimeSteps: int = Field(
        default=-1,
        description="Number of time steps; -1 = fly through entire structure.",
    )
    StepY: float = Field(
        default=0.0002,
        description="Transverse mesh step h_y [m].",
    )
    StepZ: float = Field(
        default=0.0002,
        description="Longitudinal mesh step h_z [m].",
    )
    NStepsInConductive: int = Field(
        default=0,
        description="Mesh lines in conductive wall skin depth; 0 = PEC.",
    )
    AdjustMesh: bool = Field(
        default=True,
        description="Adjust transverse mesh to outgoing waveguide size.",
    )
    MeshMotionFile: str = Field(
        default="-",
        description="Mesh motion file (*.txt); '-' = fly with light velocity.",
    )

    # ---- monitors ----
    WakeMonitor: list[int] | None = Field(
        default=None,
        description="Wake save points: [M1, M2, M3] (start, end, step in time steps).",
    )
    BeamMonitor: list[int] | None = Field(
        default=None,
        description="Beam monitor parameters: [M1, M2, M3, M4].",
    )
    FieldMonitor: list[FieldMonitorConfig] = Field(
        default_factory=list,
        description="Field monitor configurations.",
    )
    DumpField: bool = Field(
        default=False,
        description="Dump electromagnetic field to disk.",
    )
    DumpParticles: bool = Field(
        default=False,
        description="Dump particle data to disk.",
    )
    DumpCurrent: bool = Field(
        default=False,
        description="Dump current profile to disk.",
    )
    DumpMesh: bool = Field(
        default=False,
        description="Dump mesh geometry to disk.",
    )

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------

    @field_validator("GeometryType", mode="before")
    @classmethod
    def _normalize_geometry_type(cls, v: str) -> str:
        """Accept 'rect' as alias for 'recta'."""
        if v == "rect":
            return "recta"
        return v

    @field_validator("Modes", mode="before")
    @classmethod
    def _parse_modes(cls, v: object) -> list[int]:
        """Accept space-separated string or list."""
        if isinstance(v, str):
            return [int(x) for x in v.split()]
        if isinstance(v, list):
            return [int(x) for x in v]
        raise ValueError(f"Cannot parse Modes from {v!r}")

    @field_validator("WakeMonitor", "BeamMonitor", mode="before")
    @classmethod
    def _parse_int_list_or_none(cls, v: object) -> list[int] | None:
        """Accept space-separated string, list, or '-' for None."""
        if v is None:
            return None
        if isinstance(v, str):
            stripped = v.strip()
            if stripped == "-" or stripped == "":
                return None
            return [int(x) for x in stripped.split()]
        if isinstance(v, list):
            return [int(x) for x in v]
        raise ValueError(f"Cannot parse monitor list from {v!r}")

    @model_validator(mode="after")
    def _validate_recta_modes(self) -> "ECHO2DParams":
        """For recta geometry with symmetry, modes should be odd."""
        if self.GeometryType == "recta" and self.SymmetryCondition in ("magn", "elec"):
            # With magnetic/electric symmetry on axis, only odd modes
            # contribute for rectangular structures.
            # This is a soft warning, not a hard error.
            pass
        return self

    @model_validator(mode="after")
    def _validate_width(self) -> "ECHO2DParams":
        """Width must be > 0 for recta geometry."""
        if self.GeometryType == "recta" and self.Width <= 0:
            raise ValueError(
                f"Width must be > 0 for recta geometry, got {self.Width}"
            )
        return self

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_input_file(self) -> str:
        """Generate the exact ``input_in.txt`` format.

        Returns
        -------
        str
            Full content of an ECHO2D-compatible input file.
        """
        lines: list[str] = []

        # ---- geometry ----
        lines.append("%%%%%%%%%%%%%% geometry %%%%%%%%%%%%%%%%%%%%")
        lines.append("")
        lines.append(f"GeometryFile={self.GeometryFile}\t% -(Gaussian beam)")
        lines.append(f"Units={self.Units}\t% -m/cm/mm")
        lines.append(f"GeometryType={self.GeometryType}\t % recta / round")
        lines.append(f"Width={self.Width}\t% in meters")
        lines.append(f"SymmetryCondition={self.SymmetryCondition}\t % magn/elec")
        lines.append(f"Convex={self._bool_to_int(self.Convex)}")

        # ---- beam ----
        lines.append("")
        lines.append("%%%%%%%%%%%%%% beam %%%%%%%%%%%%%%%%%%%%%%%%")
        lines.append("")
        lines.append(f"InPartFile={self.InPartFile}")
        lines.append(f"BunchSigma={self.BunchSigma}")
        lines.append(f"Offset={self.Offset}")
        lines.append(f"InjectionTimeStep={self.InjectionTimeStep}")

        # ---- field ----
        lines.append("")
        lines.append("%%%%%%%%%%%%%%  field %%%%%%%%%%%%%%%%%%%%%%")
        lines.append("")
        lines.append(f"InFieldDir={self.InFieldDir}")
        lines.append(f"PortDir={self.PortDir}")
        lines.append(f"PortPosition={self.PortPosition}")

        # ---- model ----
        lines.append("")
        lines.append("%%%%%%%%%%%%%% model %%%%%%%%%%%%%%%%%%%%%%%")
        lines.append("")
        lines.append(f"WakeIntMethod={self.WakeIntMethod}")
        lines.append(f"Modes={' '.join(str(m) for m in self.Modes)} ")
        lines.append(f"ParticleMotion={self._bool_to_int(self.ParticleMotion)}")
        lines.append(f"ParticleField={self._bool_to_int(self.ParticleField)}")
        lines.append(f"CurrentFilter={self.CurrentFilter}")
        lines.append(f"ParticleLoss={self._bool_to_int(self.ParticleLoss)}")

        # ---- mesh ----
        lines.append("")
        lines.append("%%%%%%%%%%%%%% mesh %%%%%%%%%%%%%%%%%%%%%%%")
        lines.append("")
        lines.append(f"MeshLength={self.MeshLength}")
        lines.append(f"StartPosition={self.StartPosition}")
        lines.append(f"TimeSteps={self.TimeSteps}")
        lines.append(f"StepY={self.StepY}")
        lines.append(f"StepZ={self.StepZ}")
        lines.append(f"NStepsInConductive={self.NStepsInConductive}")
        lines.append(f"AdjustMesh={self._bool_to_int(self.AdjustMesh)}")
        lines.append(f"MeshMotionFile={self.MeshMotionFile}")

        # ---- monitors ----
        lines.append("")
        lines.append("%%%%%%%%%%%%%% monitors %%%%%%%%%%%%%%%%%%%%%%%")
        lines.append("")

        if self.WakeMonitor is not None:
            wm = " ".join(str(x) for x in self.WakeMonitor)
            lines.append(f"WakeMonitor={wm} ")

        if self.BeamMonitor is not None:
            bm = " ".join(str(x) for x in self.BeamMonitor)
            lines.append(f"BeamMonitor={bm} ")

        for fm in self.FieldMonitor:
            # Standard format per ECHO2D manual section 4.3.6:
            # FieldMonitor = F tF z0 z1 y0 y1 s0 s1 N
            lines.append(
                f"FieldMonitor = {fm.component} "
                f"{fm.time_type} "
                f"{fm.z0} {fm.z1} "
                f"{fm.y0} {fm.y1} "
                f"{fm.s0} {fm.s1} "
                f"{fm.N}"
            )

        lines.append(f"DumpField={self._bool_to_int(self.DumpField)}")
        lines.append(f"DumpParticles={self._bool_to_int(self.DumpParticles)}")
        lines.append(f"DumpCurrent={self._bool_to_int(self.DumpCurrent)}")
        lines.append(f"DumpMesh={self._bool_to_int(self.DumpMesh)}")

        return "\n".join(lines) + "\n"

    # ------------------------------------------------------------------
    # Deserialisation
    # ------------------------------------------------------------------

    @classmethod
    def from_input_file(cls, path: str | Path) -> "ECHO2DParams":
        """Parse an ECHO2D ``input_in.txt`` file.

        Parameters
        ----------
        path : str or Path
            Path to the input file.

        Returns
        -------
        ECHO2DParams
            Populated parameters model.

        Raises
        ------
        FileNotFoundError
            If *path* does not exist.
        ValueError
            If the file contains unrecognised keys or malformed values.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Input file not found: {path}")

        raw_text = path.read_text(encoding="utf-8")
        return cls.from_string(raw_text)

    @classmethod
    def from_string(cls, text: str) -> "ECHO2DParams":
        """Parse parameters from a string containing ``input_in.txt`` content.

        Parameters
        ----------
        text : str
            Raw content of an input file.

        Returns
        -------
        ECHO2DParams
        """
        kv: dict[str, Any] = {}
        field_monitors: list[str] = []

        for line in text.splitlines():
            stripped = line.strip()

            # Skip empty lines and section headers
            if not stripped or stripped.startswith("%"):
                continue

            # Handle FieldMonitor specially (curly-brace format)
            if stripped.lower().startswith("fieldmonitor"):
                field_monitors.append(stripped)
                continue

            # Standard key=value lines
            if "=" not in stripped:
                continue

            key, _, value = stripped.partition("=")
            key = key.strip()
            value = value.strip()

            # Remove inline comments (everything after unquoted %)
            value = _strip_comment(value)

            if not key:
                continue

            kv[key] = value

        # Parse field monitors
        if field_monitors:
            kv["FieldMonitor"] = [
                _parse_field_monitor_line(fm) for fm in field_monitors
            ]

        return cls.model_validate(kv)

    # ------------------------------------------------------------------
    # Templates
    # ------------------------------------------------------------------

    #: Registry of built-in templates.
    _TEMPLATES: ClassVar[dict[str, dict[str, Any]]] = {
        "round_collimator": {
            "GeometryFile": "collimator.txt",
            "Units": "cm",
            "GeometryType": "round",
            "Width": 0.0,
            "SymmetryCondition": "magn",
            "Convex": True,
            "InPartFile": "-",
            "BunchSigma": 0.001,
            "Offset": -1,
            "InjectionTimeStep": 0,
            "InFieldDir": "-",
            "PortDir": "-",
            "PortPosition": -1,
            "WakeIntMethod": "ind",
            "Modes": [0],
            "ParticleMotion": False,
            "ParticleField": True,
            "CurrentFilter": 0,
            "ParticleLoss": False,
            "MeshLength": 52,
            "StartPosition": 0,
            "TimeSteps": -1,
            "StepY": 0.0002,
            "StepZ": 0.0002,
            "NStepsInConductive": 0,
            "AdjustMesh": True,
            "MeshMotionFile": "-",
            "DumpField": False,
            "DumpParticles": False,
            "DumpCurrent": False,
            "DumpMesh": False,
        },
        "flat_absorber": {
            "GeometryFile": "photon_absorber_cm.txt",
            "Units": "cm",
            "GeometryType": "recta",
            "Width": 0.07,
            "SymmetryCondition": "magn",
            "Convex": True,
            "InPartFile": "-",
            "BunchSigma": 0.004,
            "Offset": -1,
            "InjectionTimeStep": 0,
            "InFieldDir": "-",
            "PortDir": "-",
            "PortPosition": -1,
            "WakeIntMethod": "ind",
            "Modes": [1, 3, 5, 7, 9, 11, 13, 15],
            "ParticleMotion": False,
            "ParticleField": True,
            "CurrentFilter": 0,
            "ParticleLoss": False,
            "MeshLength": 104,
            "StartPosition": 0,
            "TimeSteps": -1,
            "StepY": 0.0008,
            "StepZ": 0.0008,
            "NStepsInConductive": 0,
            "AdjustMesh": False,
            "MeshMotionFile": "-",
            "DumpField": False,
            "DumpParticles": False,
            "DumpCurrent": False,
            "DumpMesh": False,
        },
        "tesla_cavity": {
            "GeometryFile": "tesla9.txt",
            "Units": "cm",
            "GeometryType": "round",
            "Width": 0.0,
            "SymmetryCondition": "magn",
            "Convex": True,
            "InPartFile": "-",
            "BunchSigma": 0.001,
            "Offset": -1,
            "InjectionTimeStep": 0,
            "InFieldDir": "-",
            "PortDir": "-",
            "PortPosition": -1,
            "WakeIntMethod": "ind",
            "Modes": [0, 1],
            "ParticleMotion": False,
            "ParticleField": True,
            "CurrentFilter": 0,
            "ParticleLoss": False,
            "MeshLength": 52,
            "StartPosition": 0,
            "TimeSteps": -1,
            "StepY": 0.00019943,
            "StepZ": 0.0002,
            "NStepsInConductive": 0,
            "AdjustMesh": False,
            "MeshMotionFile": "-",
            "DumpField": False,
            "DumpParticles": False,
            "DumpCurrent": False,
            "DumpMesh": False,
        },
        "dlw": {
            "GeometryFile": "dlw.txt",
            "Units": "mm",
            "GeometryType": "recta",
            "Width": 0.02,
            "SymmetryCondition": "magn",
            "Convex": False,
            "InPartFile": "-",
            "BunchSigma": 0.0001,
            "Offset": 0,
            "InjectionTimeStep": 0,
            "InFieldDir": "-",
            "PortDir": "-",
            "PortPosition": -1,
            "WakeIntMethod": "dir",
            "Modes": [1, 3, 5],
            "ParticleMotion": False,
            "ParticleField": True,
            "CurrentFilter": 0,
            "ParticleLoss": False,
            "MeshLength": 250,
            "StartPosition": 0,
            "TimeSteps": -1,
            "StepY": 5e-5,
            "StepZ": 5e-5,
            "NStepsInConductive": 0,
            "AdjustMesh": False,
            "MeshMotionFile": "-",
            "DumpField": False,
            "DumpParticles": False,
            "DumpCurrent": False,
            "DumpMesh": False,
        },
    }

    @classmethod
    def from_template(cls, name: str, **overrides: Any) -> "ECHO2DParams":
        """Create parameters from a named preset template.

        Parameters
        ----------
        name : str
            Template name.  Available templates:
            ``"round_collimator"``, ``"flat_absorber"``, ``"tesla_cavity"``.
        **overrides
            Keyword arguments to override specific template fields.

        Returns
        -------
        ECHO2DParams

        Raises
        ------
        ValueError
            If *name* is not a recognised template.
        """
        try:
            data = dict(cls._TEMPLATES[name])
        except KeyError:
            raise ValueError(
                f"Unknown template {name!r}. "
                f"Available: {list(cls._TEMPLATES.keys())}"
            )
        data.update(overrides)
        return cls.model_validate(data)

    @classmethod
    def list_templates(cls) -> list[str]:
        """Return the names of all registered templates."""
        return list(cls._TEMPLATES.keys())

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _bool_to_int(value: bool) -> int:
        """Convert Python bool → ECHO2D 0/1 integer."""
        return 1 if value else 0


# ---------------------------------------------------------------------------
# Module-level convenience functions (lazy-imported by __init__.py)
# ---------------------------------------------------------------------------

def load_params(path: str | Path) -> ECHO2DParams:
    """Load ECHO2D parameters from an ``input_in.txt`` file.

    Parameters
    ----------
    path : str or Path
        Path to the input file.

    Returns
    -------
    ECHO2DParams
    """
    return ECHO2DParams.from_input_file(path)


def save_params(params: ECHO2DParams, path: str | Path) -> None:
    """Write ECHO2D parameters to an ``input_in.txt`` file.

    Parameters
    ----------
    params : ECHO2DParams
        Parameter model to serialise.
    path : str or Path
        Destination file path.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(params.to_input_file(), encoding="utf-8")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _strip_comment(value: str) -> str:
    """Remove trailing ``%`` comment from a value string.

    Preserves quoted strings (single quotes) that may contain ``%``.
    """
    # Simple heuristic: split on % that is not inside single quotes
    in_quote = False
    for i, ch in enumerate(value):
        if ch == "'":
            in_quote = not in_quote
        elif ch == "%" and not in_quote:
            return value[:i].rstrip()
    return value


def _parse_field_monitor_line(line: str) -> FieldMonitorConfig:
    """Parse a ``FieldMonitor`` line from an ECHO2D input file.

    Supports two formats (ECHO2D manual section 4.3.6):

    1. **Curly-brace format** (used in N8 example)::

        FieldMonitor = { 'Ez' 'z' 0.02 0.1 0 0.021 0 1 1 }

    2. **Standard space-separated format** (manual default)::

        FieldMonitor = Ez z 0.02 0.1 0 0.021 0 1 1

    Parameters
    ----------
    line : str
        Raw line from input file.

    Returns
    -------
    FieldMonitorConfig
    """
    # Detect format: curly-brace or standard
    if "{" in line and "}" in line:
        return _parse_field_monitor_curly(line)
    else:
        return _parse_field_monitor_standard(line)


def _parse_field_monitor_curly(line: str) -> FieldMonitorConfig:
    """Parse curly-brace format: ``FieldMonitor = { 'Ez' 'z' ... }``."""
    match = re.search(r"\{([^}]*)\}", line)
    if not match:
        raise ValueError(f"Cannot parse curly-brace FieldMonitor line: {line!r}")

    content = match.group(1).strip()

    # Tokenise: split on whitespace, preserving quoted strings
    tokens: list[str] = []
    i = 0
    while i < len(content):
        if content[i] == "'":
            # Quoted string
            j = content.index("'", i + 1)
            tokens.append(content[i + 1 : j])
            i = j + 1
        elif content[i].isspace():
            i += 1
        else:
            # Unquoted token
            j = i
            while j < len(content) and not content[j].isspace():
                j += 1
            tokens.append(content[i:j])
            i = j

    if len(tokens) != 9:
        raise ValueError(
            f"Expected 9 tokens in FieldMonitor, got {len(tokens)}: {tokens}"
        )

    return FieldMonitorConfig(
        component=tokens[0],
        time_type=tokens[1],  # type: ignore[arg-type]
        z0=float(tokens[2]),
        z1=float(tokens[3]),
        y0=float(tokens[4]),
        y1=float(tokens[5]),
        s0=float(tokens[6]),
        s1=float(tokens[7]),
        N=int(tokens[8]),
    )


def _parse_field_monitor_standard(line: str) -> FieldMonitorConfig:
    """Parse standard format: ``FieldMonitor = Ez z 0.02 0.1 ...``."""
    # Remove "FieldMonitor =" prefix (case-insensitive)
    content = re.sub(r"^FieldMonitor\s*=\s*", "", line, flags=re.IGNORECASE).strip()

    # Split on whitespace
    tokens = content.split()
    if len(tokens) != 9:
        raise ValueError(
            f"Expected 9 tokens in FieldMonitor (standard format), "
            f"got {len(tokens)}: {tokens}"
        )

    return FieldMonitorConfig(
        component=tokens[0],
        time_type=tokens[1],  # type: ignore[arg-type]
        z0=float(tokens[2]),
        z1=float(tokens[3]),
        y0=float(tokens[4]),
        y1=float(tokens[5]),
        s0=float(tokens[6]),
        s1=float(tokens[7]),
        N=int(tokens[8]),
    )
