"""User-level persistent configuration (~/.echo2d/config.yaml).

Simplest possible key-value store for CLI preferences.
"""

from __future__ import annotations

from pathlib import Path

import yaml  # type: ignore[import-untyped]

_CONFIG_DIR = Path.home() / ".echo2d"
_CONFIG_FILE = _CONFIG_DIR / "config.yaml"

_DEFAULTS = {
    "backend": "pyqtgraph",
}


def _ensure_dir() -> None:
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load() -> dict:
    """Load user config, merging with defaults. Returns full dict."""
    if not _CONFIG_FILE.is_file():
        return dict(_DEFAULTS)
    try:
        data = yaml.safe_load(_CONFIG_FILE.read_text(encoding="utf-8")) or {}
    except Exception:
        data = {}
    merged = dict(_DEFAULTS)
    merged.update({k: v for k, v in data.items() if k in _DEFAULTS})
    return merged


def get(key: str) -> str:
    """Read a single config value."""
    return str(load().get(key, _DEFAULTS.get(key, "")))


def set_(key: str, value: str) -> None:
    """Write a single config value."""
    _ensure_dir()
    data = yaml.safe_load(_CONFIG_FILE.read_text(encoding="utf-8")) if _CONFIG_FILE.is_file() else {}
    data[key] = value
    _CONFIG_FILE.write_text(yaml.dump(data, default_flow_style=False), encoding="utf-8")


def list_all() -> dict:
    """Return all current settings with values."""
    return load()
