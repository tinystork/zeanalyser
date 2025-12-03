import pytest

import analyse_gui
import analyse_gui_qt as mod


def _stub_var(value):
    class _Var:
        def get(self):
            return value

    return _Var()


def _build_sample_results():
    return [
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


def test_tk_apply_current_recommendations_recomputes(monkeypatch):
    app = analyse_gui.AstroImageAnalyzerGUI.__new__(analyse_gui.AstroImageAnalyzerGUI)
    app.analysis_results = _build_sample_results()
    app.reco_snr_pct_min = _stub_var(25)
    app.reco_fwhm_pct_max = _stub_var(75)
    app.reco_ecc_pct_max = _stub_var(75)
    app.reco_starcount_pct_min = _stub_var(25)
    app.use_starcount_filter = _stub_var(True)
    app._ = lambda key, default=None, **kwargs: default or key
    app.recommended_images = []

    info_messages = []
    monkeypatch.setattr(analyse_gui.messagebox, "showinfo", lambda *a, **k: info_messages.append((a, k)))

    called = {}

    def fake_apply(*, auto=False):
        called["auto"] = auto

    app._apply_recommendations_gui = fake_apply

    app._apply_current_recommendations()

    assert called == {"auto": False}
    assert len(app.recommended_images) == 1
    assert app.recommended_images[0]["file"] == "a.fits"
    assert info_messages == []

@pytest.mark.skipif(
    mod.QApplication is object, reason="PySide6 not installed in this environment"
)
def test_qt_apply_current_recommendations_recomputes(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    created_app = False
    app = mod.QApplication.instance()
    if app is None:
        app = mod.QApplication([])
        created_app = True

    win = mod.ZeAnalyserMainWindow()
    win.analysis_results = _build_sample_results()
    win.reco_snr_pct_min = 25.0
    win.reco_fwhm_pct_max = 75.0
    win.reco_ecc_pct_max = 75.0
    win.reco_starcount_pct_min = 25.0
    win.use_starcount_filter = True
    win.recommended_images = []

    info_messages = []

    class DummyMsgBox:
        @staticmethod
        def information(*args, **kwargs):
            info_messages.append((args, kwargs))

    monkeypatch.setattr(mod, "QMessageBox", DummyMsgBox)

    called = {}

    def fake_apply(*, auto=False):
        called["auto"] = auto

    win._apply_recommendations_gui = fake_apply

    try:
        win._apply_current_recommendations()
        assert called == {"auto": False}
        assert len(win.recommended_images) == 1
        assert win.recommended_images[0]["file"] == "a.fits"
        assert info_messages == []
    finally:
        try:
            win.close()
        except Exception:
            pass
        if created_app:
            app.quit()
