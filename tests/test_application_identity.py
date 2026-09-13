from __future__ import annotations

import os
from pathlib import Path

import pytest

from zeanalyser import app_identity
import zeanalyser.analyse_gui_qt as gui

pytestmark = pytest.mark.skipif(
    gui.QApplication is object, reason="PySide6 unavailable"
)


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    return gui.QApplication.instance() or gui.QApplication([])


def test_stable_cross_platform_identity_constants():
    assert app_identity.APPLICATION_NAME == "ZeAnalyser"
    assert app_identity.APPLICATION_DISPLAY_NAME == "ZeAnalyser"
    assert app_identity.WINDOWS_APP_USER_MODEL_ID == "ZeSoftware.ZeAnalyser"
    assert app_identity.LINUX_DESKTOP_ID == "io.github.tinystork.ZeAnalyser"
    assert app_identity.LINUX_DESKTOP_FILENAME == (
        f"{app_identity.LINUX_DESKTOP_ID}.desktop"
    )


def test_linux_qt_identity_uses_canonical_desktop_id():
    calls = []

    class FakeApplication:
        def setOrganizationName(self, value):
            calls.append(("organization", value))

        def setApplicationName(self, value):
            calls.append(("name", value))

        def setApplicationDisplayName(self, value):
            calls.append(("display", value))

        def setDesktopFileName(self, value):
            calls.append(("desktop", value))

    app_identity.configure_qt_application(FakeApplication(), system_name="Linux")
    assert ("organization", app_identity.ORGANIZATION_NAME) in calls
    assert ("name", app_identity.APPLICATION_NAME) in calls
    assert ("display", app_identity.APPLICATION_DISPLAY_NAME) in calls
    assert ("desktop", app_identity.LINUX_DESKTOP_ID) in calls


def test_linux_identity_is_inert_on_other_platforms():
    desktop_calls = []

    class FakeApplication:
        def setOrganizationName(self, _value):
            pass

        def setApplicationName(self, _value):
            pass

        def setApplicationDisplayName(self, _value):
            pass

        def setDesktopFileName(self, value):
            desktop_calls.append(value)

    app_identity.configure_qt_application(FakeApplication(), system_name="Windows")
    assert desktop_calls == []


def test_application_and_main_window_use_packaged_icon_from_arbitrary_cwd(app, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    icon = gui._configure_application_identity_and_icon(app)
    assert not icon.isNull()
    assert not app.windowIcon().isNull()

    window = gui.ZeAnalyserMainWindow()
    assert not window.windowIcon().isNull()

    expected = icon.pixmap(64, 64).toImage()
    assert app.windowIcon().pixmap(64, 64).toImage() == expected
    assert window.windowIcon().pixmap(64, 64).toImage() == expected


def test_packaged_desktop_entry_matches_qt_identity_and_public_entrypoint():
    package_dir = Path(gui.__file__).resolve().parent
    desktop_entry = package_dir / "resources" / app_identity.LINUX_DESKTOP_FILENAME
    text = desktop_entry.read_text(encoding="utf-8")

    assert "Exec=zeanalyser\n" in text
    assert f"Icon={app_identity.LINUX_DESKTOP_ID}\n" in text
    assert "StartupWMClass=ZeAnalyser\n" in text
    assert "ZeAlfie" not in text

    pyproject = (package_dir.parent.parent / "pyproject.toml").read_text(encoding="utf-8")
    assert 'zeanalyser = "zeanalyser.analyse_gui_qt:main"' in pyproject
    assert '"resources/*.desktop"' in pyproject


def test_runtime_never_installs_desktop_files():
    package_dir = Path(gui.__file__).resolve().parent
    production = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (package_dir / "app_identity.py", package_dir / "analyse_gui_qt.py")
    )
    forbidden = (
        "/usr/share/applications",
        ".local/share/applications",
        "sudo ",
        "ZeAlfie",
    )
    assert all(token not in production for token in forbidden)
