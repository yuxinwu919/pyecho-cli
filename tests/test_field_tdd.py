"""Test-driven unit tests for ``pyecho.preprocess.field.InitialFieldGenerator``.

The generator solves the axisymmetric (round, mode-0 monopole) Poisson
equation on a 2-D ``(nz, nr)`` r-z mesh, computes ``E = -grad(phi)``,
Lorentz-boosts to the lab frame and writes three float32 field arrays
(Ez, Er, Hphi) plus an ``<ii`` dimensions header to a ``*.bin`` file.

The tests below verify the binary output format, mesh dimensions,
monopole/axis symmetry handling, error paths, edge cases and the
numerical correctness of the internal Poisson / field / deposition
routines.  All file I/O runs under pytest's ``tmp_path``.
"""

from __future__ import annotations

import struct
import warnings
from pathlib import Path

import numpy as np
import pytest

from pyecho.errors import PreprocessError
from pyecho.mathlib import Z0, c, eps0
from pyecho.preprocess.field import InitialFieldGenerator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

#: Single macro-particle deposited into interior grid cells.
#: y = 3e-4 -> r/hr = 1.5 -> cells (col 1, col 2) with 0.25 weights.
PARTICLE = [0.0, 3e-4, 0.0, 0.0, 1.0, 1e-9]


def make_generator(
    pipe_radius: float = 2e-3,
    mesh_length: int = 20,
    step_z: float = 2e-4,
    step_y: float = 2e-4,
) -> InitialFieldGenerator:
    return InitialFieldGenerator(pipe_radius, mesh_length, step_z, step_y)


def write_particles(
    tmp_path: Path, particles, name: str = "particles.txt"
) -> Path:
    """Write an ECHO2D-format particle file (6 columns per row)."""
    arr = np.asarray(particles, dtype=np.float64)
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    path: Path = tmp_path / name
    np.savetxt(path, arr, fmt="%.9e")
    return path


def read_field_bin(path: str | Path, nz: int, nr: int) -> tuple[np.ndarray, ...]:
    """Parse a field ``.bin`` file and return ``(Ez, Er, Hphi)``."""
    raw = Path(path).read_bytes()
    assert len(raw) == 8 + 3 * nz * nr * 4, "unexpected file size"
    header_nz, header_nr = struct.unpack("<ii", raw[:8])
    assert (header_nz, header_nr) == (nz, nr)
    body = np.frombuffer(raw[8:], dtype="<f4")
    ez = body[0 : nz * nr].reshape(nz, nr, order="F")
    er = body[nz * nr : 2 * nz * nr].reshape(nz, nr, order="F")
    hp = body[2 * nz * nr : 3 * nz * nr].reshape(nz, nr, order="F")
    return ez, er, hp


# ---------------------------------------------------------------------------
# 1. Round geometry: output file format
# ---------------------------------------------------------------------------


class TestOutputFormat:
    def test_output_file_written_next_to_particle_file(self, tmp_path):
        pf = write_particles(tmp_path, [PARTICLE])
        gen = make_generator()
        out = gen.generate(pf, current_filter=1)
        out_path = Path(out)
        assert out_path.is_file()
        assert out_path.parent == pf.parent
        assert out_path.name == f"{pf.stem}_field.bin"

    def test_output_binary_header_is_nz_nr_int32(self, tmp_path):
        pf = write_particles(tmp_path, [PARTICLE])
        gen = make_generator()
        out = Path(gen.generate(pf))
        nz, nr = struct.unpack("<ii", out.read_bytes()[:8])
        assert (nz, nr) == (gen.mesh_length, int(gen.pipe_radius / gen.step_y) + 1)

    def test_output_three_float32_components_column_major(self, tmp_path):
        pf = write_particles(tmp_path, [PARTICLE])
        gen = make_generator()
        out = Path(gen.generate(pf))
        ez, er, hp = read_field_bin(out, gen.nz, gen.nr)
        assert ez.dtype == np.float32
        assert er.dtype == np.float32
        assert hp.dtype == np.float32
        assert ez.shape == (gen.nz, gen.nr)
        assert er.shape == (gen.nz, gen.nr)
        assert hp.shape == (gen.nz, gen.nr)
        assert np.isfinite(ez).all()
        assert np.isfinite(er).all()
        assert np.isfinite(hp).all()

    def test_output_components_are_related_by_lorentz_boost(self, tmp_path):
        """The lab-frame Hphi = beta*c/Z0 * Er_lab (Er_lab = gamma * Er)."""
        pf = write_particles(tmp_path, [PARTICLE])
        gen = make_generator()
        ez, er, hp = read_field_bin(Path(gen.generate(pf)), gen.nz, gen.nr)
        beta = 0.999999
        expected = beta * c / Z0 * er
        np.testing.assert_allclose(hp, expected, rtol=1e-4, atol=1e-9)


# ---------------------------------------------------------------------------
# 5-6. Mesh dimensions: shape matches mesh parameters
# ---------------------------------------------------------------------------


class TestMeshDimensions:
    def test_grid_dims_derived_from_mesh_parameters(self, tmp_path):
        pf = write_particles(tmp_path, [PARTICLE])
        gen = make_generator(pipe_radius=5e-3, mesh_length=37, step_y=1e-3)
        gen.generate(pf)
        assert gen.nz == 37
        assert gen.nr == int(5e-3 / 1e-3) + 1 == 6

    def test_field_shape_matches_mesh_dimensions(self, tmp_path):
        pf = write_particles(tmp_path, [PARTICLE])
        gen = make_generator()
        ez, er, hp = read_field_bin(Path(gen.generate(pf)), gen.nz, gen.nr)
        assert ez.shape == (gen.mesh_length, int(gen.pipe_radius / gen.step_y) + 1)
        assert er.shape == ez.shape
        assert hp.shape == ez.shape


# ---------------------------------------------------------------------------
# 3-4, 7-9. mode-0 monopole field + symmetry / axis boundary conditions
# ---------------------------------------------------------------------------


class TestMonopoleSymmetry:
    def test_y_sign_flip_produces_identical_field(self, tmp_path):
        """Monopole (mode 0) is symmetric under y -> -y (r = |y|)."""
        gen = make_generator()
        pf1 = write_particles(tmp_path, [[0.0, 3e-4, 0.0, 0.0, 1.0, 1e-9]], "a.txt")
        pf2 = write_particles(tmp_path, [[0.0, -3e-4, 0.0, 0.0, 1.0, 1e-9]], "b.txt")
        ez1, er1, hp1 = read_field_bin(Path(gen.generate(pf1)), gen.nz, gen.nr)
        ez2, er2, hp2 = read_field_bin(Path(gen.generate(pf2)), gen.nz, gen.nr)
        np.testing.assert_array_equal(ez1, ez2)
        np.testing.assert_array_equal(er1, er2)
        np.testing.assert_array_equal(hp1, hp2)

    def test_field_is_real_2d_rz_only_no_azimuthal_mode(self, tmp_path):
        """Mode-0 monopole solver produces plain (nz, nr) real arrays."""
        pf = write_particles(tmp_path, [PARTICLE])
        gen = make_generator()
        ez, er, hp = read_field_bin(Path(gen.generate(pf)), gen.nz, gen.nr)
        assert ez.ndim == er.ndim == hp.ndim == 2
        assert not np.iscomplexobj(ez)
        assert not np.iscomplexobj(er)
        assert not np.iscomplexobj(hp)

    def test_on_axis_particle_no_nan(self, tmp_path):
        pf = write_particles(tmp_path, [[0.0, 1e-9, 0.0, 0.0, 1.0, 1e-9]])
        gen = make_generator()
        ez, er, hp = read_field_bin(Path(gen.generate(pf)), gen.nz, gen.nr)
        assert np.isfinite(ez).all()
        assert np.isfinite(er).all()
        assert np.isfinite(hp).all()

    def test_charge_at_mesh_midpoint_is_mirror_antisymmetric_in_ez(self, tmp_path):
        """With filtering off, a charge at the grid's midpoint gives an
        odd Ez / even Er about the z-centre (monopole parity).

        The nz-node grid spans [z_min, z_max - hz], whose symmetry axis
        is the grid midpoint z = -hz/2 (here -1e-4 m); the mirror map is
        row i <-> row nz-1-i.
        """
        pf = write_particles(tmp_path, [[-1e-4, 3e-4, 0.0, 0.0, 1.0, 1e-9]])
        gen = make_generator(mesh_length=20)
        ez, er, _ = read_field_bin(Path(gen.generate(pf, current_filter=0)), gen.nz, gen.nr)
        for i, j in [(7, 12), (8, 11), (9, 10)]:
            np.testing.assert_allclose(ez[i], -ez[j], rtol=1e-3, atol=1e-6)
            np.testing.assert_allclose(er[i], er[j], rtol=1e-3, atol=1e-6)

    def test_mesh_position_z_shifts_symmetry_axis(self, tmp_path):
        """A non-zero ``mesh_position_z`` moves the grid centre, so a charge
        at the *new* midpoint z = mesh_position_z - hz/2 still yields the
        same odd-Ez / even-Er monopole parity about the shifted axis."""
        pf = write_particles(tmp_path, [[9e-4, 3e-4, 0.0, 0.0, 1.0, 1e-9]])
        gen = make_generator(mesh_length=20)
        ez, er, _ = read_field_bin(
            Path(gen.generate(pf, mesh_position_z=1e-3, current_filter=0)),
            gen.nz, gen.nr,
        )
        for i, j in [(7, 12), (8, 11), (9, 10)]:
            np.testing.assert_allclose(ez[i], -ez[j], rtol=1e-3, atol=1e-6)
            np.testing.assert_allclose(er[i], er[j], rtol=1e-3, atol=1e-6)

    def test_poisson_solution_respects_dirichlet_boundaries(self, tmp_path):
        """phi = 0 on z boundaries (rows 0, nz-1) and outer wall (col nr-1)."""
        pf = write_particles(tmp_path, [PARTICLE])
        gen = make_generator()
        charge = gen._deposit_charge(
            np.asarray([PARTICLE]), 20, 11, 2e-4, 2e-4, z_min=-2e-3
        )
        phi = gen._solve_poisson(charge, 20, 11, 2e-4, 2e-4)
        assert np.allclose(phi[0, :], 0.0, atol=1e-12)
        assert np.allclose(phi[-1, :], 0.0, atol=1e-12)
        assert np.allclose(phi[:, -1], 0.0, atol=1e-12)


# ---------------------------------------------------------------------------
# 6, 10-12. Errors
# ---------------------------------------------------------------------------


class TestErrors:
    def test_missing_particle_file_raises(self, tmp_path):
        gen = make_generator()
        with pytest.raises(PreprocessError, match="not found"):
            gen.generate(tmp_path / "missing.txt")

    def test_too_few_columns_raises(self, tmp_path):
        pf = write_particles(tmp_path, [[0.0, 3e-4, 1.0]])  # only 3 columns
        gen = make_generator()
        with pytest.raises(PreprocessError, match="columns"):
            gen.generate(pf)

    def test_non_numeric_particle_file_raises(self, tmp_path):
        pf = tmp_path / "bad.txt"
        pf.write_text("hello world\nnot numbers\n", encoding="utf-8")
        gen = make_generator()
        with pytest.raises(PreprocessError, match="Failed to read particle file"):
            gen.generate(pf)

    def test_missing_input_file_is_not_a_directory_trap(self, tmp_path):
        """A directory path must be rejected, not silently accepted."""
        gen = make_generator()
        with pytest.raises(PreprocessError, match="not found"):
            gen.generate(tmp_path)  # tmp_path is a directory


# ---------------------------------------------------------------------------
# 13-15. Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_zero_mesh_length_raises_clean_error(self, tmp_path):
        pf = write_particles(tmp_path, [PARTICLE])
        gen = make_generator(mesh_length=0)
        with pytest.raises(PreprocessError, match="mesh"):
            gen.generate(pf)

    def test_single_cell_mesh_raises_clean_error(self, tmp_path):
        pf = write_particles(tmp_path, [PARTICLE])
        gen = make_generator(mesh_length=1)
        with pytest.raises(PreprocessError, match="mesh"):
            gen.generate(pf)

    def test_tiny_pipe_radius_raises_clean_error(self, tmp_path):
        # nr = int(1e-4/2e-4) + 1 = 1 -> no interior cells
        pf = write_particles(tmp_path, [PARTICLE])
        gen = make_generator(pipe_radius=1e-4)
        with pytest.raises(PreprocessError, match="mesh"):
            gen.generate(pf)

    def test_large_mesh_length_runs_and_preserves_shape(self, tmp_path):
        pf = write_particles(tmp_path, [PARTICLE])
        gen = make_generator(mesh_length=120, step_z=5e-5)
        ez, er, hp = read_field_bin(Path(gen.generate(pf)), gen.nz, gen.nr)
        assert ez.shape == (120, gen.nr)
        assert np.isfinite(ez).all()

    def test_large_current_filter_runs(self, tmp_path):
        pf = write_particles(tmp_path, [PARTICLE])
        gen = make_generator()
        ez, _, _ = read_field_bin(Path(gen.generate(pf, current_filter=8)), gen.nz, gen.nr)
        assert ez.shape == (gen.nz, gen.nr)
        assert np.isfinite(ez).all()


# ---------------------------------------------------------------------------
# 8-12. Field value verification (vacuum region / known solutions)
# ---------------------------------------------------------------------------


class TestFieldValues:
    def test_no_deposited_charge_yields_zero_vacuum_field(self, tmp_path):
        """Particles outside the mesh deposit nothing -> constant (zero)
        field throughout the vacuum region."""
        pf = write_particles(tmp_path, [[-100.0, 3e-4, 0.0, 0.0, 1.0, 1e-9]])
        gen = make_generator()
        ez, er, hp = read_field_bin(Path(gen.generate(pf)), gen.nz, gen.nr)
        np.testing.assert_allclose(ez, 0.0, atol=1e-12)
        np.testing.assert_allclose(er, 0.0, atol=1e-12)
        np.testing.assert_allclose(hp, 0.0, atol=1e-12)

    def test_poisson_residual_small_in_interior(self):
        """The discrete axisymmetric Poisson equation must be satisfied."""
        gen = make_generator()
        nz, nr, hz, hr = 20, 11, 2e-4, 2e-4
        charge = np.zeros((nz, nr))
        charge[10, 2] = 1.0
        charge[5, 3] = -0.5
        phi = gen._solve_poisson(charge, nz, nr, hz, hr)

        r = (np.arange(nr, dtype=np.float64) + 0.5) * hr
        r[0] = 0.5 * hr
        rp, rm = r + 0.5 * hr, r - 0.5 * hr
        rm[0] = 0.0
        res = np.zeros_like(phi)
        for i in range(1, nz - 1):
            for j in range(1, nr - 1):
                d2z = (phi[i + 1, j] - 2 * phi[i, j] + phi[i - 1, j]) / (hz * hz)
                d2r = (
                    rp[j] * (phi[i, j + 1] - phi[i, j])
                    - rm[j] * (phi[i, j] - phi[i, j - 1])
                ) / (r[j] * hr * hr)
                res[i, j] = d2z + d2r + charge[i, j] / eps0
        scale = np.max(np.abs(charge)) / eps0
        assert np.max(np.abs(res)) / scale < 1e-6

    def test_poisson_solver_is_linear_superposition(self):
        """phi(a + b) == phi(a) + phi(b) for the linear solver."""
        gen = make_generator()
        nz, nr, hz, hr = 20, 11, 2e-4, 2e-4
        a = np.zeros((nz, nr)); a[10, 2] = 1.0
        b = np.zeros((nz, nr)); b[4, 1] = 0.7
        phia = gen._solve_poisson(a, nz, nr, hz, hr)
        phib = gen._solve_poisson(b, nz, nr, hz, hr)
        phis = gen._solve_poisson(a + b, nz, nr, hz, hr)
        np.testing.assert_allclose(phis, phia + phib, rtol=1e-6, atol=1e-9)

    def test_compute_efield_known_potential_radial(self):
        """phi = r^2/2 -> Er = -r, Ez = 0."""
        gen = make_generator()
        nz, nr, hz, hr = 20, 11, 2e-4, 2e-4
        r = (np.arange(nr, dtype=np.float64) + 0.5) * hr
        phi = np.broadcast_to(r**2 / 2.0, (nz, nr)).copy()
        ez, er = gen._compute_efield(phi, nz, nr, hz, hr)
        np.testing.assert_allclose(ez, 0.0, atol=1e-12)
        np.testing.assert_allclose(er[0, 1:-1], -r[1:-1], rtol=1e-6)

    def test_compute_efield_known_potential_longitudinal(self):
        """phi = z^2/2 -> Ez = -z, Er = 0."""
        gen = make_generator()
        nz, nr, hz, hr = 20, 11, 2e-4, 2e-4
        z = (np.arange(nz, dtype=np.float64) - 10.0) * hz
        phi = np.broadcast_to((z**2 / 2.0)[:, None], (nz, nr)).copy()
        ez, er = gen._compute_efield(phi, nz, nr, hz, hr)
        np.testing.assert_allclose(er, 0.0, atol=1e-12)
        np.testing.assert_allclose(ez[1:-1, 0], -z[1:-1], rtol=1e-6)

    def test_charge_deposition_bilinear_weights(self):
        """A particle at a cell centre splits 0.25 into each corner cell."""
        gen = make_generator()
        nz, nr, hz, hr = 20, 11, 2e-4, 2e-4
        z_min, iz0, ir0 = -2e-3, 10, 2
        z = z_min + (iz0 + 0.5) * hz
        y = (ir0 + 0.5) * hr
        particles = np.asarray([[z, y, 0.0, 0.0, 1.0, 4.0]])
        grid = gen._deposit_charge(particles, nz, nr, hz, hr, z_min=z_min)
        block = grid[iz0:iz0 + 2, ir0:ir0 + 2]
        np.testing.assert_allclose(block, np.full((2, 2), 0.25 * 4.0 / (hz * hr)), rtol=1e-12)
        assert grid.sum() == pytest.approx(4.0 / (hz * hr), rel=1e-12)

    def test_low_pass_filter_halves_delta_peak(self):
        gen = make_generator()
        data = np.zeros((10, 3))
        data[0, :] = 1.0
        out = gen._low_pass_filter_z(data)
        assert out[0, 0] == 1.0            # first row untouched
        assert out[1, 0] == pytest.approx(0.5)  # delta peak halved
        assert out[2, 0] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# 16-18. File I/O details
# ---------------------------------------------------------------------------


class TestFileIO:
    def test_output_created_even_when_particle_file_in_nested_dir(self, tmp_path):
        nested = tmp_path / "a" / "b"
        nested.mkdir(parents=True)
        pf = write_particles(nested, [PARTICLE])
        gen = make_generator()
        out = Path(gen.generate(pf))
        assert out.parent == nested
        assert out.is_file()

    def test_output_name_uses_particle_stem(self, tmp_path):
        pf = write_particles(tmp_path, [PARTICLE], name="beam_01.txt")
        gen = make_generator()
        out = Path(gen.generate(pf))
        assert out.name == "beam_01_field.bin"

    def test_generate_returns_absolute_path(self, tmp_path):
        pf = write_particles(tmp_path, [PARTICLE])
        gen = make_generator()
        out = gen.generate(pf)
        assert Path(out).is_absolute()
        assert Path(out).is_file()

    def test_generate_emits_no_runtime_warnings(self, tmp_path):
        """Regression: the dead 'gamma = 1/sqrt(1-1)' line raised a
        divide-by-zero RuntimeWarning on every call."""
        pf = write_particles(tmp_path, [PARTICLE])
        gen = make_generator()
        with warnings.catch_warnings():
            warnings.simplefilter("error", RuntimeWarning)
            Path(gen.generate(pf))  # must not raise
