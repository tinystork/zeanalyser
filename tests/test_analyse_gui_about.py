import pytest
import tomllib
from pathlib import Path

import zeanalyser.analyse_gui_qt as mod
from zeanalyser._version import __version__
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
    assert f'Version: {__version__}' in win._last_about_text
    assert 'unknown' not in win._last_about_text.lower()
    assert win.windowTitle() == f"ZeAnalyser {__version__} — Analyseur d'Images Astronomiques"

    if created:
        app.quit()


def test_about_packaging_and_source_version_share_canonical_attribute():
    assert __version__ == "3.4.0"

    pyproject_path = mod.os.path.join(
        mod.os.path.dirname(mod.os.path.dirname(mod.os.path.dirname(mod.__file__))),
        "pyproject.toml",
    )
    with open(pyproject_path, "rb") as stream:
        pyproject = tomllib.load(stream)

    assert pyproject["tool"]["setuptools"]["dynamic"]["version"]["attr"] == (
        "zeanalyser._version.__version__"
    )


def test_production_gui_has_no_stale_active_version_literal():
    package_dir = Path(mod.__file__).resolve().parent
    active_surfaces = (
        package_dir / "analyse_gui_qt.py",
        package_dir / "analyse_gui.py",
        package_dir / "sat_trail.py",
        package_dir / "zone.py",
    )
    combined = "\n".join(path.read_text(encoding="utf-8") for path in active_surfaces)
    assert "V3.3" not in combined
    assert "Version: unknown" not in combined
