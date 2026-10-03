"""Targeted tests for the Bortle base raster file picker in the Qt GUI.

These tests exercise the wiring of ``self.bortle_browse_btn`` to
``_choose_bortle_file`` and validate parent/filter/start-dir behaviour
without requiring a real raster file to exist on disk.
"""
import os
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

import zeanalyser.analyse_gui_qt as mod

pytestmark = pytest.mark.skipif(
    mod.QApplication is object, reason="PySide6 not installed in this environment"
)


def _make_window(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    created_app = False
    app = mod.QApplication.instance()
    if app is None:
        app = mod.QApplication([])
        created_app = True
    win = mod.ZeAnalyserMainWindow()
    return win, app, created_app


def test_bortle_browse_click_opens_dialog_and_fills_path(monkeypatch):
    captured = {}

    def fake_open(parent, title, start_dir, filter_str):
        captured["parent"] = parent
        captured["title"] = title
        captured["start_dir"] = start_dir
        captured["filter"] = filter_str
        return ("/tmp/bortle_map.tif", "GeoTIFF/KMZ (*.tif *.tiff *.kmz)")

    monkeypatch.setattr(mod.QFileDialog, "getOpenFileName", fake_open)

    win, app, created_app = _make_window(monkeypatch)
    try:
        assert win.bortle_browse_btn is not None
        win.bortle_browse_btn.click()

        # exactly QFileDialog.getOpenFileName with parent self
        assert captured["parent"] is win
        # portable explicit filter: tif/tiff/kmz + all files
        assert "*.tif" in captured["filter"]
        assert "*.tiff" in captured["filter"]
        assert "*.kmz" in captured["filter"]
        assert "All Files" in captured["filter"]
        # non-empty selection fills the field verbatim
        assert win.bortle_path_edit.text() == "/tmp/bortle_map.tif"
    finally:
        try:
            win.close()
        except Exception:
            pass
        if created_app:
            app.quit()


def test_bortle_browse_cancel_preserves_field(monkeypatch):
    monkeypatch.setattr(
        mod.QFileDialog, "getOpenFileName", lambda *args, **kwargs: ("", "")
    )

    win, app, created_app = _make_window(monkeypatch)
    try:
        win.bortle_path_edit.setText("/tmp/existing_bortle.tif")
        win.bortle_browse_btn.click()
        assert win.bortle_path_edit.text() == "/tmp/existing_bortle.tif"
    finally:
        try:
            win.close()
        except Exception:
            pass
        if created_app:
            app.quit()


def test_bortle_browse_start_dir_derived_from_existing_path(monkeypatch, tmp_path):
    captured = {}

    def fake_open(parent, title, start_dir, filter_str):
        captured["start_dir"] = start_dir
        return ("", "")

    monkeypatch.setattr(mod.QFileDialog, "getOpenFileName", fake_open)

    win, app, created_app = _make_window(monkeypatch)
    try:
        # A non-existent file path must still yield its parent directory,
        # without requiring the raster to exist on disk.
        win.bortle_path_edit.setText("/some/data_dir/bortle.tif")
        win.bortle_browse_btn.click()
        assert captured["start_dir"] == "/some/data_dir"

        # An existing directory path must be reused as-is.
        real_dir = tmp_path / "real_dir"
        real_dir.mkdir()
        win.bortle_path_edit.setText(str(real_dir))
        win.bortle_browse_btn.click()
        assert captured["start_dir"] == str(real_dir)
    finally:
        try:
            win.close()
        except Exception:
            pass
        if created_app:
            app.quit()


def test_bortle_browse_start_dir_fallback_to_home(monkeypatch):
    captured = {}

    def fake_open(parent, title, start_dir, filter_str):
        captured["start_dir"] = start_dir
        return ("", "")

    monkeypatch.setattr(mod.QFileDialog, "getOpenFileName", fake_open)

    win, app, created_app = _make_window(monkeypatch)
    try:
        win.bortle_path_edit.setText("")
        win.bortle_browse_btn.click()
        assert captured["start_dir"] == os.path.expanduser("~")
    finally:
        try:
            win.close()
        except Exception:
            pass
        if created_app:
            app.quit()


def test_bortle_browse_persists_without_polluting_user_settings(monkeypatch, tmp_path):
    """Persist the chosen path via isolated QSettings (temp INI)."""
    from PySide6.QtCore import QSettings as _QS

    ini_path = str(tmp_path / "isolated_settings.ini")

    def isolated_settings():
        return _QS(ini_path, _QS.IniFormat)

    monkeypatch.setattr(mod, "QSettings", isolated_settings)
    monkeypatch.setattr(
        mod.QFileDialog,
        "getOpenFileName",
        lambda *args, **kwargs: ("/tmp/bortle_map.kmz", "GeoTIFF/KMZ (*.tif *.tiff *.kmz)"),
    )

    win, app, created_app = _make_window(monkeypatch)
    try:
        win.bortle_browse_btn.click()
        assert win.bortle_path_edit.text() == "/tmp/bortle_map.kmz"
        # persistence landed in the isolated settings, not the user's
        stored = _QS(ini_path, _QS.IniFormat).value("paths/bortle", "")
        assert stored == "/tmp/bortle_map.kmz"
    finally:
        try:
            win.close()
        except Exception:
            pass
        if created_app:
            app.quit()
