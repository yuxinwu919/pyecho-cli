"""Tests for the preprocess subpackage (bunch profiles + particle converters).

Covers:
- ``pyecho.preprocess.bunch``:
  - ``generate_gaussian``  (shape, normalization, peak position)
  - ``generate_flattop``   (plateau, edge decay)
  - ``save_bunch_profile`` (header, line count, roundtrip, str path)
  - ``validate_bunch_profile`` (valid / missing / non-uniform step)
- ``pyecho.preprocess.particles``:
  - ``create_beam_profile`` (Gaussian, custom, error cases)
  - ``parse_beam_profile`` (missing file, header skipping)
  - ``ASTRAConverter`` (astra→echo, divergence, echo→astra)
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from pyecho.errors import PreprocessError
from pyecho.preprocess.bunch import (
    generate_flattop,
    generate_gaussian,
    save_bunch_profile,
    validate_bunch_profile,
)
from pyecho.preprocess.particles import (
    ASTRAConverter,
    create_beam_profile,
    parse_beam_profile,
)


# ---------------------------------------------------------------------------
# generate_gaussian
# ---------------------------------------------------------------------------

class TestGenerateGaussian:
    def test_returns_uniform_grid(self) -> None:
        sigma, n_points = 0.001, 101
        s, rho = generate_gaussian(sigma=sigma, n_points=n_points)

        assert s.shape == (n_points,)
        assert rho.shape == (n_points,)
        # uniform step
        assert np.allclose(np.diff(s), np.diff(s)[0])
        # positive head→tail range: [0, n_sigma * sigma]
        assert s[0] == pytest.approx(0.0)
        assert s[-1] == pytest.approx(6.0 * sigma)
        assert np.all(s >= 0.0)

    def test_peak_normalized_to_one(self) -> None:
        s, rho = generate_gaussian(sigma=0.001, n_points=201)

        assert rho.max() == pytest.approx(1.0)
        assert np.all(rho <= 1.0 + 1e-12)
        assert np.all(rho >= 0.0)
        # within the finite window the tails stay strictly positive
        assert rho.min() > 0.0

    def test_peak_at_window_center(self) -> None:
        sigma, n_points = 0.0005, 101
        s, rho = generate_gaussian(sigma=sigma, n_points=n_points, n_sigma=6.0)

        center = n_points // 2
        assert int(np.argmax(rho)) == center
        assert s[center] == pytest.approx(3.0 * sigma)


# ---------------------------------------------------------------------------
# generate_flattop
# ---------------------------------------------------------------------------

class TestGenerateFlattop:
    def test_plateau_normalized_to_one(self) -> None:
        s, rho = generate_flattop(
            sigma=0.001, rise=0.0001, flat_length=0.002, n_points=1001
        )

        assert rho.max() == pytest.approx(1.0)
        assert np.all(rho <= 1.0 + 1e-12)
        assert np.all(rho >= 0.0)
        # a large plateau of exactly-1.0 samples exists (the flat region)
        n_ones = int((rho == 1.0).sum())
        assert n_ones > 100
        # the bunch head (first sample) is far below the plateau
        assert rho[0] < 0.5
        # some samples fall below the plateau (rising/falling edges)
        assert (rho < 1.0).any()

    def test_edges_decay_gaussian_tail(self) -> None:
        s, rho = generate_flattop(
            sigma=0.001, rise=0.0001, flat_length=0.002, n_points=1001
        )

        # first sample sits 3 sigma from the rising-edge center → exp(-4.5)
        assert rho[0] == pytest.approx(np.exp(-0.5 * 3.0**2), rel=1e-3)

        # the plateau spans approximately flat_length in meters
        s_flat = s[rho == 1.0]
        assert s_flat.max() - s_flat.min() == pytest.approx(0.002, abs=5e-4)


# ---------------------------------------------------------------------------
# save_bunch_profile
# ---------------------------------------------------------------------------

class TestSaveBunchProfile:
    def test_header_and_line_count(self, tmp_path) -> None:
        s, rho = generate_gaussian(n_points=50)
        out = tmp_path / "profile.txt"

        saved = save_bunch_profile(out, s, rho)
        assert saved == out

        lines = out.read_text().splitlines()
        assert len(lines) == 1 + 50
        assert lines[0].startswith("# %")
        assert "% s[m] charge [normalized]" in lines[0]

    def test_roundtrip(self, tmp_path) -> None:
        s, rho = generate_gaussian(n_points=100)
        out = tmp_path / "bunch.txt"

        save_bunch_profile(out, s, rho)
        data = np.loadtxt(out, comments=["%", "#"])

        assert data.shape == (100, 2)
        assert np.allclose(data[:, 0], s)
        assert np.allclose(data[:, 1], rho)

    def test_accepts_str_path(self, tmp_path) -> None:
        s, rho = generate_gaussian(n_points=20)
        out = tmp_path / "str_path.txt"

        saved = save_bunch_profile(str(out), s, rho)

        assert isinstance(saved, type(out))
        assert out.is_file()


# ---------------------------------------------------------------------------
# validate_bunch_profile
# ---------------------------------------------------------------------------

class TestValidateBunchProfile:
    def test_valid_file(self, tmp_path) -> None:
        s, rho = generate_gaussian(n_points=201)
        out = tmp_path / "valid.txt"
        save_bunch_profile(out, s, rho)

        res = validate_bunch_profile(out)
        assert res["valid"] is True
        assert res["n_points"] == 201
        assert res["peak"] == pytest.approx(1.0)
        assert res["s_step"] == pytest.approx(np.mean(np.diff(s)))
        assert res["s_range"][0] == pytest.approx(s[0])
        assert res["s_range"][1] == pytest.approx(s[-1])
        assert res["issues"] == []

    def test_missing_file_invalid(self, tmp_path) -> None:
        res = validate_bunch_profile(tmp_path / "nope.txt")

        assert res["valid"] is False
        assert res["n_points"] == 0
        assert any("not found" in issue for issue in res["issues"])

    def test_nonuniform_step_invalid(self, tmp_path) -> None:
        p = tmp_path / "bad_step.txt"
        p.write_text(
            "% s[m] charge [normalized]\n"
            "0.000 1.0\n"
            "0.001 0.8\n"
            "0.003 0.5\n"
            "0.004 0.2\n"
        )

        res = validate_bunch_profile(p)
        assert res["valid"] is False
        assert any("uniform" in issue for issue in res["issues"])


# ---------------------------------------------------------------------------
# create_beam_profile
# ---------------------------------------------------------------------------

class TestCreateBeamProfile:
    def test_gaussian(self, tmp_path) -> None:
        s, rho = generate_gaussian(n_points=80)
        out = tmp_path / "beam.txt"

        written = create_beam_profile(s, rho, out)

        assert isinstance(written, str)
        assert Path(written) == out.resolve()
        lines = out.read_text().splitlines()
        assert len(lines) == 1 + len(s)
        assert lines[0].startswith("%")

    def test_custom_values_roundtrip(self, tmp_path) -> None:
        s_vals = np.linspace(0.0, 0.01, 50)
        rho_vals = np.linspace(1.0, 0.2, 50)
        out = tmp_path / "custom.txt"

        create_beam_profile(s_vals, rho_vals, out)
        data = np.loadtxt(out, comments="%")

        assert data.shape == (50, 2)
        assert np.allclose(data[:, 0], s_vals)
        assert np.allclose(data[:, 1], rho_vals)

    def test_length_mismatch_and_short_input_raises(self, tmp_path) -> None:
        with pytest.raises(PreprocessError):
            create_beam_profile(
                np.array([0.0, 0.001, 0.002]),
                np.array([1.0, 0.5]),
                tmp_path / "mismatch.txt",
            )

        with pytest.raises(PreprocessError):
            create_beam_profile(
                np.array([0.0]),
                np.array([1.0]),
                tmp_path / "short.txt",
            )


# ---------------------------------------------------------------------------
# parse_beam_profile
# ---------------------------------------------------------------------------

class TestParseBeamProfile:
    def test_missing_file_raises(self, tmp_path) -> None:
        with pytest.raises(PreprocessError) as exc_info:
            parse_beam_profile(tmp_path / "missing.txt")
        assert "not found" in str(exc_info.value)

    def test_skips_header_and_comments(self, tmp_path) -> None:
        p = tmp_path / "prof.txt"
        p.write_text(
            "% s[m] charge [normalized]\n"
            "# another comment line\n"
            "\n"
            "0.000000e+00\t 1.000000e+00\n"
            "1.000000e-04\t 0.900000e+00\n"
            "2.000000e-04\t 0.700000e+00\n"
        )

        s, rho = parse_beam_profile(p)

        assert np.allclose(s, [0.0, 1e-4, 2e-4])
        assert np.allclose(rho, [1.0, 0.9, 0.7])


# ---------------------------------------------------------------------------
# ASTRAConverter
# ---------------------------------------------------------------------------

class TestASTRAConverter:
    def test_astra_to_echo_columns(self, tmp_path) -> None:
        astra_file = tmp_path / "dist.astra"
        # x y z px py pz clock charge index status
        rows = np.array(
            [
                [0.01, 0.02, 0.03, 1.0e6, 2.0e6, 1.0e7, 0.0, 0.5, 1.0, 1.0],
                [-0.01, 0.005, -0.02, -0.5e6, 0.5e6, 0.8e7, 0.0, 1.5, 2.0, 1.0],
            ]
        )
        np.savetxt(astra_file, rows)
        echo_file = tmp_path / "particles.echo"

        ASTRAConverter.astra_to_echo(astra_file, echo_file, z_offset=-0.01)
        data = np.loadtxt(echo_file)

        assert data.shape == (2, 6)
        assert np.allclose(data[:, 0], rows[:, 2] - 0.01)  # z + offset
        assert np.allclose(data[:, 1], rows[:, 1])  # y
        assert np.allclose(data[:, 2], rows[:, 3] / rows[:, 5])  # x' = px / pz
        assert np.allclose(data[:, 3], rows[:, 4] / rows[:, 5])  # y' = py / pz
        assert np.allclose(data[:, 4], rows[:, 5])  # Pz
        # weights normalised so total charge = 1 → 0.5/2.0, 1.5/2.0
        assert np.allclose(data[:, 5], [0.25, 0.75])

    def test_astra_to_echo_divergence(self, tmp_path) -> None:
        astra_file = tmp_path / "div.astra"
        rows = np.array(
            [
                [0.0, 0.0, 0.0, 0.0, 0.0, 1.0e7, 0.0, 1.0, 1.0, 1.0],
                [0.0, 0.0, 0.0, 5.0e6, -3.0e6, 1.0e7, 0.0, 1.0, 2.0, 1.0],
            ]
        )
        np.savetxt(astra_file, rows)
        echo_file = tmp_path / "div.echo"

        ASTRAConverter.astra_to_echo(astra_file, echo_file)
        data = np.loadtxt(echo_file)

        # zero transverse momenta → zero divergence
        assert data[0, 2] == pytest.approx(0.0)
        assert data[0, 3] == pytest.approx(0.0)
        # px/pz = 0.5, py/pz = -0.3
        assert data[1, 2] == pytest.approx(0.5)
        assert data[1, 3] == pytest.approx(-0.3)

    def test_astra_to_echo_missing_file_and_few_columns(self, tmp_path) -> None:
        with pytest.raises(PreprocessError):
            ASTRAConverter.astra_to_echo(
                tmp_path / "nope.astra", tmp_path / "out.echo"
            )

        too_few = tmp_path / "few.astra"
        np.savetxt(too_few, np.array([[0.0, 1.0, 2.0]]))
        with pytest.raises(PreprocessError):
            ASTRAConverter.astra_to_echo(too_few, tmp_path / "out.echo")

    def test_echo_to_astra_columns(self, tmp_path) -> None:
        echo_file = tmp_path / "in.echo"
        rows = np.array(
            [
                [0.001, 0.002, 0.1, -0.2, 1.0e7, 0.5],
                [0.002, 0.001, -0.3, 0.4, 2.0e7, 1.0],
            ]
        )
        np.savetxt(echo_file, rows)
        astra_file = tmp_path / "out.astra"

        ASTRAConverter.echo_to_astra(echo_file, astra_file)
        data = np.loadtxt(astra_file)

        assert data.shape == (2, 10)
        assert np.allclose(data[:, 0], 0.0)  # x = 0 (round geometry)
        assert np.allclose(data[:, 1], rows[:, 1])  # y
        assert np.allclose(data[:, 2], rows[:, 0])  # z
        assert np.allclose(data[:, 3], rows[:, 2] * rows[:, 4])  # px = x' * Pz
        assert np.allclose(data[:, 4], rows[:, 3] * rows[:, 4])  # py = y' * Pz
        assert np.allclose(data[:, 5], rows[:, 4])  # pz
        assert np.allclose(data[:, 6], 0.0)  # clock
        assert np.allclose(data[:, 7], rows[:, 5])  # weight
        assert np.allclose(data[:, 8], [1.0, 2.0])  # index
        assert np.allclose(data[:, 9], 1.0)  # status
