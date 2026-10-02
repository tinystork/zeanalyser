"""Regression tests for recommendation/reject category isolation (3.5.0 fix).

The apply-recommendations path used to merge "not in recommendation" images
into the low-SNR reject directory and never applied trail actions. These tests
lock in the strict category separation:

* Apply SNR      -> only ``low_snr_pending_action`` -> snr reject dir
* Apply trails   -> only ``trail_pending_action``  -> trail reject dir
* Apply reco     -> only ``not_in_recommendation`` -> dedicated ``rejected_recommendations`` dir
* Organize all   -> every category to its own destination, no double move
* Preview/confirm with cancel => zero mutation, no auto-apply without consent
"""
import json
import os

import pytest

from zeanalyser import analyse_logic, analyse_gui, analysis_schema, project_state
import zeanalyser.analyse_gui_qt as mod


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


# ---------------------------------------------------------------------------
# resolve_reco_reject_dir
# ---------------------------------------------------------------------------

def test_resolve_reco_reject_dir_defaults_to_dedicated():
    assert analyse_logic.resolve_reco_reject_dir(None, "/in") == (
        os.path.join("/in", "rejected_recommendations")
    )
    assert analyse_logic.resolve_reco_reject_dir("/x/y", "/in") == "/x/y"
    assert analyse_logic.resolve_reco_reject_dir("", "/in") == (
        os.path.join("/in", "rejected_recommendations")
    )
    assert analyse_logic.resolve_reco_reject_dir(None, None) is None


def test_resolve_reco_reject_dir_never_snr_dir():
    # The dedicated dir must never equal the low-SNR dir default.
    reco = analyse_logic.resolve_reco_reject_dir(None, "/in")
    assert os.path.basename(reco) == "rejected_recommendations"
    assert reco != os.path.join("/in", "rejected_low_snr")


# ---------------------------------------------------------------------------
# recommendation_failure_breakdown
# ---------------------------------------------------------------------------

def _kept(snr, fwhm, ecc, starcount):
    return {
        "file": f"img_{snr}_{fwhm}_{ecc}_{starcount}.fits",
        "status": "ok",
        "action": "kept",
        "rejected_reason": None,
        "snr": snr,
        "fwhm": fwhm,
        "ecc": ecc,
        "starcount": starcount,
    }


def test_recommendation_failure_breakdown_single_and_overlap():
    rows = [
        _kept(5.0, 1.0, 0.5, 100),   # fails snr only
        _kept(30.0, 3.0, 0.5, 100),  # fails fwhm only
        _kept(30.0, 1.0, 0.9, 100),  # fails ecc only
        _kept(5.0, 3.0, 0.9, 10),    # fails snr+fwhm+ecc+starcount => overlap
        _kept(30.0, 1.0, 0.5, 100),  # passes all => none
    ]
    bd = analyse_logic.recommendation_failure_breakdown(
        rows, snr_min=10.0, fwhm_max=2.0, ecc_max=0.8,
        starcount_min=20, use_starcount=True,
    )
    assert bd["snr"] == 1
    assert bd["fwhm"] == 1
    assert bd["ecc"] == 1
    assert bd["starcount"] == 0
    assert bd["overlap"] == 1
    assert bd["none"] == 1


def test_recommendation_failure_breakdown_ignores_non_kept():
    rows = [
        _kept(5.0, 1.0, 0.5, 100),
        {
            "file": "err.fits", "status": "error", "action": "kept",
            "rejected_reason": None, "snr": 1.0, "fwhm": 9.0,
            "ecc": 9.0, "starcount": 1,
        },
    ]
    bd = analyse_logic.recommendation_failure_breakdown(
        rows, snr_min=10.0, fwhm_max=2.0, ecc_max=0.8,
        starcount_min=20, use_starcount=True,
    )
    assert bd["snr"] == 1
    assert sum(bd.values()) == 1


# ---------------------------------------------------------------------------
# Category isolation at the logic layer
# ---------------------------------------------------------------------------

def test_category_isolation_snr_trail_reco(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    snr_dir = tmp_path / "rejected_low_snr"
    trail_dir = tmp_path / "rejected_satellite_trails"
    reco_dir = tmp_path / "rejected_recommendations"

    snr_file = root / "snr.fits"
    trail_file = root / "trail.fits"
    reco_file = root / "reco.fits"
    kept_file = root / "kept.fits"
    for f in (snr_file, trail_file, reco_file, kept_file):
        f.touch()

    rows = [
        _row("snr.fits", snr_file, "low_snr_pending_action", "pending_snr_action"),
        _row("trail.fits", trail_file, "trail_pending_action", "pending_trail_action"),
        _row("reco.fits", reco_file, "not_in_recommendation", "pending_reco_action"),
        _row("kept.fits", kept_file, None, "kept"),
    ]

    assert analyse_logic.apply_pending_snr_actions(
        rows, str(snr_dir), False, True, _NOOP, _NOOP, _NOOP, str(root)
    ) == 1
    assert (snr_dir / "snr.fits").exists()
    assert trail_file.exists() and reco_file.exists()

    assert analyse_logic.apply_pending_trail_actions(
        rows, str(trail_dir), False, True, _NOOP, _NOOP, _NOOP, str(root)
    ) == 1
    assert (trail_dir / "trail.fits").exists()

    assert analyse_logic.apply_pending_reco_actions(
        rows, str(reco_dir), False, True, _NOOP, _NOOP, _NOOP, str(root)
    ) == 1
    assert (reco_dir / "reco.fits").exists()

    # Strict separation: no file landed in a foreign directory.
    assert not (trail_dir / "snr.fits").exists()
    assert not (reco_dir / "snr.fits").exists()
    assert not (snr_dir / "trail.fits").exists()
    assert not (reco_dir / "trail.fits").exists()
    assert not (snr_dir / "reco.fits").exists()
    assert not (trail_dir / "reco.fits").exists()
    assert kept_file.exists()


def test_organize_all_three_destinations_no_double_move(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    snr_dir = tmp_path / "snr"
    trail_dir = tmp_path / "trail"
    reco_dir = tmp_path / "reco"
    snr_file = root / "snr.fits"
    trail_file = root / "trail.fits"
    reco_file = root / "reco.fits"
    for f in (snr_file, trail_file, reco_file):
        f.touch()

    rows = [
        _row("snr.fits", snr_file, "low_snr_pending_action", "pending_snr_action"),
        _row("trail.fits", trail_file, "trail_pending_action", "pending_trail_action"),
        _row("reco.fits", reco_file, "not_in_recommendation", "pending_reco_action"),
    ]

    total = 0
    total += analyse_logic.apply_pending_snr_actions(
        rows, str(snr_dir), False, True, _NOOP, _NOOP, _NOOP, str(root))
    total += analyse_logic.apply_pending_reco_actions(
        rows, str(reco_dir), False, True, _NOOP, _NOOP, _NOOP, str(root))
    total += analyse_logic.apply_pending_trail_actions(
        rows, str(trail_dir), False, True, _NOOP, _NOOP, _NOOP, str(root))

    assert total == 3
    assert (snr_dir / "snr.fits").exists()
    assert (trail_dir / "trail.fits").exists()
    assert (reco_dir / "reco.fits").exists()
    # no double move
    for dest in (trail_dir, reco_dir):
        assert not (dest / "snr.fits").exists()
    for dest in (snr_dir, reco_dir):
        assert not (dest / "trail.fits").exists()
    for dest in (snr_dir, trail_dir):
        assert not (dest / "reco.fits").exists()


def test_trails_stay_pending_after_reco_then_move(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    reco_dir = root / "rejected_recommendations"
    trail_dir = root / "rejected_satellite_trails"
    reco_file = root / "reco.fits"
    trail_file = root / "trail.fits"
    reco_file.touch()
    trail_file.touch()

    rows = [
        _row("reco.fits", reco_file, "not_in_recommendation", "pending_reco_action"),
        _row("trail.fits", trail_file, "trail_pending_action", "pending_trail_action"),
    ]

    # Apply recommendations only: trail stays pending, untouched.
    assert analyse_logic.apply_pending_reco_actions(
        rows, str(reco_dir), False, True, _NOOP, _NOOP, _NOOP, str(root)) == 1
    assert trail_file.exists()
    assert rows[1]["rejected_reason"] == "trail_pending_action"

    # Then apply trails: it moves.
    assert analyse_logic.apply_pending_trail_actions(
        rows, str(trail_dir), False, True, _NOOP, _NOOP, _NOOP, str(root)) == 1
    assert (trail_dir / "trail.fits").exists()


def test_reco_apply_idempotent_second_click(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    reco_dir = root / "rejected_recommendations"
    f = root / "bad.fits"
    f.touch()
    rows = [_row("bad.fits", f, "not_in_recommendation", "pending_reco_action")]

    assert analyse_logic.apply_pending_reco_actions(
        rows, str(reco_dir), False, True, _NOOP, _NOOP, _NOOP, str(root)) == 1
    # Second application finds no pending reco action -> 0 actions, no error.
    assert analyse_logic.apply_pending_reco_actions(
        rows, str(reco_dir), False, True, _NOOP, _NOOP, _NOOP, str(root)) == 0
    assert rows[0].get("status") == "processed_action"
    assert rows[0].get("status") != "error"


def test_persistence_reload_matches_filesystem(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    reco_dir = root / "rejected_recommendations"
    f = root / "bad.fits"
    f.touch()
    rows = [_row("bad.fits", f, "not_in_recommendation", "pending_reco_action")]

    analyse_logic.apply_pending_reco_actions(
        rows, str(reco_dir), False, True, _NOOP, _NOOP, _NOOP, str(root))

    log_path = root / "analyse_resultats.log"
    options = {
        "move_rejected": True,
        "delete_rejected": False,
        "analyze_snr": True,
        "detect_trails": False,
        "include_subfolders": False,
        "snr_reject_dir": str(root / "rejected_low_snr"),
        "trail_reject_dir": str(root / "rejected_satellite_trails"),
        "reco_reject_dir": str(reco_dir),
        "snr_selection_mode": "percent",
        "snr_selection_value": "80",
        "trail_params": {},
    }
    assert analyse_logic.write_log_summary(
        str(log_path), str(root), options, results_list=rows)

    loaded = project_state.load_latest_valid_visualization_block(str(log_path))
    assert loaded is not None
    moved = [r for r in loaded if r.get("action") == "moved_reco"]
    assert len(moved) == 1
    assert moved[0].get("file") == "bad.fits"
    assert moved[0].get("rejected_reason") == "not_in_recommendation"


# ---------------------------------------------------------------------------
# Qt GUI: dedicated dir + confirmation (cancel => zero mutation)
# ---------------------------------------------------------------------------

_NOOP_CALLBACKS = {
    "log": lambda *a, **k: None,
    "status": lambda *a, **k: None,
    "progress": lambda *a, **k: None,
}


@pytest.mark.skipif(mod.QApplication is object, reason="PySide6 not available")
def test_qt_apply_reco_moves_to_dedicated_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    created_app = False
    app = mod.QApplication.instance()
    if app is None:
        app = mod.QApplication([])
        created_app = True

    win = mod.ZeAnalyserMainWindow()
    root = tmp_path / "project"
    root.mkdir()
    good = root / "good.fits"
    bad = root / "bad.fits"
    good.touch()
    bad.touch()

    rows = [
        {"file": "good.fits", "path": str(good), "status": "ok", "action": "kept",
         "rejected_reason": None, "snr": 30.0, "fwhm": 1.0, "ecc": 0.5, "starcount": 100},
        {"file": "bad.fits", "path": str(bad), "status": "ok", "action": "kept",
         "rejected_reason": None, "snr": 5.0, "fwhm": 3.0, "ecc": 0.9, "starcount": 10},
    ]
    win.analysis_results = rows
    win.recommended_images = [rows[0]]

    snr_dir = tmp_path / "rejected_low_snr"
    opts = {
        "input_path": str(root),
        "move_rejected": True,
        "delete_rejected": False,
        "snr_reject_dir": str(snr_dir),
        "reco_reject_dir": "",
    }
    monkeypatch.setattr(win, "_build_options_from_ui", lambda: opts)
    monkeypatch.setattr(win, "_build_logic_callbacks", lambda *a, **k: _NOOP_CALLBACKS)
    monkeypatch.setattr(win, "_confirm_recommendations_apply", lambda **kw: True)
    monkeypatch.setattr(win, "_persist_actions_state", lambda *a, **k: None)

    try:
        win._apply_recommendations_gui(recommended=[rows[0]], auto=False)
        # Moved to dedicated dir, NOT the low-SNR dir.
        assert (root / "rejected_recommendations" / "bad.fits").exists()
        assert not (snr_dir / "bad.fits").exists()
        assert good.exists()
    finally:
        try:
            win.close()
        except Exception:
            pass
        if created_app:
            app.quit()


@pytest.mark.skipif(mod.QApplication is object, reason="PySide6 not available")
def test_qt_apply_reco_cancel_zero_mutation(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    created_app = False
    app = mod.QApplication.instance()
    if app is None:
        app = mod.QApplication([])
        created_app = True

    win = mod.ZeAnalyserMainWindow()
    root = tmp_path / "project"
    root.mkdir()
    good = root / "good.fits"
    bad = root / "bad.fits"
    good.touch()
    bad.touch()

    rows = [
        {"file": "good.fits", "path": str(good), "status": "ok", "action": "kept",
         "rejected_reason": None, "snr": 30.0, "fwhm": 1.0, "ecc": 0.5, "starcount": 100},
        {"file": "bad.fits", "path": str(bad), "status": "ok", "action": "kept",
         "rejected_reason": None, "snr": 5.0, "fwhm": 3.0, "ecc": 0.9, "starcount": 10},
    ]
    win.analysis_results = rows
    win.recommended_images = [rows[0]]

    opts = {
        "input_path": str(root),
        "move_rejected": True,
        "delete_rejected": False,
        "snr_reject_dir": str(tmp_path / "rejected_low_snr"),
        "reco_reject_dir": "",
    }
    monkeypatch.setattr(win, "_build_options_from_ui", lambda: opts)
    monkeypatch.setattr(win, "_build_logic_callbacks", lambda *a, **k: _NOOP_CALLBACKS)
    monkeypatch.setattr(win, "_confirm_recommendations_apply", lambda **kw: False)
    monkeypatch.setattr(win, "_persist_actions_state", lambda *a, **k: None)

    try:
        win._apply_recommendations_gui(recommended=[rows[0]], auto=False)
        # Cancel => zero mutation, no dedicated dir created.
        assert good.exists() and bad.exists()
        assert not (root / "rejected_recommendations").exists()
    finally:
        try:
            win.close()
        except Exception:
            pass
        if created_app:
            app.quit()


def _stub_var(value):
    class _Var:
        def get(self):
            return value

    return _Var()


# ---------------------------------------------------------------------------
# REWORK-1: canonical identity (no basename conflation)
# ---------------------------------------------------------------------------

def test_resolve_row_abs_path_no_basename_conflation():
    a = analysis_schema.resolve_row_abs_path({"path": "/root/A", "file": "light.fit"})
    b = analysis_schema.resolve_row_abs_path({"path": "/root/B", "file": "light.fit"})
    assert a != b
    assert a == os.path.abspath("/root/A/light.fit")
    assert b == os.path.abspath("/root/B/light.fit")
    # canonical full-path form (basename(path)==file) is used as-is
    c = analysis_schema.resolve_row_abs_path({"path": "/root/A/light.fit", "file": "light.fit"})
    assert c == os.path.abspath("/root/A/light.fit")


# ---------------------------------------------------------------------------
# REWORK-1: SNR percent=80 acceptance (bottom 20% rejected)
# ---------------------------------------------------------------------------

def test_compute_snr_percent_threshold_keep80_rejects_bottom_20():
    snrs = [float(i) for i in range(1, 11)]  # 1..10, deterministic, no quantile ambiguity
    thr = analyse_logic.compute_snr_percent_threshold(snrs, 80)
    rejected = [s for s in snrs if s < thr]
    assert len(rejected) == 2  # exactly the bottom 20% (2 of 10)
    assert set(rejected) == {1.0, 2.0}
    kept = [s for s in snrs if s >= thr]
    assert len(kept) == 8


def test_compute_snr_percent_threshold_invalid_percent():
    with pytest.raises(ValueError):
        analyse_logic.compute_snr_percent_threshold([1.0, 2.0], 0)
    with pytest.raises(ValueError):
        analyse_logic.compute_snr_percent_threshold([1.0, 2.0], 101)


# ---------------------------------------------------------------------------
# REWORK-1: write_log_summary reco counters + resolved reco path
# ---------------------------------------------------------------------------

def test_write_log_summary_includes_reco_counters_and_path(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    reco_dir = root / "rejected_recommendations"
    f = root / "bad.fits"
    f.touch()
    rows = [_row("bad.fits", f, "not_in_recommendation", "pending_reco_action")]
    analyse_logic.apply_pending_reco_actions(
        rows, str(reco_dir), False, True, _NOOP, _NOOP, _NOOP, str(root))

    log_path = root / "analyse_resultats.log"
    options = {
        "move_rejected": True,
        "delete_rejected": False,
        "analyze_snr": True,
        "detect_trails": False,
        "include_subfolders": False,
        "snr_reject_dir": str(root / "rejected_low_snr"),
        "trail_reject_dir": str(root / "rejected_satellite_trails"),
        "reco_reject_dir": None,  # default derived from input_dir
        "snr_selection_mode": "percent",
        "snr_selection_value": "80",
        "trail_params": {},
    }
    analyse_logic.write_log_summary(str(log_path), str(root), options, results_list=rows)

    text = log_path.read_text(encoding="utf-8")
    assert "hors recommandation" in text
    assert "rejected_recommendations" in text  # resolved default path, not None/N/A

    loaded = project_state.load_latest_valid_visualization_block(str(log_path))
    moved = [r for r in loaded if r.get("action") == "moved_reco"]
    assert len(moved) == 1
    assert moved[0].get("rejected_reason") == "not_in_recommendation"


# ---------------------------------------------------------------------------
# REWORK-1: marker is reference-only; reload reads the LAST post-action block
# ---------------------------------------------------------------------------

def test_marker_is_reference_only(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    marker = project_state.write_marker_atomic(root, "analyse_resultats.log", product_version="3.5.0")
    payload = json.loads(marker.read_text(encoding="utf-8"))
    assert set(payload.keys()) <= {"schema_version", "product", "completed_at_utc", "log_file", "product_version"}
    assert "results" not in payload
    assert payload["log_file"] == "analyse_resultats.log"
    assert payload["product_version"] == "3.5.0"


def test_reload_marker_last_block_wins(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    f = root / "bad.fits"
    f.touch()
    log_path = root / "analyse_resultats.log"
    project_state.write_marker_atomic(root, "analyse_resultats.log", product_version="3.5.0")

    options = {
        "move_rejected": True, "delete_rejected": False, "analyze_snr": True,
        "detect_trails": False, "include_subfolders": False,
        "snr_reject_dir": str(root / "rejected_low_snr"),
        "trail_reject_dir": str(root / "rejected_satellite_trails"),
        "reco_reject_dir": None,
        "snr_selection_mode": "percent", "snr_selection_value": "80",
        "trail_params": {},
    }

    # Block 1 (pre-action): kept.
    before = [_row("bad.fits", f, None, "kept")]
    analyse_logic.write_log_summary(str(log_path), str(root), options, results_list=before)

    # Action: move to reco, then append Block 2 (post-action).
    after = [_row("bad.fits", f, "not_in_recommendation", "pending_reco_action")]
    analyse_logic.apply_pending_reco_actions(
        after, str(root / "rejected_recommendations"), False, True, _NOOP, _NOOP, _NOOP, str(root))
    analyse_logic.write_log_summary(str(log_path), str(root), options, results_list=after)

    log_ref = project_state.resolve_marker_log_path(root)
    assert log_ref is not None
    loaded = project_state.load_latest_valid_visualization_block(str(log_ref))
    assert loaded is not None
    moved = [r for r in loaded if r.get("action") == "moved_reco"]
    assert len(moved) == 1  # the LAST (post-action) block wins


# ---------------------------------------------------------------------------
# REWORK-1: Qt no-basename-conflation + auto=True zero mutation
# ---------------------------------------------------------------------------

@pytest.mark.skipif(mod.QApplication is object, reason="PySide6 not available")
def test_qt_apply_reco_no_basename_conflation(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    created_app = False
    app = mod.QApplication.instance()
    if app is None:
        app = mod.QApplication([])
        created_app = True

    win = mod.ZeAnalyserMainWindow()
    root = tmp_path / "project"
    (root / "A").mkdir(parents=True)
    (root / "B").mkdir(parents=True)
    a = root / "A" / "light.fit"
    b = root / "B" / "light.fit"
    a.touch()
    b.touch()

    rows = [
        {"file": "light.fit", "path": str(a), "status": "ok", "action": "kept",
         "rejected_reason": None, "snr": 30.0, "fwhm": 1.0, "ecc": 0.5, "starcount": 100},
        {"file": "light.fit", "path": str(b), "status": "ok", "action": "kept",
         "rejected_reason": None, "snr": 5.0, "fwhm": 3.0, "ecc": 0.9, "starcount": 10},
    ]
    win.analysis_results = rows
    win.recommended_images = [rows[0]]  # only A/light.fit recommended

    opts = {
        "input_path": str(root),
        "move_rejected": True,
        "delete_rejected": False,
        "snr_reject_dir": str(tmp_path / "rejected_low_snr"),
        "reco_reject_dir": "",
    }
    monkeypatch.setattr(win, "_build_options_from_ui", lambda: opts)
    monkeypatch.setattr(win, "_build_logic_callbacks", lambda *a, **k: _NOOP_CALLBACKS)
    monkeypatch.setattr(win, "_confirm_recommendations_apply", lambda **kw: True)
    monkeypatch.setattr(win, "_persist_actions_state", lambda *a, **k: None)

    try:
        win._apply_recommendations_gui(recommended=[rows[0]], auto=False)
        # A (recommended) stays; B (same basename) is the one moved, with its
        # subpath preserved under the dedicated reco dir.
        assert a.exists()
        assert not b.exists()
        assert (root / "rejected_recommendations" / "B" / "light.fit").exists()
        assert not (root / "rejected_recommendations" / "A" / "light.fit").exists()
    finally:
        try:
            win.close()
        except Exception:
            pass
        if created_app:
            app.quit()


@pytest.mark.skipif(mod.QApplication is object, reason="PySide6 not available")
def test_qt_apply_reco_auto_no_mutation(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    created_app = False
    app = mod.QApplication.instance()
    if app is None:
        app = mod.QApplication([])
        created_app = True

    win = mod.ZeAnalyserMainWindow()
    root = tmp_path / "project"
    root.mkdir()
    good = root / "good.fits"
    bad = root / "bad.fits"
    good.touch()
    bad.touch()

    rows = [
        {"file": "good.fits", "path": str(good), "status": "ok", "action": "kept",
         "rejected_reason": None, "snr": 30.0, "fwhm": 1.0, "ecc": 0.5, "starcount": 100},
        {"file": "bad.fits", "path": str(bad), "status": "ok", "action": "kept",
         "rejected_reason": None, "snr": 5.0, "fwhm": 3.0, "ecc": 0.9, "starcount": 10},
    ]
    win.analysis_results = rows
    win.recommended_images = [rows[0]]

    opts = {
        "input_path": str(root),
        "move_rejected": True,
        "delete_rejected": False,
        "snr_reject_dir": str(tmp_path / "rejected_low_snr"),
        "reco_reject_dir": "",
    }
    monkeypatch.setattr(win, "_build_options_from_ui", lambda: opts)
    monkeypatch.setattr(win, "_build_logic_callbacks", lambda *a, **k: _NOOP_CALLBACKS)
    # Confirmation must NOT be reached in auto mode.
    monkeypatch.setattr(win, "_confirm_recommendations_apply", lambda **kw: True)
    monkeypatch.setattr(win, "_persist_actions_state", lambda *a, **k: None)

    try:
        win._apply_recommendations_gui(recommended=[rows[0]], auto=True)
        # No consent => zero mutation / zero move.
        assert good.exists() and bad.exists()
        assert not (root / "rejected_recommendations").exists()
        assert rows[1]["rejected_reason"] is None
        assert rows[1]["action"] == "kept"
    finally:
        try:
            win.close()
        except Exception:
            pass
        if created_app:
            app.quit()


def test_tk_apply_reco_auto_no_mutation(monkeypatch, tmp_path):
    app = analyse_gui.AstroImageAnalyzerGUI.__new__(analyse_gui.AstroImageAnalyzerGUI)
    root = tmp_path / "project"
    root.mkdir()
    good = root / "good.fits"
    bad = root / "bad.fits"
    good.touch()
    bad.touch()

    rows = [
        {"file": "good.fits", "path": str(good), "status": "ok", "action": "kept",
         "rejected_reason": None, "snr": 30.0},
        {"file": "bad.fits", "path": str(bad), "status": "ok", "action": "kept",
         "rejected_reason": None, "snr": 5.0},
    ]
    app.analysis_results = rows
    app.recommended_images = [rows[0]]
    app.reco_reject_dir = _stub_var("")
    app.input_dir = _stub_var(str(root))
    app.reject_action = _stub_var("move")
    app._ = lambda key, default=None, **kwargs: default or key
    logged = []
    app.update_results_text = lambda key, **kw: logged.append((key, kw))

    app._apply_recommendations_gui(auto=True)

    assert good.exists() and bad.exists()
    assert not (root / "rejected_recommendations").exists()
    assert rows[1]["rejected_reason"] is None
    assert rows[1]["action"] == "kept"
    assert any(k == "gui_reco_auto_skipped" for k, _ in logged)
