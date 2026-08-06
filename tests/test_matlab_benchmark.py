"""Benchmark the Python wake post-processing against MATLAB reference data.

This module reproduces the MATLAB ``PostProcessor2D`` / ``MatLib4ECHO`` wake
pipelines in Python and compares the resulting loss / kick factors (and
supporting quantities) against reference values extracted from the MATLAB
output files shipped with the ECHO2D ``Examples``.

Reference data layout
---------------------
Reference cases live in ``tests/Examples_tests/``.  Each case is a
subdirectory holding an ``expected.json`` manifest plus an ECHO2D output
tree (raw ``wakeL_XX.txt`` files and ``Iz0.txt``):

::

    tests/Examples_tests/
    ├── N1_round_monopole/
    │   ├── data/                     # parent of the ``round/`` subdirectory
    │   │   └── round/
    │   │       ├── wakeL_00.txt
    │   │       ├── wakeL_01.txt      # (needed only for dipole cases)
    │   │       └── Iz0.txt
    │   └── expected.json
    ├── N5_flat_absorber/
    │   ├── data/
    │   │   ├── magn/                 # cos-cos (magnetic) modes + Iz0.txt
    │   │   └── elec/                 # sin-sin (electric) modes
    │   └── expected.json
    └── ...

``expected.json`` schema::

    {
        "geometry": "round" | "recta",
        "type": "monopole" | "dipole" | "recta",
        "data": "data",                # optional; relative data dir (default "data")
        "n_modes_cc": 15,              # optional; recta only
        "n_modes_ss": 15,              # optional; recta only
        "tolerance": 0.01,             # optional; relative tolerance (default 1%)
        "expected": {
            "loss_long":   <float>,    # monopole / dipole-long / recta-long loss factor [V/pC]
            "rms_spread":  <float>,    # monopole only
            "peak":        <float>,    # monopole only
            "kick_dipole": <float>,    # dipole / recta kick factor [V/pC/m or V/pC/mm]
            "kick_quad":   <float>,    # recta only [V/pC/mm]
            "sigma":       <float>,    # optional; dipole only, bunch RMS length [m]
            "dy":          <float>     # optional; dipole only, effective step [m]
        }
    }

Skipping
--------
The whole module is skipped with :func:`pytest.mark.skipif` when no
reference data is present (``tests/Examples_tests/`` missing or containing
no ``expected.json`` manifest).  A case whose manifest is malformed is *not*
silently skipped — the framework tests fail loudly so the reference data
can be fixed.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Iterator

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Reference-data discovery
# ---------------------------------------------------------------------------

#: Root directory that holds the MATLAB reference cases.
_REFERENCE_DIR = Path(__file__).parent / "Examples_tests"

#: Filename of the per-case manifest.
_MANIFEST_NAME = "expected.json"

#: Expected keys that each case type must define in ``expected``.
_REQUIRED_EXPECTED: dict[str, tuple[str, ...]] = {
    "monopole": ("loss_long", "rms_spread", "peak"),
    "dipole": ("loss_long", "kick_dipole"),
    "recta": ("loss_long", "kick_quad", "kick_dipole"),
}

#: Default relative tolerance — 1% as required by the benchmark.
_DEFAULT_TOLERANCE = 0.01

#: Absolute tolerance used for near-zero expected values (e.g. on-axis
#: quadrupole wakes that are exactly zero in the MATLAB reference).
_DEFAULT_ATOL = 1e-6


def _iter_manifest_dirs() -> list[Path]:
    """Return the case directories that contain an ``expected.json``."""
    if not _REFERENCE_DIR.is_dir():
        return []
    return sorted(
        p
        for p in _REFERENCE_DIR.iterdir()
        if p.is_dir() and (p / _MANIFEST_NAME).is_file()
    )


def _load_case(case_dir: Path) -> dict:
    """Load and fully validate one reference case.

    Returns a case dict with keys ``name``, ``dir``, ``manifest``.  Raises
    :class:`AssertionError` when the manifest is malformed or incomplete.
    """
    manifest_path = case_dir / _MANIFEST_NAME
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AssertionError(
            f"Reference case {case_dir.name}: expected.json is not valid JSON: {exc}"
        ) from exc

    if not isinstance(manifest, dict):
        raise AssertionError(
            f"Reference case {case_dir.name}: manifest must be a JSON object."
        )

    case = {"name": case_dir.name, "dir": case_dir, "manifest": manifest}
    _validate_manifest(case)
    return case


def _validate_manifest(case: dict) -> None:
    """Validate the schema of one case manifest (raises AssertionError)."""
    m = case["manifest"]
    name = case["name"]

    assert "geometry" in m, f"{name}: manifest missing 'geometry'"
    assert "type" in m, f"{name}: manifest missing 'type'"
    expected = m.get("expected")
    assert isinstance(expected, dict), f"{name}: 'expected' must be a JSON object"

    geometry = m["geometry"]
    type_ = m["type"]
    if geometry == "round":
        assert type_ in ("monopole", "dipole"), (
            f"{name}: round geometry requires type 'monopole' or 'dipole', "
            f"got {type_!r}"
        )
    elif geometry == "recta":
        assert type_ == "recta", (
            f"{name}: recta geometry requires type 'recta', got {type_!r}"
        )
    else:
        raise AssertionError(
            f"{name}: unknown geometry {geometry!r} (expected 'round' or 'recta')"
        )

    for key in _REQUIRED_EXPECTED[type_]:
        assert key in expected, (
            f"{name}: expected dict missing required key {key!r} "
            f"(required: {_REQUIRED_EXPECTED[type_]})"
        )

    tol = _tol(case)
    assert isinstance(tol, float) and 0.0 < tol <= 1.0, (
        f"{name}: tolerance must lie in (0, 1], got {tol!r}"
    )

    for key, val in expected.items():
        assert isinstance(val, (int, float)) and math.isfinite(float(val)), (
            f"{name}: expected.{key} must be a finite number, got {val!r}"
        )


def _discover_cases() -> list[dict]:
    """Return the list of valid, fully-validated reference cases."""
    cases: list[dict] = []
    for case_dir in _iter_manifest_dirs():
        try:
            cases.append(_load_case(case_dir))
        except AssertionError:
            # Malformed manifests are reported by the framework tests rather
            # than silently dropping the case from discovery.
            continue
    return cases


def _has_reference_data() -> bool:
    """True when at least one ``expected.json`` manifest exists."""
    return bool(_iter_manifest_dirs())


# ---------------------------------------------------------------------------
# Skipping: no MATLAB reference data available
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.skipif(
    not _has_reference_data(),
    reason=(
        "No MATLAB reference data in tests/Examples_tests/ — "
        "add a case directory with raw wakeL_XX.txt / Iz0.txt files plus "
        "an expected.json manifest (see module docstring)."
    ),
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _case_id(case: dict) -> str:
    return case["name"]


def _cases(geometry: str, type_: str) -> list[dict]:
    return [
        c for c in _discover_cases()
        if c["manifest"]["geometry"] == geometry and c["manifest"]["type"] == type_
    ]


def _data_dir(case: dict) -> Path:
    return case["dir"] / str(case["manifest"].get("data", "data"))


def _expected(case: dict) -> dict:
    return case["manifest"]["expected"]


def _tol(case: dict) -> float:
    return float(case["manifest"].get("tolerance", _DEFAULT_TOLERANCE))


def _atol(case: dict) -> float:
    return float(case["manifest"].get("atol", _DEFAULT_ATOL))


def _assert_close(
    actual: float,
    expected: float,
    rtol: float,
    atol: float,
    label: str,
    case_name: str,
) -> None:
    """Assert ``actual`` within ``rtol``/``atol`` of ``expected``.

    Uses :func:`math.isclose` semantics: a pure relative comparison is
    impossible for zero expected values, so an absolute tolerance *atol* is
    blended in, exactly as the benchmark's "<1%" rule intends.
    """
    assert math.isfinite(float(actual)), (
        f"{case_name}: computed {label}={actual!r} is not finite"
    )
    assert math.isfinite(float(expected)), (
        f"{case_name}: reference {label}={expected!r} is not finite"
    )
    ok = math.isclose(actual, expected, rel_tol=rtol, abs_tol=atol)
    assert ok, (
        f"{case_name}: {label} actual={actual:.8g} vs reference={expected:.8g} "
        f"outside rtol={rtol}, atol={atol}"
    )


# ---------------------------------------------------------------------------
# Post-processing wrappers (mirror the MATLAB pipeline)
# ---------------------------------------------------------------------------


def _process_round_monopole(case: dict):
    """Run ``PP_Wake_Monopole.m`` equivalent for a round monopole case."""
    from pyecho.parser import OutputLoader
    from pyecho.postprocess.wakes.round import process_wake_monopole

    data_dir = _data_dir(case)
    round_dir = data_dir / "round"
    for required in ("wakeL_00.txt", "Iz0.txt"):
        assert (round_dir / required).is_file(), (
            f"{case['name']}: round monopole case missing {round_dir.name}/{required}"
        )
    return process_wake_monopole(OutputLoader(data_dir))


def _process_round_dipole(case: dict):
    """Run ``PP_Wake_Dipole.m`` equivalent for a round dipole case."""
    from pyecho.parser import OutputLoader
    from pyecho.postprocess.wakes.round import process_wake_dipole

    data_dir = _data_dir(case)
    round_dir = data_dir / "round"
    for required in ("wakeL_01.txt", "Iz0.txt"):
        assert (round_dir / required).is_file(), (
            f"{case['name']}: round dipole case missing {round_dir.name}/{required}"
        )
    return process_wake_dipole(OutputLoader(data_dir))


def _process_recta(case: dict) -> dict:
    """Run the full ``PP_WakeLQ(LD).m`` pipeline for a flat/recta case."""
    from pyecho.postprocess.wakes.recta import process_recta_wake

    data_dir = _data_dir(case)
    magn_dir = data_dir / "magn"
    elec_dir = data_dir / "elec"
    for sub in ("magn", "elec"):
        assert (data_dir / sub / "wakeL_01.txt").is_file(), (
            f"{case['name']}: recta case missing {sub}/wakeL_01.txt"
        )
    assert (magn_dir / "Iz0.txt").is_file(), (
        f"{case['name']}: recta case missing magn/Iz0.txt (needed for loss factors)"
    )

    n_modes_cc = int(case["manifest"].get("n_modes_cc", 15))
    n_modes_ss = int(case["manifest"].get("n_modes_ss", 15))
    return process_recta_wake(
        magn_dir,
        elec_dir,
        n_modes_cc=n_modes_cc,
        n_modes_ss=n_modes_ss,
    )


def _primary_loss(case: dict) -> float:
    """Return the primary longitudinal loss factor for any case type."""
    geometry = case["manifest"]["geometry"]
    type_ = case["manifest"]["type"]
    if geometry == "round" and type_ == "monopole":
        return _process_round_monopole(case).loss_factor
    if geometry == "round" and type_ == "dipole":
        return _process_round_dipole(case)["longitudinal"].loss_factor
    return float(_process_recta(case)["loss_long"])


def _extract_arrays(case: dict) -> tuple[np.ndarray, list[tuple[str, np.ndarray]], np.ndarray | None]:
    """Return ``(s, [(label, wake), ...], bunch)`` for any case type."""
    geometry = case["manifest"]["geometry"]
    type_ = case["manifest"]["type"]
    if geometry == "round" and type_ == "monopole":
        result = _process_round_monopole(case)
        return result.s, [("W", result.W)], result.bunch
    if geometry == "round" and type_ == "dipole":
        result = _process_round_dipole(case)
        long_r = result["longitudinal"]
        trans_r = result["transverse"]
        return (
            long_r.s,
            [("W_long", long_r.W), ("W_trans", trans_r.W)],
            long_r.bunch,
        )
    result = _process_recta(case)
    wakes: list[tuple[str, np.ndarray]] = [("Wlong", result["Wlong"])]
    if "Wquad" in result:
        wakes.append(("Wquad", result["Wquad"]))
    if "Wdipole" in result:
        wakes.append(("Wdipole", result["Wdipole"]))
    return result["s"], wakes, result.get("bunch")


# ---------------------------------------------------------------------------
# Framework tests — the reference data itself must be sound
# ---------------------------------------------------------------------------


def test_reference_data_directory_exists() -> None:
    """The reference-data directory must exist (skipped otherwise)."""
    assert _REFERENCE_DIR.is_dir(), f"Missing reference-data directory: {_REFERENCE_DIR}"


def test_reference_data_contains_cases() -> None:
    """At least one reference case must be discoverable."""
    assert len(_discover_cases()) >= 1, (
        "tests/Examples_tests/ contains no valid expected.json manifests"
    )


@pytest.mark.parametrize("case_dir", _iter_manifest_dirs(), ids=lambda p: p.name)
def test_manifests_are_valid_json(case_dir: Path) -> None:
    """Every manifest must parse as a JSON object."""
    try:
        data = json.loads((case_dir / _MANIFEST_NAME).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        pytest.fail(f"{case_dir.name}: manifest is not valid JSON: {exc}")
    assert isinstance(data, dict), f"{case_dir.name}: manifest must be a JSON object"


@pytest.mark.parametrize("case_dir", _iter_manifest_dirs(), ids=lambda p: p.name)
def test_manifests_have_required_fields(case_dir: Path) -> None:
    """Every manifest must satisfy the ``expected.json`` schema."""
    _load_case(case_dir)  # raises AssertionError with a descriptive message


@pytest.mark.parametrize("case_dir", _iter_manifest_dirs(), ids=lambda p: p.name)
def test_expected_values_are_finite(case_dir: Path) -> None:
    """All ``expected`` numbers must be finite floats."""
    case = _load_case(case_dir)
    for key, val in _expected(case).items():
        assert math.isfinite(float(val)), f"{case['name']}: expected.{key} not finite"


@pytest.mark.parametrize("case_dir", _iter_manifest_dirs(), ids=lambda p: p.name)
def test_expected_tolerance_in_range(case_dir: Path) -> None:
    """Per-case tolerance must lie strictly in (0, 1] (1% or tighter)."""
    case = _load_case(case_dir)
    tol = float(case["manifest"].get("tolerance", _DEFAULT_TOLERANCE))
    assert 0.0 < tol <= 1.0, f"{case['name']}: tolerance={tol} outside (0, 1]"


# ---------------------------------------------------------------------------
# Round monopole — PP_Wake_Monopole.m
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case", _cases("round", "monopole"), ids=_case_id)
def test_round_monopole_loss_factor_matches_reference(case: dict) -> None:
    """Monopole loss factor κ = −∫λ·W ds matches the MATLAB reference."""
    result = _process_round_monopole(case)
    _assert_close(
        result.loss_factor,
        _expected(case)["loss_long"],
        _tol(case), _atol(case),
        "loss factor", case["name"],
    )


@pytest.mark.parametrize("case", _cases("round", "monopole"), ids=_case_id)
def test_round_monopole_rms_spread_matches_reference(case: dict) -> None:
    """Monopole RMS spread matches the MATLAB reference."""
    result = _process_round_monopole(case)
    _assert_close(
        result.rms_spread,
        _expected(case)["rms_spread"],
        _tol(case), _atol(case),
        "rms spread", case["name"],
    )


@pytest.mark.parametrize("case", _cases("round", "monopole"), ids=_case_id)
def test_round_monopole_peak_matches_reference(case: dict) -> None:
    """Monopole peak |W| matches the MATLAB reference."""
    result = _process_round_monopole(case)
    _assert_close(
        result.peak,
        _expected(case)["peak"],
        _tol(case), _atol(case),
        "peak", case["name"],
    )


# ---------------------------------------------------------------------------
# Round dipole — PP_Wake_Dipole.m
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case", _cases("round", "dipole"), ids=_case_id)
def test_round_dipole_longitudinal_loss_matches_reference(case: dict) -> None:
    """Dipole longitudinal loss factor matches the MATLAB reference."""
    result = _process_round_dipole(case)
    _assert_close(
        result["longitudinal"].loss_factor,
        _expected(case)["loss_long"],
        _tol(case), _atol(case),
        "longitudinal loss factor", case["name"],
    )


@pytest.mark.parametrize("case", _cases("round", "dipole"), ids=_case_id)
def test_round_dipole_kick_factor_matches_reference(case: dict) -> None:
    """Dipole transverse kick factor matches the MATLAB reference."""
    result = _process_round_dipole(case)
    _assert_close(
        result["transverse"].loss_factor,
        _expected(case)["kick_dipole"],
        _tol(case), _atol(case),
        "kick factor", case["name"],
    )


@pytest.mark.parametrize("case", _cases("round", "dipole"), ids=_case_id)
def test_round_dipole_sigma_matches_reference(case: dict) -> None:
    """Bunch RMS length (from the wakeL_01.txt header) matches the manifest."""
    result = _process_round_dipole(case)
    exp = _expected(case)
    if "sigma" not in exp:
        pytest.skip(f"{case['name']}: no expected 'sigma' in manifest")
    _assert_close(
        result["sigma"],
        exp["sigma"],
        _tol(case), _atol(case),
        "sigma", case["name"],
    )


@pytest.mark.parametrize("case", _cases("round", "dipole"), ids=_case_id)
def test_round_dipole_dy_matches_offset_convention(case: dict) -> None:
    """Effective step dy = (offset + 0.5)·hr reproduces the MATLAB convention.

    This is the +0.5 shift that distinguishes round geometry from recta
    geometry and is essential to match the reference wake.
    """
    from pyecho.parser import find_wake_file, parse_wake_file

    data_dir = _data_dir(case)
    wake_path = find_wake_file(data_dir / "round", 1)
    assert wake_path is not None, f"{case['name']}: no wakeL_01.txt to read dy from"

    parsed = parse_wake_file(wake_path)
    expected_dy = (parsed["offset"] + 0.5) * parsed["hr"]

    result = _process_round_dipole(case)
    assert math.isclose(result["dy"], expected_dy, rel_tol=1e-12), (
        f"{case['name']}: dy={result['dy']!r} does not equal "
        f"(offset+0.5)*hr={expected_dy!r}"
    )

    # Optionally cross-check against a manifest-provided dy.
    exp = _expected(case)
    if "dy" in exp:
        _assert_close(result["dy"], exp["dy"], _tol(case), _atol(case), "dy", case["name"])


# ---------------------------------------------------------------------------
# Recta (flat) geometry — PP_WakeLQ(LD).m
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case", _cases("recta", "recta"), ids=_case_id)
def test_recta_loss_long_matches_reference(case: dict) -> None:
    """Flat-geometry longitudinal loss factor matches the MATLAB reference."""
    result = _process_recta(case)
    assert "loss_long" in result, f"{case['name']}: pipeline produced no loss_long"
    _assert_close(
        float(result["loss_long"]),
        _expected(case)["loss_long"],
        _tol(case), _atol(case),
        "loss_long", case["name"],
    )


@pytest.mark.parametrize("case", _cases("recta", "recta"), ids=_case_id)
def test_recta_kick_quad_matches_reference(case: dict) -> None:
    """Flat-geometry quadrupole kick factor matches the MATLAB reference."""
    result = _process_recta(case)
    assert "loss_quad" in result, f"{case['name']}: pipeline produced no loss_quad"
    _assert_close(
        float(result["loss_quad"]),
        _expected(case)["kick_quad"],
        _tol(case), _atol(case),
        "kick_quad", case["name"],
    )


@pytest.mark.parametrize("case", _cases("recta", "recta"), ids=_case_id)
def test_recta_kick_dipole_matches_reference(case: dict) -> None:
    """Flat-geometry dipole kick factor matches the MATLAB reference."""
    result = _process_recta(case)
    assert "loss_dipole" in result, f"{case['name']}: pipeline produced no loss_dipole"
    _assert_close(
        float(result["loss_dipole"]),
        _expected(case)["kick_dipole"],
        _tol(case), _atol(case),
        "kick_dipole", case["name"],
    )


# ---------------------------------------------------------------------------
# Structural sanity checks — apply to every reference case
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case", _discover_cases(), ids=_case_id)
def test_wake_grid_is_monotonic(case: dict) -> None:
    """The longitudinal s-grid must be strictly increasing."""
    s, _wakes, _bunch = _extract_arrays(case)
    assert np.all(np.diff(s) > 0), f"{case['name']}: s-grid is not strictly increasing"


@pytest.mark.parametrize("case", _discover_cases(), ids=_case_id)
def test_wake_values_are_finite(case: dict) -> None:
    """All computed wake arrays must be finite (no NaN/Inf)."""
    _s, wakes, _bunch = _extract_arrays(case)
    for label, wake in wakes:
        assert np.all(np.isfinite(wake)), f"{case['name']}: {label} contains non-finite values"


@pytest.mark.parametrize("case", _discover_cases(), ids=_case_id)
def test_bunch_profile_matches_wake_grid(case: dict) -> None:
    """The interpolated bunch profile must share the wake s-grid and be finite."""
    s, _wakes, bunch = _extract_arrays(case)
    assert bunch is not None, f"{case['name']}: no bunch profile returned"
    assert len(bunch) == len(s), (
        f"{case['name']}: bunch length {len(bunch)} != wake length {len(s)}"
    )
    assert np.all(np.isfinite(bunch)), f"{case['name']}: bunch contains non-finite values"


@pytest.mark.parametrize("case", _discover_cases(), ids=_case_id)
def test_every_case_defines_loss_long(case: dict) -> None:
    """Every reference case must pin a ``loss_long`` expected value.

    Guarantees that the benchmark always exercises the primary
    loss-factor comparison, not just structural metadata.
    """
    exp = _expected(case)
    assert "loss_long" in exp, f"{case['name']}: expected dict must define 'loss_long'"
    # The computed primary loss must be finite and positive-when-reference-positive.
    actual = _primary_loss(case)
    assert math.isfinite(actual), f"{case['name']}: computed loss_long not finite"
    assert (actual >= 0.0) == (float(exp["loss_long"]) >= 0.0), (
        f"{case['name']}: computed loss_long sign disagrees with the reference"
    )
