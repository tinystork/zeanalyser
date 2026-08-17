"""Targeted tests for the Windows application identity / icon fix (ZA-M1-3A.1)."""

from __future__ import annotations

import sys
import types

import pytest

import zeanalyser.analyse_gui_qt as mod

pytestmark = pytest.mark.skipif(
    mod.QApplication is object, reason="PySide6 not installed in this environment"
)


def test_get_app_icon_uses_packaged_resources(monkeypatch):
    """get_app_icon() returns a non-null icon when package resources exist."""
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    # QIcon/QPixmap require an existing QApplication instance.
    if mod.QApplication.instance() is None:
        mod.QApplication([])
    icon = mod.get_app_icon()
    # The packaged icon/ folder ships zeanalyz_icon.png etc.; a non-null icon
    # proves the resource lookup (dirname(__file__)/icon) works.
    assert not icon.isNull()


def test_windows_aumid_is_noop_on_non_windows(monkeypatch):
    """On non-Windows platforms the helper must not touch ctypes at all."""
    monkeypatch.setattr(mod.platform, "system", lambda: "Linux")
    applied = mod._set_windows_app_user_model_id()
    assert applied is False


def test_windows_aumid_applied_on_windows(monkeypatch):
    """On Windows the helper calls SetCurrentProcessExplicitAppUserModelID."""
    monkeypatch.setattr(mod.platform, "system", lambda: "Windows")

    calls = []

    class FakeShell32:
        @staticmethod
        def SetCurrentProcessExplicitAppUserModelID(app_id):
            calls.append(app_id)
            return 0

    class FakeWindll:
        shell32 = FakeShell32()

    fake_ctypes = types.ModuleType("ctypes")
    fake_ctypes.windll = FakeWindll()
    monkeypatch.setitem(sys.modules, "ctypes", fake_ctypes)

    applied = mod._set_windows_app_user_model_id()
    assert applied is True
    assert calls == ["ZeSoftware.ZeAnalyser"]


def test_windows_aumid_failure_degrades_cleanly(monkeypatch):
    """A broken Windows API must not raise: the helper returns False."""
    monkeypatch.setattr(mod.platform, "system", lambda: "Windows")

    class FakeWindll:
        @property
        def shell32(self):
            raise OSError("shell32 unavailable")

    fake_ctypes = types.ModuleType("ctypes")
    fake_ctypes.windll = FakeWindll()
    monkeypatch.setitem(sys.modules, "ctypes", fake_ctypes)

    assert mod._set_windows_app_user_model_id() is False


def test_main_sets_windows_identity_before_qapplication(monkeypatch):
    """main() must declare the Windows identity BEFORE creating QApplication."""
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    events: list[str] = []
    monkeypatch.setattr(mod, "_set_windows_app_user_model_id", lambda: events.append("aumid"))

    RealQApplication = mod.QApplication
    had_instance = RealQApplication.instance() is not None

    class RecordingQApplication(RealQApplication):
        def __init__(self, argv=None):
            events.append("qapp")
            super().__init__(argv or [])

    monkeypatch.setattr(mod, "QApplication", RecordingQApplication)

    rc = mod.main(run_for=50)
    assert rc == 0
    # The Windows identity is declared first, unconditionally.
    assert events[0] == "aumid"
    # When no QApplication existed yet, the (recorded) creation must come after.
    if not had_instance:
        assert events[1] == "qapp"
