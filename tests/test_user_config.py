"""Unit tests for pyecho.user_config — persistent user settings."""

from __future__ import annotations

import pytest
from pyecho import user_config


class TestDefaults:
    def test_load_returns_defaults_when_no_file(self, monkeypatch):
        monkeypatch.setattr(user_config, "_CONFIG_FILE",
                            user_config._CONFIG_DIR / "nonexistent_test.yaml")
        cfg = user_config.load()
        assert cfg["backend"] == "pyqtgraph"

    def test_default_backend_is_pyqtgraph(self):
        assert user_config._DEFAULTS["backend"] == "pyqtgraph"

    def test_load_merges_partial_data(self, tmp_path, monkeypatch):
        f = tmp_path / "config.yaml"
        f.write_text("backend: matplotlib\n", encoding="utf-8")
        monkeypatch.setattr(user_config, "_CONFIG_FILE", f)
        cfg = user_config.load()
        assert cfg["backend"] == "matplotlib"

    def test_load_handles_corrupt_yaml(self, tmp_path, monkeypatch):
        f = tmp_path / "config.yaml"
        f.write_text(": : : bad yaml : :", encoding="utf-8")
        monkeypatch.setattr(user_config, "_CONFIG_FILE", f)
        cfg = user_config.load()
        assert cfg["backend"] == "pyqtgraph"  # falls back to default


class TestGet:
    def test_get_returns_default_for_missing_key(self, monkeypatch):
        monkeypatch.setattr(user_config, "_CONFIG_FILE",
                            user_config._CONFIG_DIR / "nonexistent_test.yaml")
        assert user_config.get("backend") == "pyqtgraph"

    def test_get_unknown_key_returns_empty(self):
        assert user_config.get("nonexistent") == ""


class TestSet:
    def test_set_and_read_back(self, tmp_path, monkeypatch):
        f = tmp_path / "config.yaml"
        monkeypatch.setattr(user_config, "_CONFIG_FILE", f)
        user_config.set_("backend", "matplotlib")
        assert user_config.get("backend") == "matplotlib"
        # Reread from disk
        assert f.read_text(encoding="utf-8").strip() == "backend: matplotlib"

    def test_set_creates_parent_dir(self, tmp_path, monkeypatch):
        d = tmp_path / "sub" / "nested"
        f = d / "config.yaml"
        monkeypatch.setattr(user_config, "_CONFIG_DIR", d)
        monkeypatch.setattr(user_config, "_CONFIG_FILE", f)
        user_config.set_("backend", "pyqtgraph")
        assert f.is_file()

    def test_set_overwrites_existing(self, tmp_path, monkeypatch):
        f = tmp_path / "config.yaml"
        f.write_text("backend: matplotlib\n", encoding="utf-8")
        monkeypatch.setattr(user_config, "_CONFIG_FILE", f)
        user_config.set_("backend", "pyqtgraph")
        assert user_config.get("backend") == "pyqtgraph"


class TestListAll:
    def test_list_all_returns_merged_defaults(self, monkeypatch):
        monkeypatch.setattr(user_config, "_CONFIG_FILE",
                            user_config._CONFIG_DIR / "nonexistent_test.yaml")
        cfg = user_config.list_all()
        assert isinstance(cfg, dict)
        assert "backend" in cfg
        assert cfg["backend"] == "pyqtgraph"
