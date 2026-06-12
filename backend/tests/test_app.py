"""Unit tests for the pure helpers in app.py (no subprocess / engine launch)."""
from pathlib import Path

import app


def test_resolve_gadgets_maps_customize_keys_to_existing_lua():
    # 'prioritize_target' ships as db/rule/codes/prioritize_target.lua;
    # the bogus key must be silently skipped, not raise.
    cfg = {"customize": {"prioritize_target": {}, "nonexistent_gadget": {}}}
    names = [Path(g).name for g in app._resolve_gadgets(cfg)]
    assert "prioritize_target.lua" in names
    assert all("nonexistent_gadget" not in n for n in names)


def test_resolve_gadgets_handles_empty_or_missing_customize():
    assert app._resolve_gadgets({}) == []
    assert app._resolve_gadgets({"customize": {}}) == []
    assert app._resolve_gadgets({"customize": None}) == []


def test_resolve_gadgets_returns_absolute_existing_paths():
    for path in app._resolve_gadgets({"customize": {"prioritize_target": {}}}):
        assert Path(path).is_file()


def test_launch_request_defaults_to_gadget_mode():
    req = app.LaunchRequest(config={"information": {"map_name": "BarR 1.1"}})
    assert req.mode == "gadget"


def test_load_json_returns_default_on_missing_file(tmp_path):
    assert app._load_json(tmp_path / "missing.json", {"fallback": True}) == {"fallback": True}
