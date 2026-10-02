"""REWORK-3 tests: collision handling preserves retryable pending state.

A refused collision (existing destination) must never overwrite, must leave the
source intact, and must preserve the exact pending state so a later retry (after
the destination conflict is resolved) succeeds — for deferred helpers, for the
immediate ``perform_analysis`` SNR branch and the immediate trail branch.
"""
from __future__ import annotations

import os
from concurrent.futures import Future
from pathlib import Path

import numpy as np
import pytest
from astropy.io import fits

from zeanalyser import analyse_logic, trail_module


def _row(name, path, reason, action):
    return {
        "file": name,
        "path": str(path),
        "status": "ok",
        "rejected_reason": reason,
        "action": action,
        "action_comment": "",
    }


_NOOP = lambda *a, **k: None


REJECT_CASES = [
    ("snr", "low_snr_pending_action", "pending_snr_action", "moved_snr"),
    ("trail", "trail_pending_action", "pending_trail_action", "moved_trail"),
    ("reco", "not_in_recommendation", "pending_reco_action", "moved_reco"),
]

HELPERS = {
    "snr": analyse_logic.apply_pending_snr_actions,
    "trail": analyse_logic.apply_pending_trail_actions,
    "reco": analyse_logic.apply_pending_reco_actions,
}


# ---------------------------------------------------------------------------
# Deferred collision: pending preserved, then retry succeeds
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("helper_name,reason,pending_action,moved_action", REJECT_CASES)
def test_deferred_collision_preserves_pending_then_retry(
    tmp_path, helper_name, reason, pending_action, moved_action
):
    helper = HELPERS[helper_name]
    root = tmp_path / "project"
    root.mkdir()
    reject_dir = tmp_path / "reject"
    reject_dir.mkdir()

    f = root / "light.fit"
    f.write_text("source-content")
    existing = reject_dir / "light.fit"
    existing.write_text("existing-content")

    rows = [_row("light.fit", f, reason, pending_action)]

    # First attempt: collision, refused, pending preserved.
    assert helper(rows, str(reject_dir), False, True, _NOOP, _NOOP, _NOOP, str(root)) == 0
    assert f.exists() and f.read_text() == "source-content"
    assert existing.read_text() == "existing-content"
    assert rows[0]["action"] == pending_action
    assert rows[0]["rejected_reason"] == reason
    assert "Collision" in rows[0]["action_comment"]

    # Resolve the conflict, retry: the move now succeeds.
    existing.unlink()
    assert helper(rows, str(reject_dir), False, True, _NOOP, _NOOP, _NOOP, str(root)) == 1
    assert not f.exists()
    assert (reject_dir / "light.fit").read_text() == "source-content"
    assert rows[0]["action"] == moved_action


# ---------------------------------------------------------------------------
# already-in-destination: no nesting, second click 0
# ---------------------------------------------------------------------------

def test_already_destination_no_nesting_and_idempotent(tmp_path):
    from zeanalyser.path_safety import resolve_reject_destination

    root = tmp_path / "project"
    root.mkdir()
    reject_dir = root / "rejected_low_snr"
    reject_dir.mkdir()
    f = root / "light.fit"
    f.write_text("content")

    # A source already inside the reject dir resolves to itself (no re-nesting).
    already = resolve_reject_destination(
        str(reject_dir / "light.fit"), str(reject_dir), str(root)
    )
    assert already == str(reject_dir / "light.fit")
    assert "rejected_low_snr/rejected_low_snr" not in already

    # Normal deferred move, then a second click finds nothing to do.
    rows = [_row("light.fit", f, "low_snr_pending_action", "pending_snr_action")]
    assert analyse_logic.apply_pending_snr_actions(
        rows, str(reject_dir), False, True, _NOOP, _NOOP, _NOOP, str(root)) == 1
    assert rows[0]["action"] == "moved_snr"
    # second click: 0 actions (row is no longer pending)
    assert analyse_logic.apply_pending_snr_actions(
        rows, str(reject_dir), False, True, _NOOP, _NOOP, _NOOP, str(root)) == 0


# ---------------------------------------------------------------------------
# Symlink source outside root: refused, no move
# ---------------------------------------------------------------------------

def test_symlink_source_outside_root_refused(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    outside = tmp_path / "outside.fit"
    outside.write_text("outside")
    link = root / "linked.fit"
    link.symlink_to(outside)
    reject_dir = tmp_path / "reject"

    rows = [_row("linked.fit", link, "low_snr_pending_action", "pending_snr_action")]
    count = analyse_logic.apply_pending_snr_actions(
        rows, str(reject_dir), False, True, _NOOP, _NOOP, _NOOP, str(root))

    assert count == 0
    assert outside.exists()
    assert rows[0]["action"] == "skipped_outside_project"
    assert not (reject_dir / "linked.fit").exists()


# ---------------------------------------------------------------------------
# Summary + last JSON stays honest after a collision
# ---------------------------------------------------------------------------

def test_collision_pending_reflected_in_summary_json(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    reject_dir = root / "rejected_low_snr"
    reject_dir.mkdir()
    f = root / "light.fit"
    f.write_text("source")
    existing = reject_dir / "light.fit"
    existing.write_text("existing")

    rows = [_row("light.fit", f, "low_snr_pending_action", "pending_snr_action")]
    analyse_logic.apply_pending_snr_actions(
        rows, str(reject_dir), False, True, _NOOP, _NOOP, _NOOP, str(root))

    log_path = root / "analyse_resultats.log"
    options = {
        "move_rejected": True, "delete_rejected": False, "analyze_snr": True,
        "detect_trails": False, "include_subfolders": False,
        "snr_reject_dir": str(reject_dir), "trail_reject_dir": "",
        "reco_reject_dir": None, "snr_selection_mode": "percent",
        "snr_selection_value": "80", "trail_params": {},
    }
    analyse_logic.write_log_summary(str(log_path), str(root), options, results_list=rows)

    text = log_path.read_text(encoding="utf-8")
    # the row is still pending (not counted as moved/kept with no reason)
    assert "Images marquées pour rejet (faible SNR): 0" in text
    loaded = analyse_logic.write_log_summary  # noqa: just confirm module import path
    from zeanalyser import project_state
    loaded_rows = project_state.load_latest_valid_visualization_block(str(log_path))
    assert loaded_rows is not None
    rec = loaded_rows[0]
    assert rec["rejected_reason"] == "low_snr_pending_action"
    assert rec["action"] == "pending_snr_action"


# ---------------------------------------------------------------------------
# Immediate SNR collision via perform_analysis
# ---------------------------------------------------------------------------

def _snr_ok_result(path):
    return {
        "path": path,
        "snr": 20.0, "sky_bg": 1.0, "sky_noise": 1.0, "signal_pixels": 10,
        "starcount": 5, "starcount_outcome": "ok", "starcount_error": None,
        "exposure": 10.0, "filter": "LP", "temperature": 0.0, "eqmode": 2,
        "sitelong": None, "sitelat": None, "telescope": "Seestar",
        "date_obs": "2026-09-14T00:00:00", "error": None, "fwhm": 2.0,
        "ecc": 0.5, "n_star_ecc": 5, "fwhm_ecc_outcome": "ok",
        "fwhm_ecc_error": None, "ra": None, "dec": None,
    }


class _ImmediateSNRExecutor:
    def __init__(self, **_kw):
        pass
    def __enter__(self):
        return self
    def __exit__(self, *_a):
        return False
    def submit(self, _fn, path):
        f = Future()
        f.set_result(_snr_ok_result(path))
        return f
    def shutdown(self, wait=True, *, cancel_futures=False):
        return None


def _callbacks(logs=None):
    logs = logs if logs is not None else []
    return {
        "is_cancelled": lambda: False,
        "progress": lambda *_a, **_k: None,
        "status": lambda *_a, **_k: None,
        "log": lambda key, **kw: logs.append((key, kw)),
    }


def test_immediate_snr_collision_preserves_pending_then_retry(tmp_path, monkeypatch):
    fits_path = tmp_path / "light.fit"
    fits.PrimaryHDU(data=np.zeros((8, 8), dtype=np.float32)).writeto(str(fits_path))
    reject_dir = tmp_path / "rejected_low_snr"
    reject_dir.mkdir()
    existing = reject_dir / "light.fit"
    existing.write_text("existing-content")

    monkeypatch.setattr(
        analyse_logic.concurrent.futures, "ProcessPoolExecutor", _ImmediateSNRExecutor)

    options = {
        "include_subfolders": False,
        "analyze_snr": True,
        "detect_trails": False,
        "move_rejected": True,
        "delete_rejected": False,
        "use_bortle": False,
        "analyse_fwhm": False,
        "analyse_ecc": False,
        "output_root": str(tmp_path),
        "snr_selection_mode": "threshold",
        "snr_selection_value": "50",  # 20 < 50 => rejected
        "apply_snr_action_immediately": True,
        "snr_reject_dir": str(reject_dir),
    }

    rows = analyse_logic.perform_analysis(
        str(tmp_path), str(tmp_path / "analyse_resultats.log"), options, _callbacks())

    assert len(rows) == 1
    row = rows[0]
    # collision: no overwrite, source intact, retryable pending state
    assert fits_path.exists()
    assert existing.read_text() == "existing-content"
    assert row["rejected_reason"] == "low_snr_pending_action"
    assert row["action"] == "pending_snr_action"
    assert row["status"] == "ok"

    # retry after resolving the conflict
    existing.unlink()
    assert analyse_logic.apply_pending_snr_actions(
        rows, str(reject_dir), False, True, _NOOP, _NOOP, _NOOP, str(tmp_path)) == 1
    assert not fits_path.exists()
    assert (reject_dir / "light.fit").exists()


# ---------------------------------------------------------------------------
# Immediate trail collision via perform_analysis (fake acstools)
# ---------------------------------------------------------------------------

class _FakeSatdet:
    def __init__(self, results, errors):
        self.results = dict(results)
        self.errors = dict(errors)

    def detsat(self, searchpattern, **kwargs):
        out = {k: v for k, v in self.results.items() if k[0] == searchpattern}
        err = {k: v for k, v in self.errors.items() if k[0] == searchpattern}
        return out, err


class _ImmediateTrailExecutor:
    def __init__(self, max_workers=None):
        pass
    def __enter__(self):
        return self
    def __exit__(self, *_a):
        return False
    def submit(self, fn, *args, **kwargs):
        f = Future()
        f.set_result(fn(*args, **kwargs))
        return f
    def shutdown(self, wait=True, *, cancel_futures=False):
        return None


def _patch_trail_available(monkeypatch):
    monkeypatch.setattr(trail_module, "SATDET_AVAILABLE", True)
    monkeypatch.setattr(trail_module, "SATDET_USES_SEARCHPATTERN", True)
    monkeypatch.setattr(trail_module, "SCIPY_AVAILABLE", True)
    monkeypatch.setattr(trail_module, "SKIMAGE_AVAILABLE", True)
    monkeypatch.setattr(analyse_logic, "SATDET_AVAILABLE", True)
    monkeypatch.setattr(analyse_logic, "TRAIL_MODULE_LOADED", True)


def test_immediate_trail_collision_preserves_pending(tmp_path, monkeypatch):
    pos = tmp_path / "pos.fit"
    fits.PrimaryHDU(data=np.zeros((8, 8), dtype=np.float32)).writeto(str(pos))
    reject_dir = tmp_path / "rejected_trails"
    reject_dir.mkdir()
    existing = reject_dir / "pos.fit"
    existing.write_text("existing-content")

    results = {(str(pos), 0): [[[10.0, 20.0], [30.0, 40.0]]]}
    errors = {}
    fake = _FakeSatdet(results, errors)
    monkeypatch.setattr(trail_module, "satdet", fake)
    _patch_trail_available(monkeypatch)
    monkeypatch.setattr(analyse_logic.concurrent.futures, "ProcessPoolExecutor", _ImmediateSNRExecutor)
    monkeypatch.setattr(analyse_logic.concurrent.futures, "ThreadPoolExecutor", _ImmediateTrailExecutor)

    options = {
        "include_subfolders": False,
        "analyze_snr": False,
        "detect_trails": True,
        "move_rejected": True,
        "delete_rejected": False,
        "use_bortle": False,
        "analyse_fwhm": False,
        "analyse_ecc": False,
        "output_root": str(tmp_path),
        "trail_params": {"low_thresh": 0.1, "h_thresh": 0.5},
        "trail_reject_dir": str(reject_dir),
        "apply_trail_action_immediately": True,
    }

    rows = analyse_logic.perform_analysis(
        str(tmp_path), str(tmp_path / "analyse_resultats.log"), options, _callbacks())

    row = [r for r in rows if r["file"] == "pos.fit"][0]
    # collision: source intact, no overwrite, retryable pending trail state
    assert pos.exists()
    assert existing.read_text() == "existing-content"
    assert row["rejected_reason"] == "trail_pending_action"
    assert row["action"] == "pending_trail_action"
    assert row["status"] == "ok"

    # retry after resolving the conflict
    existing.unlink()
    assert analyse_logic.apply_pending_trail_actions(
        rows, str(reject_dir), False, True, _NOOP, _NOOP, _NOOP, str(tmp_path)) == 1
    assert not pos.exists()
    assert (reject_dir / "pos.fit").exists()
