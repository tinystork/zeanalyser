import pytest

import analyse_gui_qt as mod

pytestmark = pytest.mark.skipif(
    mod.QApplication is object, reason="PySide6 not available"
)


def test_about_action_sets_last_text(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    # Prevent modal dialog from blocking in test
    def fake_about(*args):
        pass

    try:
        from PySide6.QtWidgets import QMessageBox
        monkeypatch.setattr(QMessageBox, 'about', fake_about)
    except (ImportError, AttributeError):
        pass

    app = mod.QApplication.instance()
    created = False
    if app is None:
        app = mod.QApplication([])
        created = True

    win = mod.ZeAnalyserMainWindow()

    # call about dialog (should set _last_about_text in test/offscreen)
    try:
        win._show_about_dialog()
    except Exception:
        # some environments may raise, but ensure we stored the last text
        pass

    assert hasattr(win, '_last_about_text')
    assert 'ZeAnalyser' in win._last_about_text

    if created:
        app.quit()
