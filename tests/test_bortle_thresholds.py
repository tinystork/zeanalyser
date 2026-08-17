"""Unit tests for bortle threshold loading (read-only, user override)."""

import json
import os

import zeanalyser.bortle_utils as bu


def _write_user_override(base_dir, values):
    """Create $base/ZeAnalyser/bortle_thresholds.json and return its path."""
    path = os.path.join(base_dir, "ZeAnalyser", "bortle_thresholds.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(values, f)
    return path


def test_user_override_wins_over_package_resource(monkeypatch, tmp_path):
    override = {"1": 20.0, "2": 19.0, "9": 0.0}
    _write_user_override(str(tmp_path), override)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    result = bu._load_thresholds()

    assert result == {int(k): float(v) for k, v in override.items()}
    assert all(isinstance(k, int) and isinstance(v, float) for k, v in result.items())


def test_package_resource_fallback_is_read_only(monkeypatch, tmp_path):
    # No user override anywhere: XDG_CONFIG_HOME points to an empty dir.
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "empty-config"))

    pkg_dir = os.path.dirname(bu.__file__)
    pkg_resource = os.path.join(pkg_dir, "bortle_thresholds.json")
    assert os.path.isfile(pkg_resource), "package resource must be shipped beside the module"

    before_files = set(os.listdir(pkg_dir))
    result = bu._load_thresholds()

    with open(pkg_resource, "r", encoding="utf-8") as f:
        expected = {int(k): float(v) for k, v in json.load(f).items()}
    assert result == expected
    assert all(isinstance(k, int) and isinstance(v, float) for k, v in result.items())

    # No writes: no user override generated, nothing added in the package dir.
    assert not os.path.exists(os.path.join(str(tmp_path / "empty-config"), "ZeAnalyser"))
    assert set(os.listdir(pkg_dir)) == before_files

    # Public constant keeps its {int: float} signature.
    assert all(isinstance(k, int) and isinstance(v, float) for k, v in bu.THRESHOLDS.items())
