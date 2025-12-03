import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

import analyse_gui_qt as mod


pytestmark = pytest.mark.skipif(
    mod.QApplication is object, reason="PySide6 not installed in this environment"
)


def _get_app(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    created_app = False
    app = mod.QApplication.instance()
    if app is None:
        app = mod.QApplication([])
        created_app = True
    return app, created_app


def test_settings_tab_language_and_skin(monkeypatch):
    app, created_app = _get_app(monkeypatch)
    win = mod.ZeAnalyserMainWindow()
    try:
        assert win.lang_combo is not None
        assert win.skin_combo is not None

        lang_values = [win.lang_combo.itemData(i) for i in range(win.lang_combo.count())]
        assert "system" in lang_values

        skin_values = [win.skin_combo.itemData(i) for i in range(win.skin_combo.count())]
        assert "system" in skin_values
        assert "dark" in skin_values
    finally:
        try:
            win.close()
        except Exception:
            pass
        if created_app:
            app.quit()


def test_compute_recommended_subset_respects_thresholds(monkeypatch):
    app, created_app = _get_app(monkeypatch)
    win = mod.ZeAnalyserMainWindow()
    try:
        win.analysis_results = [
            {
                "file": "a.fits",
                "status": "ok",
                "action": "kept",
                "rejected_reason": None,
                "snr": 30.0,
                "fwhm": 1.5,
                "ecc": 0.8,
                "starcount": 150,
            },
            {
                "file": "b.fits",
                "status": "ok",
                "action": "kept",
                "rejected_reason": None,
                "snr": 10.0,
                "fwhm": 2.5,
                "ecc": 0.9,
                "starcount": 50,
            },
        ]

        win.reco_snr_pct_min = 50.0
        win.reco_fwhm_pct_max = 50.0
        win.reco_ecc_pct_max = 50.0
        win.use_starcount_filter = True
        win.reco_starcount_pct_min = 50.0

        recos, snr_p, fwhm_p, ecc_p, sc_p = win._compute_recommended_subset()

        assert len(recos) == 1
        assert recos[0]["file"] == "a.fits"
        assert snr_p >= 20.0
        assert fwhm_p <= 2.0
        assert ecc_p <= 0.9
        assert sc_p >= 100.0
    finally:
        try:
            win.close()
        except Exception:
            pass
        if created_app:
            app.quit()


def test_visualise_results_handles_small_dataset(monkeypatch):
    app, created_app = _get_app(monkeypatch)
    monkeypatch.setenv("MPLBACKEND", "Agg")
    win = mod.ZeAnalyserMainWindow()
    try:
        rows = [
            {
                "file": "c.fits",
                "status": "ok",
                "action": "kept",
                "rejected_reason": None,
                "snr": 25.0,
                "fwhm": 1.8,
                "ecc": 0.7,
                "starcount": 120,
                "has_trails": False,
            }
        ]

        monkeypatch.setattr(mod.QDialog, "exec", lambda self: None)

        win.analysis_results = rows
        win._visualise_results()
    finally:
        try:
            win.close()
        except Exception:
            pass
        if created_app:
            app.quit()
