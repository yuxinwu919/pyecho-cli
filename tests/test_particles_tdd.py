"""Tests for ``pyecho.postprocess.particles``.

Covers:
- ``load_echo_particles``    (binary ``particles.out`` parse / missing / corrupt)
- ``compute_beam_moments``   (mean / rms / emittance / energy, empty + single row)
- ``convert_echo_to_astra``  (ASTRA binary layout, momenta/time/status, z→t)
- ``compute_particle_statistics``  (active/lost counts, means, emittances)
"""

from __future__ import annotations

import struct
from pathlib import Path

import numpy as np
import pytest

from pyecho.errors import PostProcessError
from pyecho.postprocess.particles import (
    compute_beam_moments,
    compute_particle_statistics,
    convert_echo_to_astra,
    load_echo_particles,
)

# Independent physics literals (matching the module constants) so the tests
# are not tautological with the implementation.
E0 = 510998.95          # electron rest energy [eV] ≈ m_e c² / e
C = 2.99792458e8        # speed of light [m/s]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _write_echo_particles(
    path: Path,
    *,
    x,
    y,
    z,
    px,
    py,
    pz,
    status=None,
    q0: float = 1e-12,
) -> None:
    """Write a little-endian ECHO ``particles.out`` file."""
    x = np.asarray(x, dtype=float)
    Np = x.size
    if status is None:
        status = np.zeros(Np, dtype=np.int64)
    status = np.asarray(status, dtype=np.int64)
    phase = np.column_stack([x, y, z, px, py, pz]).astype("<f8")
    buf = struct.pack("<dd", float(Np), q0)
    buf += phase.tobytes(order="F")          # component-major: all x, all y, ...
    buf += status.astype("<i8").tobytes()
    path.write_bytes(buf)


def _make_particles(
    *,
    x,
    y,
    z,
    px,
    py,
    pz,
    status=None,
):
    x = np.asarray(x, dtype=float)
    Np = x.size
    if status is None:
        status = np.zeros(Np, dtype=np.int64)
    return {
        "x": x,
        "y": np.asarray(y, dtype=float),
        "z": np.asarray(z, dtype=float),
        "px": np.asarray(px, dtype=float),
        "py": np.asarray(py, dtype=float),
        "pz": np.asarray(pz, dtype=float),
        "status": np.asarray(status, dtype=np.int64),
    }


def _read_astra_record(raw: bytes, rec: int) -> tuple:
    """Unpack a single 108-byte ASTRA record (rec 0-based) as a tuple."""
    off = 4 + rec * 108
    vals = struct.unpack_from("<6d", raw, off)
    t, charge = struct.unpack_from("<2d", raw, off + 48)
    (status,) = struct.unpack_from("<i", raw, off + 64)
    (macro_charge,) = struct.unpack_from("<d", raw, off + 72)
    return (*vals, t, charge, status, macro_charge)


# ---------------------------------------------------------------------------
# load_echo_particles
# ---------------------------------------------------------------------------

class TestLoadEchoParticles:
    def test_valid_file_parses_header(self, tmp_path) -> None:
        p = tmp_path / "particles.out"
        _write_echo_particles(
            p,
            x=[0.001, -0.002, 0.003],
            y=[0.0, 0.002, -0.001],
            z=[0.5, 0.1, -0.2],
            px=[0.01, -0.02, 0.03],
            py=[0.005, 0.0, -0.004],
            pz=[1.0, 2.0, 0.5],
            status=[0, 0, 1],
            q0=2.5e-12,
        )

        data = load_echo_particles(p)

        assert data["Np"] == 3
        assert data["q0"] == pytest.approx(2.5e-12)
        assert data["x"].shape == (3,)

    def test_phase_space_is_component_major(self, tmp_path) -> None:
        p = tmp_path / "parts.out"
        _write_echo_particles(
            p,
            x=[0.001, 0.001, 0.001],
            y=[0.002, 0.002, 0.002],
            z=[0.003, 0.003, 0.003],
            px=[0.004, 0.004, 0.004],
            py=[0.005, 0.005, 0.005],
            pz=[0.006, 0.006, 0.006],
        )

        data = load_echo_particles(p)

        # each particle's row must be (x, y, z, px, py, pz) in order
        assert np.allclose(data["x"], 0.001)
        assert np.allclose(data["y"], 0.002)
        assert np.allclose(data["z"], 0.003)
        assert np.allclose(data["px"], 0.004)
        assert np.allclose(data["py"], 0.005)
        assert np.allclose(data["pz"], 0.006)

    def test_status_flags_parsed(self, tmp_path) -> None:
        p = tmp_path / "parts.out"
        _write_echo_particles(
            p,
            x=[0.001, 0.002, 0.003, 0.004],
            y=[0.0, 0.0, 0.0, 0.0],
            z=[0.0, 0.0, 0.0, 0.0],
            px=[0.0, 0.0, 0.0, 0.0],
            py=[0.0, 0.0, 0.0, 0.0],
            pz=[1.0, 1.0, 1.0, 1.0],
            status=[0, 0, 1, 1],
        )

        data = load_echo_particles(p)

        assert data["status"].dtype == np.int64
        assert data["status"].tolist() == [0, 0, 1, 1]

    def test_missing_file_raises(self, tmp_path) -> None:
        with pytest.raises(PostProcessError) as exc_info:
            load_echo_particles(tmp_path / "does_not_exist.out")
        assert "Cannot read" in str(exc_info.value)

    def test_file_too_small_raises(self, tmp_path) -> None:
        p = tmp_path / "tiny.out"
        p.write_bytes(b"\x00\x01\x02")  # < 16 bytes minimum header

        with pytest.raises(PostProcessError) as exc_info:
            load_echo_particles(p)
        assert "too small" in str(exc_info.value)

    def test_nonpositive_np_raises(self, tmp_path) -> None:
        p = tmp_path / "bad_np.out"
        p.write_bytes(struct.pack("<dd", -3.0, 1e-12) + b"\x00" * 16)

        with pytest.raises(PostProcessError) as exc_info:
            load_echo_particles(p)
        assert "invalid particle count" in str(exc_info.value)

    def test_truncated_data_raises(self, tmp_path) -> None:
        p = tmp_path / "truncated.out"
        # header claims 4 particles but only stores 1 particle's data
        buf = struct.pack("<dd", 4.0, 1e-12)
        buf += np.zeros(6, dtype="<f8").tobytes(order="F")
        buf += np.zeros(1, dtype="<i8").tobytes()
        p.write_bytes(buf)

        with pytest.raises(PostProcessError) as exc_info:
            load_echo_particles(p)
        assert "expected" in str(exc_info.value)

    def test_accepts_str_path(self, tmp_path) -> None:
        p = tmp_path / "parts.out"
        _write_echo_particles(
            p,
            x=[0.001], y=[0.0], z=[0.1], px=[0.0], py=[0.0], pz=[1.0],
        )

        data = load_echo_particles(str(p))

        assert data["Np"] == 1


# ---------------------------------------------------------------------------
# compute_beam_moments
# ---------------------------------------------------------------------------

# 19-column BeamMomentsMonitor row:
#   step <x> <y> <z> <px> <py> <pz> <x2> <y2> <z2> <px2> <py2> <pz2>
#   <xpx> <ypy> <zpz> <E/E0> <E2/E0> <zE/E0>
def _beam_row(step: float) -> list[float]:
    return [
        step,
        1e-3, 2e-3, 0.5,                    # <x> <y> <z>
        0.01, 0.02, 1.0,                    # <px> <py> <pz>
        4e-6, 9e-6, 0.25,                   # <x2> <y2> <z2>
        1e-4, 4e-4, 1.0,                    # <px2> <py2> <pz2>
        1e-5, 1e-5, 0.1,                    # <xpx> <ypy> <zpz>
        1.001, 1.002, 0.5,                  # <E> <E2> <zE>
    ]


class TestComputeBeamMoments:
    def test_mean_moments_and_z_reconstruction(self, tmp_path) -> None:
        f = tmp_path / "moments.txt"
        np.savetxt(f, np.array([_beam_row(0.0), _beam_row(2.0)]), fmt="%.12e")
        step_z = 0.0005

        res = compute_beam_moments(f, step_z=step_z)

        assert res["step"].tolist() == [0.0, 2.0]
        assert np.allclose(res["z"], [0.0, 2.0 * step_z])
        assert np.allclose(res["mean_x"], 1e-3)
        assert np.allclose(res["mean_y"], 2e-3)
        assert np.allclose(res["mean_z"], 0.5)
        assert np.allclose(res["mean_px"], 0.01)
        assert np.allclose(res["mean_py"], 0.02)
        assert np.allclose(res["mean_pz"], 1.0)

    def test_rms_sizes_are_sqrt_of_squared_moments(self, tmp_path) -> None:
        f = tmp_path / "moments.txt"
        np.savetxt(f, np.array([_beam_row(0.0)]), fmt="%.12e")

        res = compute_beam_moments(f)

        assert np.allclose(res["sigma_x"], np.sqrt(4e-6))
        assert np.allclose(res["sigma_y"], np.sqrt(9e-6))
        assert np.allclose(res["sigma_z"], np.sqrt(0.25))
        assert np.allclose(res["sigma_px"], np.sqrt(1e-4))
        assert np.allclose(res["sigma_py"], np.sqrt(4e-4))
        assert np.allclose(res["sigma_pz"], np.sqrt(1.0))

    def test_emittance(self, tmp_path) -> None:
        f = tmp_path / "moments.txt"
        np.savetxt(f, np.array([_beam_row(0.0)]), fmt="%.12e")

        res = compute_beam_moments(f)

        # eps = sqrt(<u2><pu2> - <u·pu>²)
        assert np.allclose(res["emit_x"], np.sqrt(4e-6 * 1e-4 - 1e-5**2))
        assert np.allclose(res["emit_y"], np.sqrt(9e-6 * 4e-4 - 1e-5**2))
        assert np.allclose(res["emit_z"], np.sqrt(0.25 * 1.0 - 0.1**2))

    def test_energy_and_energy_spread(self, tmp_path) -> None:
        f = tmp_path / "moments.txt"
        np.savetxt(f, np.array([_beam_row(0.0)]), fmt="%.12e")

        res = compute_beam_moments(f)

        assert res["energy"][0] == pytest.approx(1.001 * E0, rel=1e-9)
        assert res["energy2"][0] == pytest.approx(1.002 * E0**2, rel=1e-9)
        assert res["energy_spread"][0] == pytest.approx(np.sqrt(1.002) * E0, rel=1e-9)
        assert res["zE"][0] == pytest.approx(0.5 * E0, rel=1e-9)

    def test_single_row_file(self, tmp_path) -> None:
        f = tmp_path / "one_row.txt"
        np.savetxt(f, np.array([_beam_row(1.0)]), fmt="%.12e")
        step_z = 0.0005

        res = compute_beam_moments(f, step_z=step_z)

        assert res["n_rows"] == 1
        assert res["n_cols"] == 19
        assert np.allclose(res["z"], [1.0 * step_z])
        assert np.allclose(res["sigma_x"], np.sqrt(4e-6))

    def test_missing_columns_omit_keys(self, tmp_path) -> None:
        # 2 columns → step / z / mean_x present, everything else omitted
        two = tmp_path / "two_col.txt"
        np.savetxt(two, np.array([[0.0, 1e-3], [1.0, 2e-3]]), fmt="%.12e")
        res = compute_beam_moments(two)
        assert res["n_cols"] == 2
        assert np.allclose(res["step"], [0.0, 1.0])
        assert np.allclose(res["mean_x"], [1e-3, 2e-3])
        # first-order mean keys always exist but are None for missing columns
        assert res["mean_y"] is None
        assert res["mean_z"] is None
        assert "sigma_x" not in res
        assert "energy" not in res

        # 16 columns → sigma/emit present, energy keys absent
        sixteen = tmp_path / "sixteen_col.txt"
        np.savetxt(sixteen, _beam_row(0.0)[:16], fmt="%.12e")
        res = compute_beam_moments(sixteen)
        assert res["n_cols"] == 16
        assert "sigma_x" in res
        assert "emit_x" in res
        assert "energy" not in res
        assert "energy_spread" not in res

    def test_empty_file_raises(self, tmp_path) -> None:
        # np.loadtxt returns an empty array; the function currently indexes
        # column 0 of an empty row → IndexError (a latent crash, not a
        # PostProcessError).  Documented here as the current behaviour.
        f = tmp_path / "empty.txt"
        f.write_text("")

        with pytest.raises(IndexError):
            compute_beam_moments(f)


# ---------------------------------------------------------------------------
# convert_echo_to_astra
# ---------------------------------------------------------------------------

class TestConvertEchoToAstra:
    @pytest.fixture()
    def echo_file(self, tmp_path) -> Path:
        p = tmp_path / "particles.out"
        _write_echo_particles(
            p,
            x=[0.001, -0.002],
            y=[0.002, 0.0],
            z=[5e-4, -1e-4],
            px=[0.01, -0.02],
            py=[0.005, 0.0],
            pz=[1.0, 2.0],
            status=[0, 1],
            q0=1e-12,
        )
        return p

    def test_returns_particle_count_and_header(self, echo_file, tmp_path) -> None:
        astra = tmp_path / "out.astra"

        n = convert_echo_to_astra(echo_file, astra)

        assert n == 2
        raw = astra.read_bytes()
        (header,) = struct.unpack_from("<i", raw, 0)
        assert header == 2

    def test_record_size_108_bytes(self, echo_file, tmp_path) -> None:
        astra = tmp_path / "out.astra"

        convert_echo_to_astra(echo_file, astra)

        raw = astra.read_bytes()
        assert len(raw) == 4 + 2 * 108

    def test_positions_copied_directly(self, echo_file, tmp_path) -> None:
        astra = tmp_path / "out.astra"

        convert_echo_to_astra(echo_file, astra)
        raw = astra.read_bytes()

        r0 = _read_astra_record(raw, 0)
        r1 = _read_astra_record(raw, 1)
        assert r0[:3] == pytest.approx((0.001, 0.002, 5e-4))
        assert r1[:3] == pytest.approx((-0.002, 0.0, -1e-4))

    def test_momenta_converted_to_ev_per_c(self, echo_file, tmp_path) -> None:
        astra = tmp_path / "out.astra"

        convert_echo_to_astra(echo_file, astra)
        raw = astra.read_bytes()

        r0 = _read_astra_record(raw, 0)
        r1 = _read_astra_record(raw, 1)
        # p[eV/c] = βγ · (m_e c² / e)
        assert r0[3:6] == pytest.approx((0.01 * E0, 0.005 * E0, 1.0 * E0), rel=1e-9)
        assert r1[3:6] == pytest.approx((-0.02 * E0, 0.0 * E0, 2.0 * E0), rel=1e-9)

    def test_time_is_z_over_c(self, echo_file, tmp_path) -> None:
        astra = tmp_path / "out.astra"

        convert_echo_to_astra(echo_file, astra)
        raw = astra.read_bytes()

        r0 = _read_astra_record(raw, 0)
        r1 = _read_astra_record(raw, 1)
        assert r0[6] == pytest.approx(5e-4 / C, rel=1e-12)
        assert r1[6] == pytest.approx(-1e-4 / C, rel=1e-12)

    def test_status_mapping_and_charge(self, echo_file, tmp_path) -> None:
        astra = tmp_path / "out.astra"

        convert_echo_to_astra(echo_file, astra)
        raw = astra.read_bytes()

        r0 = _read_astra_record(raw, 0)   # active → 5
        r1 = _read_astra_record(raw, 1)   # lost → 1
        assert r0[8] == 5
        assert r1[8] == 1
        assert r0[7] == pytest.approx(1e-12)  # per-particle charge = q0

    def test_macro_charge_default_and_override(self, echo_file, tmp_path) -> None:
        default_out = tmp_path / "default.astra"
        convert_echo_to_astra(echo_file, default_out)
        raw = _read_astra_record(default_out.read_bytes(), 0)
        # default total = Np·q0 → macro_charge = q0
        assert raw[9] == pytest.approx(1e-12)

        override_out = tmp_path / "override.astra"
        convert_echo_to_astra(echo_file, override_out, total_charge=3e-12)
        raw = _read_astra_record(override_out.read_bytes(), 0)
        assert raw[9] == pytest.approx(3e-12 / 2)

    def test_missing_echo_file_raises(self, tmp_path) -> None:
        with pytest.raises(PostProcessError):
            convert_echo_to_astra(
                tmp_path / "nope.out", tmp_path / "out.astra"
            )


# ---------------------------------------------------------------------------
# compute_particle_statistics
# ---------------------------------------------------------------------------

class TestComputeParticleStatistics:
    def test_means_and_sigmas(self) -> None:
        parts = _make_particles(
            x=[-1.0, 0.0, 1.0],
            y=[0.0, 1.0, 2.0],
            z=[1.0, 1.0, 1.0],
            px=[1.0, 2.0, 3.0],
            py=[0.0, 0.0, 0.0],
            pz=[0.0, 0.0, 0.0],
        )

        stats = compute_particle_statistics(parts)

        assert stats["mean_x"] == pytest.approx(0.0)
        assert stats["sigma_x"] == pytest.approx(np.sqrt(2.0 / 3.0))
        assert stats["mean_y"] == pytest.approx(1.0)
        assert stats["sigma_y"] == pytest.approx(np.sqrt(2.0 / 3.0))
        assert stats["mean_z"] == pytest.approx(1.0)
        assert stats["sigma_z"] == pytest.approx(0.0)
        assert stats["mean_px"] == pytest.approx(2.0)
        assert stats["sigma_px"] == pytest.approx(np.sqrt(2.0 / 3.0))
        assert stats["mean_py"] == pytest.approx(0.0)
        assert stats["sigma_py"] == pytest.approx(0.0)

    def test_emittance(self) -> None:
        parts = _make_particles(
            x=[-1.0, 0.0, 1.0],
            y=[-1.0, 0.0, 1.0],
            z=[-1.0, 0.0, 1.0],
            px=[1.0, -1.0, 0.0],
            py=[0.0, 0.0, 0.0],
            pz=[1.0, -1.0, 0.0],
        )

        stats = compute_particle_statistics(parts)

        # <u2><pu2> − <u·pu>² = (2/3)(2/3) − (1/3)² = 1/3 for x and z
        assert stats["emit_x"] == pytest.approx(np.sqrt(1.0 / 3.0))
        # py constant → zero transverse emittance in y
        assert stats["emit_y"] == pytest.approx(0.0)
        assert stats["emit_z"] == pytest.approx(np.sqrt(1.0 / 3.0))

    def test_active_lost_counts(self) -> None:
        parts = _make_particles(
            x=[0.0, 1.0, 2.0, 3.0, 4.0],
            y=[0.0, 0.0, 0.0, 0.0, 0.0],
            z=[0.0, 0.0, 0.0, 0.0, 0.0],
            px=[0.0, 0.0, 0.0, 0.0, 0.0],
            py=[0.0, 0.0, 0.0, 0.0, 0.0],
            pz=[1.0, 1.0, 1.0, 1.0, 1.0],
            status=[0, 0, 0, 1, 1],
        )

        stats = compute_particle_statistics(parts)

        assert stats["n_active"] == 3
        assert stats["n_lost"] == 2

    def test_lost_particles_excluded_from_stats(self) -> None:
        # lost particle carries extreme values and must not affect the means
        parts = _make_particles(
            x=[1.0, 2.0, 3.0, 1e9],
            y=[0.0, 0.0, 0.0, 0.0],
            z=[0.0, 0.0, 0.0, 0.0],
            px=[0.0, 0.0, 0.0, 0.0],
            py=[0.0, 0.0, 0.0, 0.0],
            pz=[1.0, 1.0, 1.0, 1.0],
            status=[0, 0, 0, 1],
        )

        stats = compute_particle_statistics(parts)

        assert stats["mean_x"] == pytest.approx(2.0)
        assert stats["sigma_x"] == pytest.approx(np.sqrt(2.0 / 3.0))
        assert stats["n_active"] == 3

    def test_all_lost_returns_empty(self) -> None:
        parts = _make_particles(
            x=[1.0, 2.0],
            y=[0.0, 0.0],
            z=[0.0, 0.0],
            px=[0.0, 0.0],
            py=[0.0, 0.0],
            pz=[1.0, 1.0],
            status=[1, 1],
        )

        stats = compute_particle_statistics(parts)

        assert stats == {}
