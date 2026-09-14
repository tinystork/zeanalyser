"""Targeted tests for the Windows application identity / icon fix.

ZA-M1-3A.1 covered the icon/identity plumbing; ZA-APP-IDENTITY-P1.8 adds the
truthfulness contract for the Win32 ``SetCurrentProcessExplicitAppUserModelID``
call: the native HRESULT must decide success, the ABI must be declared before
the call, and failures must degrade to a bounded warning instead of a silent
``True``.
"""

from __future__ import annotations

import logging
import os
import sys
import types

import pytest

import zeanalyser.analyse_gui_qt as mod

pytestmark = pytest.mark.skipif(
    mod.QApplication is object, reason="PySide6 not installed in this environment"
)

# Native HRESULTs used by the reproducer.
S_OK = 0
E_FAIL = -2147467259
E_INVALIDARG = -2147024809


class SpyAumidFunc:
    """Records ABI declarations and the ABI state at call time."""

    def __init__(self, hr: int = S_OK, error: Exception | None = None) -> None:
        self.hr = hr
        self.error = error
        self.argtypes = None
        self.restype = None
        self.calls: list[object] = []
        self.abi_at_call = None

    def __call__(self, app_id):
        self.abi_at_call = (self.argtypes, self.restype)
        self.calls.append(app_id)
        if self.error is not None:
            raise self.error
        return self.hr


class SpyShell32:
    def __init__(self, func: SpyAumidFunc) -> None:
        self.SetCurrentProcessExplicitAppUserModelID = func


def install_fake_ctypes(monkeypatch, shell32, *, with_abi: bool = True):
    """Install a fake ``ctypes`` module mirroring the real ABI attributes."""
    fake_ctypes = types.ModuleType("ctypes")
    if with_abi:
        fake_ctypes.c_wchar_p = "c_wchar_p-sentinel"
        fake_ctypes.c_long = "c_long-sentinel"
    fake_ctypes.windll = types.SimpleNamespace(shell32=shell32)
    monkeypatch.setitem(sys.modules, "ctypes", fake_ctypes)
    return fake_ctypes


def make_spy(monkeypatch, hr: int = S_OK, error: Exception | None = None, **kw):
    func = SpyAumidFunc(hr=hr, error=error)
    fake_ctypes = install_fake_ctypes(monkeypatch, SpyShell32(func), **kw)
    return func, fake_ctypes


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

    class ExplodingCtypes(types.ModuleType):
        def __getattr__(self, name):  # pragma: no cover - must never run
            raise AssertionError(f"ctypes.{name} touched on non-Windows")

    monkeypatch.setitem(sys.modules, "ctypes", ExplodingCtypes("ctypes"))

    applied = mod._set_windows_app_user_model_id()
    assert applied is False


def test_windows_aumid_success_returns_true(monkeypatch):
    """S_OK (0) is the only HRESULT that means the identity was applied."""
    monkeypatch.setattr(mod.platform, "system", lambda: "Windows")
    func, fake_ctypes = make_spy(monkeypatch, hr=S_OK)

    applied = mod._set_windows_app_user_model_id()

    assert applied is True
    assert func.calls == ["ZeSoftware.ZeAnalyser"]
    # ABI declared *before* the call (captured inside __call__).
    assert func.abi_at_call == ([fake_ctypes.c_wchar_p], fake_ctypes.c_long)


def test_windows_aumid_declares_abi_before_call(monkeypatch):
    """argtypes/restype must be set from the real ctypes ABI types."""
    monkeypatch.setattr(mod.platform, "system", lambda: "Windows")
    func, fake_ctypes = make_spy(monkeypatch, hr=S_OK)

    mod._set_windows_app_user_model_id()

    assert func.argtypes == [fake_ctypes.c_wchar_p]
    assert func.restype == fake_ctypes.c_long


def test_windows_aumid_e_fail_returns_false_and_warns(monkeypatch, caplog):
    """E_FAIL must no longer be reported as success."""
    monkeypatch.setattr(mod.platform, "system", lambda: "Windows")
    func, _ = make_spy(monkeypatch, hr=E_FAIL)

    with caplog.at_level(logging.WARNING, logger=mod.__name__):
        applied = mod._set_windows_app_user_model_id()

    assert applied is False
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "0x80004005" in caplog.text


def test_windows_aumid_e_invalidarg_returns_false(monkeypatch, caplog):
    """E_INVALIDARG must be a truthful failure too."""
    monkeypatch.setattr(mod.platform, "system", lambda: "Windows")
    func, _ = make_spy(monkeypatch, hr=E_INVALIDARG)

    with caplog.at_level(logging.WARNING, logger=mod.__name__):
        applied = mod._set_windows_app_user_model_id()

    assert applied is False
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "0x80070057" in caplog.text


def test_windows_aumid_exception_returns_false_without_raising(monkeypatch, caplog):
    """A broken Windows API must not raise: one bounded warning, False."""
    monkeypatch.setattr(mod.platform, "system", lambda: "Windows")

    class FakeWindll:
        @property
        def shell32(self):
            raise OSError("shell32 unavailable")

    fake_ctypes = types.ModuleType("ctypes")
    fake_ctypes.c_wchar_p = "c_wchar_p-sentinel"
    fake_ctypes.c_long = "c_long-sentinel"
    fake_ctypes.windll = FakeWindll()
    monkeypatch.setitem(sys.modules, "ctypes", fake_ctypes)

    with caplog.at_level(logging.WARNING, logger=mod.__name__):
        applied = mod._set_windows_app_user_model_id()

    assert applied is False
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1


def test_windows_aumid_works_with_double_lacking_abi_attrs(monkeypatch):
    """A double without settable attrs must still degrade, not explode."""
    monkeypatch.setattr(mod.platform, "system", lambda: "Windows")

    class FrozenFunc:
        def __init__(self, hr):
            object.__setattr__(self, "_hr", hr)

        def __setattr__(self, name, value):
            raise AttributeError(f"{name} is read-only on this double")

        def __call__(self, app_id):
            return self._hr

    fake_ctypes = types.ModuleType("ctypes")
    fake_ctypes.c_wchar_p = "c_wchar_p-sentinel"
    fake_ctypes.c_long = "c_long-sentinel"
    fake_ctypes.windll = types.SimpleNamespace(
        shell32=types.SimpleNamespace(
            SetCurrentProcessExplicitAppUserModelID=FrozenFunc(S_OK)
        )
    )
    monkeypatch.setitem(sys.modules, "ctypes", fake_ctypes)

    assert mod._set_windows_app_user_model_id() is True


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


def test_main_warns_when_windows_identity_fails(monkeypatch, caplog):
    """On Windows a False helper result must produce one bounded warning."""
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setattr(mod.platform, "system", lambda: "Windows")
    monkeypatch.setattr(mod, "_set_windows_app_user_model_id", lambda: False)

    with caplog.at_level(logging.WARNING, logger=mod.__name__):
        rc = mod.main(run_for=50)

    assert rc == 0  # never fatal, never blocking
    warnings = [
        r
        for r in caplog.records
        if r.levelno == logging.WARNING and "taskbar identity" in r.getMessage()
    ]
    assert len(warnings) == 1


def test_main_does_not_warn_on_non_windows(monkeypatch, caplog):
    """Non-Windows legitimately returns False: that must stay silent."""
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setattr(mod.platform, "system", lambda: "Linux")
    monkeypatch.setattr(mod, "_set_windows_app_user_model_id", lambda: False)

    with caplog.at_level(logging.WARNING, logger=mod.__name__):
        rc = mod.main(run_for=50)

    assert rc == 0
    assert "taskbar identity" not in caplog.text


# ---------------------------------------------------------------------------
# ZA-APP-IDENTITY-P1.8 r1 — Windows *window* Shell identity POC
# ---------------------------------------------------------------------------


class SpyPropertyStore:
    """IPropertyStore double recording the property-write order."""

    def __init__(self, events, fail_on=None):
        self.events = events
        self.fail_on = fail_on

    def set_lpwstr(self, pid, value):
        if self.fail_on == ("set", pid):
            raise OSError("IPropertyStore::SetValue failed: HRESULT 0x80004005")
        self.events.append(("set", pid, value))

    def commit(self):
        if self.fail_on == "commit":
            raise OSError("IPropertyStore::Commit failed: HRESULT 0x80004005")
        self.events.append(("commit",))


def test_window_identity_schema_constants():
    """Guard the documented System.AppUserModel property-schema constants."""
    assert mod._PKEY_APPUSERMODEL_RELAUNCH_ICON_RESOURCE == 3
    assert mod._PKEY_APPUSERMODEL_ID == 5
    assert mod._VT_LPWSTR == 31  # VT_LPWSTR
    assert mod._WINDOWS_APPUSERMODEL_FMTID == "{9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3}"
    assert mod._IID_IPROPERTYSTORE == "{886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99}"
    assert mod._WINDOWS_RELAUNCH_ICON_INDEX == 0


def test_relaunch_icon_resource_is_built_from_icon_dir(monkeypatch):
    """The icon resource must be the packaged .ico + ',0' (no hardcoded path)."""
    monkeypatch.setattr(mod, "ICON_DIR", os.path.join("SENTINEL", "icon"))
    value = mod._windows_relaunch_icon_resource()
    assert value == os.path.join("SENTINEL", "icon", "zeanalyz.ico") + ",0"
    assert value.endswith("zeanalyz.ico,0")


def test_window_identity_properties_order_and_values():
    """Icon (pid 3) strictly before ID (pid 5); nothing else is written."""
    pairs = mod._windows_window_identity_properties()
    assert [pid for pid, _ in pairs] == [3, 5]
    assert pairs[0][1] == os.path.join(mod.ICON_DIR, "zeanalyz.ico") + ",0"
    assert pairs[1][1] == "ZeSoftware.ZeAnalyser"
    assert pairs[1][1] == mod.WINDOWS_APP_USER_MODEL_ID
    # RelaunchCommand (2) and RelaunchDisplayNameResource (4) are NOT set.
    assert 2 not in [pid for pid, _ in pairs]
    assert 4 not in [pid for pid, _ in pairs]


def test_write_window_identity_commits_after_both_sets():
    """Commit must come after both SetValue calls."""
    events = []
    mod._write_window_identity(SpyPropertyStore(events))
    assert [e[0] for e in events] == ["set", "set", "commit"]
    assert events[0] == ("set", 3, mod._windows_relaunch_icon_resource())
    assert events[1] == ("set", 5, mod.WINDOWS_APP_USER_MODEL_ID)


def test_window_helper_is_noop_on_non_windows(monkeypatch):
    """Off Windows the helper must not touch ctypes at all."""
    monkeypatch.setattr(mod.platform, "system", lambda: "Linux")

    class ExplodingCtypes(types.ModuleType):
        def __getattr__(self, name):  # pragma: no cover - must never run
            raise AssertionError(f"ctypes.{name} touched on non-Windows")

    monkeypatch.setitem(sys.modules, "ctypes", ExplodingCtypes("ctypes"))
    assert mod._set_windows_window_identity(1234) is False


def test_set_windows_window_identity_sets_icon_then_id(monkeypatch):
    """Windows path: property store opened for the HWND, icon then ID, commit."""
    monkeypatch.setattr(mod.platform, "system", lambda: "Windows")
    events: list = []
    opened: list = []

    def fake_store_factory(hwnd, ctypes_module):
        opened.append(hwnd)
        return SpyPropertyStore(events)

    monkeypatch.setattr(mod, "_CtypesWindowPropertyStore", fake_store_factory)

    assert mod._set_windows_window_identity(4242) is True
    assert opened == [4242]
    pids = [e[1] for e in events if e[0] == "set"]
    assert pids == [3, 5]
    assert events[0][2] == os.path.join(mod.ICON_DIR, "zeanalyz.ico") + ",0"
    assert events[1][2] == "ZeSoftware.ZeAnalyser"
    assert events[-1] == ("commit",)


def test_set_windows_window_identity_failure_warns_once(monkeypatch, caplog):
    """A failing store must degrade to False + exactly one warning."""
    monkeypatch.setattr(mod.platform, "system", lambda: "Windows")

    def failing_factory(hwnd, ctypes_module):
        raise OSError("SHGetPropertyStoreForWindow failed: HRESULT 0x80004005")

    monkeypatch.setattr(mod, "_CtypesWindowPropertyStore", failing_factory)

    with caplog.at_level(logging.WARNING, logger=mod.__name__):
        assert mod._set_windows_window_identity(7) is False

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "0x80004005" in caplog.text


def test_set_windows_window_identity_setvalue_failure_warns_once(monkeypatch, caplog):
    """A failing SetValue/Commit is still a bounded False, never a raise."""
    monkeypatch.setattr(mod.platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        mod,
        "_CtypesWindowPropertyStore",
        lambda hwnd, ctypes_module: SpyPropertyStore([], fail_on=("set", 5)),
    )

    with caplog.at_level(logging.WARNING, logger=mod.__name__):
        assert mod._set_windows_window_identity(9) is False

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1


def test_main_applies_window_identity_only_on_windows(monkeypatch):
    """main() must not invoke the window helper on non-Windows platforms."""
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setattr(mod.platform, "system", lambda: "Linux")
    calls: list = []
    monkeypatch.setattr(
        mod, "_set_windows_window_identity", lambda hwnd: calls.append(hwnd) or True
    )

    assert mod.main(run_for=50) == 0
    assert calls == []


def test_main_applies_window_identity_on_windows(monkeypatch):
    """On Windows main() must apply the window identity before showing it."""
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setattr(mod.platform, "system", lambda: "Windows")
    monkeypatch.setattr(mod, "_set_windows_app_user_model_id", lambda: True)
    calls: list = []

    def record(hwnd):
        calls.append(hwnd)
        return True

    monkeypatch.setattr(mod, "_set_windows_window_identity", record)

    assert mod.main(run_for=50) == 0
    assert len(calls) == 1
    assert isinstance(calls[0], int)


def test_main_window_identity_is_before_show(monkeypatch):
    """Ordering: window identity is applied BEFORE _show_window_safely()."""
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setattr(mod.platform, "system", lambda: "Windows")
    monkeypatch.setattr(mod, "_set_windows_app_user_model_id", lambda: True)
    events: list = []
    monkeypatch.setattr(
        mod, "_set_windows_window_identity", lambda hwnd: events.append("identity") or True
    )

    real_window = mod.ZeAnalyserMainWindow

    class RecordingWindow(real_window):
        def _show_window_safely(self):
            events.append("show")
            return super()._show_window_safely()

    monkeypatch.setattr(mod, "ZeAnalyserMainWindow", RecordingWindow)

    assert mod.main(run_for=50) == 0
    assert events[0] == "identity"
    assert "show" in events
