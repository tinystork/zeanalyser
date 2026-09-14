"""Canonical result-row source tests for the visualization path (V1-V6)."""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

import zeanalyser.analyse_gui_qt as mod

pytestmark = pytest.mark.skipif(
    mod.QApplication is object or mod.Signal is None,
    reason="PySide6 not available",
)

REAL_DERIVED_FIXTURE = Path(
    "/home/tristan/.openclaw/workspace/.a2a-reports/ZA-P1.7-astra-evidence/"
    "real-log-derived-10-rows.json"
)


def _get_app(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("MPLBACKEND", "Agg")
    created = False
    app = mod.QApplication.instance()
    if app is None:
        app = mod.QApplication([])
        created = True
    return app, created


def _valid_rows(count=10, base=30.0):
    rows = []
    for idx in range(count):
        rows.append(
            {
                "file": f"image_{idx:02d}.fit",
                "rel_path": f"image_{idx:02d}.fit",
                "path": f"/data/image_{idx:02d}.fit",
                "status": "ok",
                "action": "kept",
                "rejected_reason": None,
                "error_message": "",
                "has_trails": False,
                "num_trails": 0,
                "snr": base + idx,
                "sky_bg": 100.0,
                "sky_noise": 5.0,
                "signal_pixels": 100,
                "starcount": 50,
                "fwhm": 3.0,
                "ecc": 0.2,
                "n_star_ecc": 9,
                "exposure": 10.0,
                "filter": "LP",
                "temperature": 10.0,
            }
        )
    return rows


def _stale_row():
    return {
        "file": "stale.fit",
        "rel_path": "stale.fit",
        "path": "/data/stale.fit",
        "status": "ok",
        "action": "kept",
        "rejected_reason": None,
        "has_trails": False,
        "snr": None,
        "fwhm": None,
        "ecc": None,
        "starcount": None,
    }


def _wait_for(cond, timeout=5.0, interval=0.01):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if cond():
            return True
        app = mod.QApplication.instance()
        if app is not None:
            app.processEvents()
        time.sleep(interval)
    return False


def _visualise_without_blocking(monkeypatch, win):
    monkeypatch.setattr(mod.QDialog, "exec", lambda self: None)
    win._visualise_results()


# --- V1 ---------------------------------------------------------------------

def test_v1_direct_valid_rows_reach_visualiser(monkeypatch):
    app, created = _get_app(monkeypatch)
    win = mod.ZeAnalyserMainWindow()
    try:
        rows = _valid_rows()
        win.analysis_results = list(rows)
        _visualise_without_blocking(monkeypatch, win)

        snrs = mod.extract_valid_metric_values(
            win._get_analysis_results_rows(), "snr", require_ok_status=True
        )
        assert len(snrs) == len(rows)
        assert getattr(win, "current_snr_min", None) == min(r["snr"] for r in rows)
        assert getattr(win, "current_snr_max", None) == max(r["snr"] for r in rows)
    finally:
        win.close()
        if created:
            app.quit()


# --- V2 ---------------------------------------------------------------------

def test_v2_live_worker_chain_reaches_visualiser(monkeypatch):
    app, created = _get_app(monkeypatch)
    win = mod.ZeAnalyserMainWindow()
    try:
        rows = _valid_rows()

        def _fake_analysis(callbacks=None):
            return rows

        worker = mod.AnalysisWorker(step_ms=1)
        worker.resultsReady.connect(win._on_results_ready)
        worker.start(_fake_analysis)

        assert _wait_for(lambda: len(win._get_analysis_results_rows()) == len(rows))

        # model is the canonical projection of the same rows
        assert win._results_model.rowCount() == len(rows)
        assert win._get_analysis_results_rows() == rows

        _visualise_without_blocking(monkeypatch, win)
        snrs = mod.extract_valid_metric_values(
            win._get_analysis_results_rows(), "snr", require_ok_status=True
        )
        assert snrs == [r["snr"] for r in rows]
        assert getattr(win, "current_snr_min", None) == min(r["snr"] for r in rows)
    finally:
        win.close()
        if created:
            app.quit()


# --- V3 ---------------------------------------------------------------------

def test_v3_canonical_accessor_matches_results_model(monkeypatch):
    app, created = _get_app(monkeypatch)
    win = mod.ZeAnalyserMainWindow()
    try:
        rows = _valid_rows(6)
        win.set_results(rows)

        canonical = win._get_analysis_results_rows()
        model_rows = list(win._results_model._rows)
        assert len(canonical) == len(model_rows) == len(rows)
        assert [r["file"] for r in canonical] == [r["file"] for r in model_rows]
        assert canonical == model_rows
        for row in canonical:
            assert row["snr"] == next(
                r["snr"] for r in rows if r["file"] == row["file"]
            )
    finally:
        win.close()
        if created:
            app.quit()


# --- V4 ---------------------------------------------------------------------

def test_v4_persisted_visualisation_block_reloads_same_rows(tmp_path, monkeypatch):
    app, created = _get_app(monkeypatch)
    win = mod.ZeAnalyserMainWindow()
    try:
        rows = _valid_rows(10)
        log_path = tmp_path / "analyse_resultats.log"
        with open(log_path, "w", encoding="utf-8") as fh:
            fh.write("analyse\n")
            fh.write("--- BEGIN VISUALIZATION DATA ---\n")
            json.dump(rows, fh)
            fh.write("\n--- END VISUALIZATION DATA ---\n")

        assert win._load_visualisation_from_log_path(str(log_path)) is True

        _visualise_without_blocking(monkeypatch, win)
        snrs = mod.extract_valid_metric_values(
            win._get_analysis_results_rows(), "snr", require_ok_status=True
        )
        assert snrs == [r["snr"] for r in rows]
        assert getattr(win, "current_snr_min", None) == min(r["snr"] for r in rows)
    finally:
        win.close()
        if created:
            app.quit()


# --- V5 ---------------------------------------------------------------------

def test_v5_genuine_no_metric_rows_still_shows_no_data(monkeypatch):
    app, created = _get_app(monkeypatch)
    win = mod.ZeAnalyserMainWindow()
    try:
        rows = _valid_rows(3)
        for row in rows:
            row["snr"] = None
            row["fwhm"] = None
            row["ecc"] = None
            row["starcount"] = None
        win.set_results(rows)

        _visualise_without_blocking(monkeypatch, win)  # must not raise

        assert mod.extract_valid_metric_values(rows, "snr", require_ok_status=True) == []
        assert getattr(win, "current_snr_min", None) is None
        assert getattr(win, "current_fwhm_min", None) is None
    finally:
        win.close()
        if created:
            app.quit()


# --- V6 ---------------------------------------------------------------------

def test_v6_stale_model_never_shadows_valid_canonical_rows(monkeypatch):
    app, created = _get_app(monkeypatch)
    win = mod.ZeAnalyserMainWindow()
    try:
        from zeanalyser.analysis_model import AnalysisResultsModel

        rows = _valid_rows(10)
        win.set_results(rows)
        # inject a stale 1-row model that diverges from the canonical owner
        win._results_model = AnalysisResultsModel([_stale_row()])

        canonical = win._get_analysis_results_rows()
        assert len(canonical) == 10
        assert all(r["snr"] is not None for r in canonical)

        _visualise_without_blocking(monkeypatch, win)
        snrs = mod.extract_valid_metric_values(canonical, "snr", require_ok_status=True)
        assert len(snrs) == 10
        assert getattr(win, "current_snr_min", None) == min(r["snr"] for r in rows)
    finally:
        win.close()
        if created:
            app.quit()


def test_v6_empty_canonical_does_not_resurrect_stale_cache(monkeypatch):
    app, created = _get_app(monkeypatch)
    win = mod.ZeAnalyserMainWindow()
    try:
        from zeanalyser.analysis_model import AnalysisResultsModel
        from zeanalyser.zone import _ as tr

        win.set_results([])
        win._results_model = AnalysisResultsModel([_stale_row()])

        messages = []
        monkeypatch.setattr(win, "_log", lambda msg: messages.append(str(msg)))
        monkeypatch.setattr(mod.QDialog, "exec", lambda self: None)

        win._visualise_results()

        assert win._get_analysis_results_rows() == []
        assert win.analysis_results == []
        assert tr("gui_no_results_to_visualise") in messages
    finally:
        win.close()
        if created:
            app.quit()


# --- real-log-derived fixture ------------------------------------------------

@pytest.mark.skipif(
    not REAL_DERIVED_FIXTURE.is_file(), reason="real-derived fixture unavailable"
)
def test_real_derived_fixture_snr_available_metrics_absent(monkeypatch):
    app, created = _get_app(monkeypatch)
    win = mod.ZeAnalyserMainWindow()
    try:
        rows = json.loads(REAL_DERIVED_FIXTURE.read_text(encoding="utf-8"))
        assert len(rows) == 10
        win.set_results(rows)

        snrs = mod.extract_valid_metric_values(rows, "snr", require_ok_status=True)
        assert len(snrs) == 10, "all SNR values must be available to the visualiser"
        assert mod.extract_valid_metric_values(rows, "fwhm") == []
        assert mod.extract_valid_metric_values(rows, "ecc") == []

        _visualise_without_blocking(monkeypatch, win)  # no crash, no fake data
        assert getattr(win, "current_snr_min", None) == min(snrs)
        assert getattr(win, "current_fwhm_min", None) is None
    finally:
        win.close()
        if created:
            app.quit()
