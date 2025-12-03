import pytest

import analyse_gui_qt as mod


pytestmark = pytest.mark.skipif(
    mod.QApplication is object, reason="PySide6 not installed in this environment"
)


def test_reject_action_radio_and_options(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    created_app = False
    app = mod.QApplication.instance()
    if app is None:
        app = mod.QApplication([])
        created_app = True

    win = mod.ZeAnalyserMainWindow()

    # default should be move
    opts = win._build_options_from_ui()
    assert opts['move_rejected'] is True
    assert opts['delete_rejected'] is False

    # switch to delete
    if win.reject_delete_rb is not None:
        win.reject_delete_rb.setChecked(True)
    opts = win._build_options_from_ui()
    assert opts['move_rejected'] is False
    assert opts['delete_rejected'] is True

    # switch to none
    if win.reject_none_rb is not None:
        win.reject_none_rb.setChecked(True)
    opts = win._build_options_from_ui()
    assert opts['move_rejected'] is False
    assert opts['delete_rejected'] is False

    if created_app:
        app.quit()
