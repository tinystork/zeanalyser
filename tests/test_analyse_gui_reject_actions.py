import pytest

import zeanalyser.analyse_gui_qt as mod
from zeanalyser.zone import _
pytestmark = pytest.mark.skipif(
    mod.QApplication is object, reason="PySide6 not installed in this environment"
)


class _MemorySettings:
    values = {}

    def value(self, key, default=None):
        return self.values.get(key, default)

    def setValue(self, key, value):
        self.values[key] = value


def _fresh_settings(monkeypatch, initial=None):
    _MemorySettings.values = dict(initial or {})
    monkeypatch.setattr(mod, "QSettings", _MemorySettings)


def test_reject_action_radio_and_options(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    _fresh_settings(monkeypatch)

    created_app = False
    app = mod.QApplication.instance()
    if app is None:
        app = mod.QApplication([])
        created_app = True

    win = mod.ZeAnalyserMainWindow()

    # A fresh/default configuration must be non-mutating.
    opts = win._build_options_from_ui()
    assert opts['move_rejected'] is False
    assert opts['delete_rejected'] is False
    assert win.include_subfolders_cb.toolTip() == _("include_subfolders_tooltip")

    # switch to move explicitly
    if win.reject_move_rb is not None:
        win.reject_move_rb.setChecked(True)
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


@pytest.mark.parametrize("persisted", ["move", "delete"])
def test_explicit_reject_action_preference_survives_restart(monkeypatch, persisted):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    _fresh_settings(monkeypatch)
    app = mod.QApplication.instance() or mod.QApplication([])

    first = mod.ZeAnalyserMainWindow()
    if persisted == "move":
        first.reject_move_rb.setChecked(True)
    else:
        first.reject_delete_rb.setChecked(True)
    first._save_settings()
    first.close()

    second = mod.ZeAnalyserMainWindow()
    opts = second._build_options_from_ui()
    assert opts["move_rejected"] is (persisted == "move")
    assert opts["delete_rejected"] is (persisted == "delete")
    second.close()
