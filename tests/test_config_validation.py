"""Unit tests for ECHO2DParams validation logic."""

from __future__ import annotations

import tempfile
import warnings
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from pyecho.cli import app
from pyecho.config import ECHO2DParams, FieldMonitorConfig
from pyecho.errors import ConfigError


runner = CliRunner()


class TestGeometryValidation:
    def test_recta_requires_positive_width(self):
        """Recta geometry must have Width > 0."""
        with pytest.raises(ConfigError, match="Width must be > 0"):
            ECHO2DParams(GeometryType="recta", Width=0.0)

    def test_round_geometry_allows_zero_width(self):
        """Round geometry can have Width=0 (it's ignored)."""
        params = ECHO2DParams(GeometryType="round", Width=0.0)
        assert params.Width == 0.0

    def test_recta_with_positive_width_ok(self):
        """Recta geometry with Width > 0 should validate."""
        params = ECHO2DParams(GeometryType="recta", Width=0.07)
        assert params.Width == 0.07


class TestModeValidation:
    def test_recta_even_modes_warn(self):
        """Recta with even modes should produce a warning."""
        with pytest.warns(UserWarning, match="even modes"):
            ECHO2DParams(
                GeometryType="recta",
                Width=0.07,
                SymmetryCondition="magn",
                Modes=[1, 2, 3],
            )

    def test_recta_odd_modes_no_warn(self):
        """Recta with only odd modes should NOT warn."""
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            ECHO2DParams(
                GeometryType="recta",
                Width=0.07,
                SymmetryCondition="magn",
                Modes=[1, 3, 5, 7],
            )

    def test_round_all_modes_ok(self):
        """Round geometry allows any mode numbers."""
        params = ECHO2DParams(GeometryType="round", Modes=[0, 1, 2])
        assert params.Modes == [0, 1, 2]

    def test_modes_from_string(self):
        """Modes should parse from space-separated string."""
        params = ECHO2DParams(Modes="0 1 2 3")
        assert params.Modes == [0, 1, 2, 3]


class TestMeshResolutionValidation:
    def test_poor_resolution_warns(self):
        """Fewer than 3 mesh points across sigma should warn."""
        with pytest.warns(UserWarning, match="mesh points across bunch sigma"):
            ECHO2DParams(BunchSigma=0.001, StepZ=0.001)

    def test_good_resolution_no_warn(self):
        """Adequate mesh resolution should NOT warn."""
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            ECHO2DParams(BunchSigma=0.001, StepZ=0.0001)


class TestFieldMonitorConfig:
    def test_valid_monitor_component(self):
        """Valid field components should be accepted."""
        fm = FieldMonitorConfig(
            component="Ez",
            time_type="s",
            z0=0.0,
            z1=1.0,
            y0=0.05,
            y1=2.0,
            s0=0.0,
            s1=1.0,
            N=10,
        )
        assert fm.component == "Ez"

    def test_invalid_monitor_component(self):
        """Invalid field components should be rejected."""
        with pytest.raises(ConfigError, match="Field component must be one of"):
            FieldMonitorConfig(
                component="Bx",
                time_type="s",
                z0=0.0,
                z1=1.0,
                y0=0.05,
                y1=2.0,
                s0=0.0,
                s1=1.0,
                N=10,
            )


class TestSerialization:
    def test_minimal_output(self):
        """Minimal params should produce valid output."""
        output = ECHO2DParams().to_input_file()
        assert "GeometryFile=" in output
        assert "GeometryType=round" in output
        assert "BunchSigma=" in output
        assert "Modes=0" in output

    def test_roundtrip(self):
        """Parsing generated output should produce same params."""
        params1 = ECHO2DParams(
            GeometryType="round",
            BunchSigma=0.002,
            Modes=[0, 1],
            MeshLength=100,
            StepY=0.0001,
            StepZ=0.0001,
        )
        output = params1.to_input_file()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(output)

        try:
            params2 = ECHO2DParams.from_input_file(f.name)
            assert params2.GeometryType == params1.GeometryType
            assert params2.BunchSigma == params1.BunchSigma
            assert params2.Modes == params1.Modes
            assert params2.MeshLength == params1.MeshLength
            assert params2.StepZ == params1.StepZ
        finally:
            Path(f.name).unlink(missing_ok=True)


class TestTemplates:
    def test_from_template_round_collimator(self):
        params = ECHO2DParams.from_template("round_collimator")
        assert params.GeometryFile == "round_collimator.txt"
        assert params.GeometryType == "round"
        assert params.Modes == [0]
        assert params.WakeIntMethod == "ind"
        assert params.StepZ == pytest.approx(0.0002)

    def test_from_template_flat_absorber(self):
        params = ECHO2DParams.from_template("flat_absorber")
        assert params.GeometryType == "recta"
        assert params.Width == 0.07
        assert params.Modes == [1, 3, 5, 7, 9, 11, 13, 15]
        assert params.AdjustMesh is False

    def test_from_template_tesla_cavity(self):
        params = ECHO2DParams.from_template("tesla_cavity")
        assert params.GeometryType == "round"
        assert params.Modes == [0, 1]
        assert params.StepY == pytest.approx(0.00019943)

    def test_from_template_dlw(self):
        params = ECHO2DParams.from_template("dlw")
        assert params.Units == "mm"
        assert params.WakeIntMethod == "dir"
        assert params.Modes == [1, 3, 5]
        assert params.Convex is False

    def test_from_template_unknown_raises(self):
        with pytest.raises(ConfigError, match="Unknown template"):
            ECHO2DParams.from_template("does_not_exist")

    def test_list_templates(self):
        templates = ECHO2DParams.list_templates()
        for name in ("round_collimator", "flat_absorber", "tesla_cavity", "dlw"):
            assert name in templates
        assert len(templates) == len(set(templates))


class TestInputFileParsing:
    def test_from_input_file_all_optional_fields(self, tmp_path):
        content = "\n".join(
            [
                "%%%%%%%%%%%%%% geometry %%%%%%%%%%%%%%%%%%%%",
                "GeometryFile=my_geo.txt % trailing comment",
                "Units=mm",
                "GeometryType=recta",
                "Width=0.1",
                "SymmetryCondition=magn",
                "Convex=1",
                "WakeMonitor=10 200 5",
                "BeamMonitor=1 2 3 4",
                "FieldMonitor = Ez z 0.02 0.1 0 0.021 0 1 1",
                "FieldMonitor = { 'Hy' 's' 0.0 0.2 0.0 0.01 0.0 2.0 5 }",
                "DumpField=1",
                "DumpParticles=0",
                "Modes=1 3 5",
                "MeshLength=120",
            ]
        )
        path = tmp_path / "input_in.txt"
        path.write_text(content, encoding="utf-8")

        params = ECHO2DParams.from_input_file(path)

        assert params.GeometryFile == "my_geo.txt"
        assert params.Units == "mm"
        assert params.GeometryType == "recta"
        assert params.Width == 0.1
        assert params.Convex is True
        assert params.WakeMonitor == [10, 200, 5]
        assert params.BeamMonitor == [1, 2, 3, 4]
        assert params.Modes == [1, 3, 5]
        assert params.MeshLength == 120
        assert params.DumpField is True
        assert params.DumpParticles is False

        assert len(params.FieldMonitor) == 2
        fm0 = params.FieldMonitor[0]
        assert fm0.component == "Ez"
        assert fm0.time_type == "z"

        fm1 = params.FieldMonitor[1]
        assert fm1.component == "Hy"
        assert fm1.N == 5

    def test_field_monitor_serialization_roundtrip(self, tmp_path):
        fm = FieldMonitorConfig(
            component="Hx",
            time_type="s",
            z0=0.0,
            z1=1.0,
            y0=0.02,
            y1=3.0,
            s0=0.0,
            s1=1.0,
            N=25,
        )
        params = ECHO2DParams(FieldMonitor=[fm])
        out = params.to_input_file()

        path = tmp_path / "input_in.txt"
        path.write_text(out, encoding="utf-8")

        parsed = ECHO2DParams.from_input_file(path)
        assert len(parsed.FieldMonitor) == 1

        got = parsed.FieldMonitor[0]
        assert got.component == fm.component
        assert got.time_type == fm.time_type
        assert got.z0 == fm.z0
        assert got.z1 == fm.z1
        assert got.y1 == fm.y1
        assert got.s1 == fm.s1
        assert got.N == fm.N


class TestModeEdgeCases:
    def test_modes_non_integer_string_rejected(self):
        with pytest.raises(ValidationError):
            ECHO2DParams(Modes="0 1 1.5")

    def test_modes_negative_values_accepted(self):
        params = ECHO2DParams(Modes=[-1, 0, 2])
        assert params.Modes == [-1, 0, 2]


class TestConfigDiff:
    """Tests for ``echo2d config diff``."""

    def test_identical_files_no_differences(self, tmp_path):
        """Two identical files report 'No differences found'."""
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        content = "\n".join(
            [
                "%%%%%%%%%%%%%% geometry %%%%%%%%%%%%%%%%%%%%",
                "GeometryFile=geo.txt",
                "BunchSigma=0.001",
                "Modes=0 1",
                "",
            ]
        )
        f1.write_text(content, encoding="utf-8")
        f2.write_text(content, encoding="utf-8")

        result = runner.invoke(app, ["config", "diff", str(f1), str(f2)])
        assert result.exit_code == 0, result.exception
        assert "No differences found" in result.output

    def test_changed_parameter_shows_both_values(self, tmp_path):
        """A single changed parameter shows both old and new values."""
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("BunchSigma=0.001\n", encoding="utf-8")
        f2.write_text("BunchSigma=0.002\n", encoding="utf-8")

        result = runner.invoke(app, ["config", "diff", str(f1), str(f2)])
        assert result.exit_code == 0, result.exception
        assert "BunchSigma" in result.output
        assert "0.001" in result.output
        assert "0.002" in result.output

    def test_param_only_in_file1_shows_as_added(self, tmp_path):
        """A parameter present only in file1 is still shown as a row."""
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("BunchSigma=0.001\nModes=0 1\n", encoding="utf-8")
        f2.write_text("BunchSigma=0.001\n", encoding="utf-8")

        result = runner.invoke(app, ["config", "diff", str(f1), str(f2)])
        assert result.exit_code == 0, result.exception
        assert "Modes" in result.output
        assert "0 1" in result.output

    def test_file_not_found_error(self, tmp_path):
        """A missing file produces an error and a non-zero exit code."""
        missing = str(tmp_path / "does_not_exist.txt")
        result = runner.invoke(app, ["config", "diff", missing, missing])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()
