"""GUI wiring tests for the stack-plan ranking mode.

Proves that the Qt "Create stacking plan" dialog defaults to
``ranking_mode='quality'`` and that switching the combo to metadata propagates
to the preview.  Tk wiring is exercised via the shared helper/constants when a
display is unavailable.
"""

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

import zeanalyser.analyse_gui_qt as mod

pytestmark = pytest.mark.skipif(
    mod.QApplication is object or mod.QComboBox is object,
    reason="PySide6 not installed in this environment",
)


def _get_app(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    created_app = False
    app = mod.QApplication.instance()
    if app is None:
        app = mod.QApplication([])
        created_app = True
    return app, created_app


def _kept_rows():
    return [
        {
            "file": "a.fits",
            "path": "/tmp/a.fits",
            "status": "ok",
            "action": "kept",
            "rejected_reason": None,
            "mount": "ALTZ",
            "bortle": "3",
            "telescope": "T1",
            "date_obs": "2025-01-01T00:00:00",
            "filter": "L",
            "exposure": 30,
            "snr": 20.0,
            "fwhm": 2.0,
            "ecc": 0.3,
            "starcount": 200,
            "sky_bg": 100.0,
            "sky_noise": 10.0,
        },
        {
            "file": "b.fits",
            "path": "/tmp/b.fits",
            "status": "ok",
            "action": "kept",
            "rejected_reason": None,
            "mount": "ALTZ",
            "bortle": "3",
            "telescope": "T1",
            "date_obs": "2025-01-01T00:00:00",
            "filter": "L",
            "exposure": 30,
            "snr": 10.0,
            "fwhm": 4.0,
            "ecc": 0.7,
            "starcount": 50,
            "sky_bg": 150.0,
            "sky_noise": 20.0,
        },
    ]


def test_qt_dialog_default_ranking_mode_is_quality(monkeypatch):
    app, created_app = _get_app(monkeypatch)
    win = mod.ZeAnalyserMainWindow()
    try:
        win.analysis_results = _kept_rows()

        captured = {}

        import zeanalyser.stack_plan as sp

        real_generate = sp.generate_stacking_plan

        def spy_generate(results, **kwargs):
            captured["ranking_mode"] = kwargs.get("ranking_mode")
            # return a tiny valid plan so the preview code doesn't crash
            return [
                {"order": 1, "batch_id": "T1_2025-01-01_L", "mount": "ALTZ",
                 "bortle": "3", "telescope": "T1", "session_date": "2025-01-01",
                 "filter": "L", "exposure": "30", "file_path": "/tmp/a.fits",
                 "ra": "", "dec": ""}
            ]

        monkeypatch.setattr(sp, "generate_stacking_plan", spy_generate)
        monkeypatch.setattr(mod.QDialog, "exec", lambda self: None)

        win.open_stack_plan_window()

        # the dialog's initial preview must have used the quality default
        assert captured.get("ranking_mode") == "quality"
    finally:
        try:
            win.close()
        except Exception:
            pass
        if created_app:
            app.quit()


def test_qt_dialog_combo_switch_to_metadata(monkeypatch):
    app, created_app = _get_app(monkeypatch)
    win = mod.ZeAnalyserMainWindow()
    try:
        win.analysis_results = _kept_rows()

        captured = {}

        import zeanalyser.stack_plan as sp

        def spy_generate(results, **kwargs):
            captured["ranking_mode"] = kwargs.get("ranking_mode")
            return [
                {"order": 1, "batch_id": "T1_2025-01-01_L", "mount": "ALTZ",
                 "bortle": "3", "telescope": "T1", "session_date": "2025-01-01",
                 "filter": "L", "exposure": "30", "file_path": "/tmp/a.fits",
                 "ra": "", "dec": ""}
            ]

        monkeypatch.setattr(sp, "generate_stacking_plan", spy_generate)

        # Intercept the dialog to locate the ranking combo and flip it to
        # metadata, then verify the preview reflects the change.
        def fake_exec(self):
            combos = self.findChildren(mod.QComboBox)
            ranking = None
            for cb in combos:
                if cb.count() == 2 and cb.itemData(0) == "quality" and cb.itemData(1) == "metadata":
                    ranking = cb
                    break
            assert ranking is not None, "ranking combo not found"
            ranking.setCurrentIndex(1)  # -> metadata, triggers update_preview
            return None

        monkeypatch.setattr(mod.QDialog, "exec", fake_exec)

        win.open_stack_plan_window()

        # after switching the combo, the preview must report metadata
        assert captured.get("ranking_mode") == "metadata"
    finally:
        try:
            win.close()
        except Exception:
            pass
        if created_app:
            app.quit()


def test_ranking_mode_constants_and_defaults():
    # Core contract exercised by Qt/Tk simple/auto/regenerate paths: the
    # default is quality, and legacy aliases to metadata.
    import zeanalyser.stack_plan as sp
    assert sp.RANKING_MODE_QUALITY == "quality"
    assert sp.RANKING_MODE_METADATA == "metadata"

    rows = [
        {"file": "a.fits", "path": "/tmp/a.fits", "status": "ok", "action": "kept",
         "telescope": "T1", "date_obs": "2025-01-01T00:00:00", "filter": "L",
         "exposure": 30, "snr": 10.0, "fwhm": 2.0, "ecc": 0.3},
        {"file": "b.fits", "path": "/tmp/b.fits", "status": "ok", "action": "kept",
         "telescope": "T1", "date_obs": "2025-01-01T00:00:00", "filter": "L",
         "exposure": 30, "snr": 30.0, "fwhm": 2.0, "ecc": 0.3},
    ]
    plan = sp.generate_stacking_plan(rows)
    assert plan[0]["file_path"] == "/tmp/b.fits"  # quality: best SNR first
    assert plan[0]["ranking_mode"] == "quality"
