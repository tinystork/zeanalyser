import os
import sys
import time
import pathlib

import numpy as np
from astropy.io import fits
from PIL import Image

import pytest

# Ensure repository root is on sys.path so top-level modules import reliably during test runs
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import zeanalyser.analyse_gui_qt as mod


needs_qt = pytest.mark.skipif(
    mod.QApplication is object, reason="PySide6 not installed in this environment"
)


def _write_test_fits(tmpdir, name="a.fits"):
    arr = np.arange(100, dtype=float).reshape((10, 10))
    p = os.path.join(tmpdir, name)
    fits.writeto(p, arr, overwrite=True)
    return p


def _write_test_png(tmpdir, name="b.png"):
    arr = (np.arange(64, dtype=np.uint8).reshape((8, 8))).repeat(4, axis=0).repeat(4, axis=1)
    img = Image.fromarray(arr)
    p = os.path.join(tmpdir, name)
    img.save(p)
    return p


def _get_app(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    created_app = False
    app = mod.QApplication.instance()
    if app is None:
        app = mod.QApplication([])
        created_app = True
    return app, created_app


def _wait_until(cond, app, timeout=10.0, interval=0.01):
    """Process Qt events until cond() is true or the bounded timeout expires."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if cond():
            return True
        try:
            app.processEvents()
        except Exception:
            pass
        time.sleep(interval)
    return False


# --- path resolution contract (pure, no Qt required) -------------------------

def test_resolve_explicit_file_path():
    assert mod.resolve_row_file_path({'file': 'a.fits', 'file_path': '/data/a.fits'}) == '/data/a.fits'


def test_resolve_canonical_path_full_file():
    # canonical: path is the complete file path, file is its basename
    assert mod.resolve_row_file_path({'file': 'a.fits', 'path': '/data/a.fits'}) == '/data/a.fits'


def test_resolve_canonical_missing_file_no_double_name():
    # a canonical path whose file does not exist yet must NOT become path/file/file
    assert mod.resolve_row_file_path({'file': 'missing.fits', 'path': '/data/missing.fits'}) == '/data/missing.fits'


def test_resolve_legacy_directory_plus_name():
    # legacy: path is a directory, file is the name inside it
    assert mod.resolve_row_file_path({'file': 'a.fits', 'path': '/data/dir'}) == '/data/dir/a.fits'


def test_resolve_path_only():
    assert mod.resolve_row_file_path({'path': '/data/a.fits'}) == '/data/a.fits'


def test_resolve_empty():
    assert mod.resolve_row_file_path({}) == ''
    assert mod.resolve_row_file_path(None) == ''


# --- ZeViewer async contract (Qt required) -----------------------------------

@needs_qt
def test_preview_loader_headless(tmp_path, monkeypatch):
    app, created_app = _get_app(monkeypatch)

    fits_path = _write_test_fits(str(tmp_path), "test_img.fits")
    png_path = _write_test_png(str(tmp_path), "test_img.png")

    win = mod.ZeAnalyserMainWindow()
    try:
        viewer = win.zeviewer
        assert viewer is not None, "ZeViewer must be present when Qt is available"

        # canonical rows: path = complete file path, file = basename
        rows = [
            {'file': 'test_img.fits', 'path': fits_path},
            {'file': 'test_img.png', 'path': png_path},
        ]
        win.set_results(rows)

        # FITS
        ok = win.select_result_row_by_file('test_img.fits')
        assert ok is True
        assert win._preview_last_path == os.path.abspath(fits_path)
        assert _wait_until(lambda: viewer.has_image() and viewer._hist is not None, app)
        assert viewer.current_path() == os.path.abspath(fits_path)
        assert viewer.has_image() is True
        assert viewer._linear_ds is not None
        assert viewer._display_u8 is not None
        assert isinstance(viewer._hist, dict)
        assert 'counts' in viewer._hist and 'edges' in viewer._hist

        # PNG (wait for a new async result, not the stale FITS one)
        old_hist = viewer._hist
        ok2 = win.select_result_row_by_file('test_img.png')
        assert ok2 is True
        assert win._preview_last_path == os.path.abspath(png_path)
        assert _wait_until(lambda: viewer._hist is not old_hist, app)
        assert viewer.current_path() == os.path.abspath(png_path)
        assert viewer.has_image() is True
        assert viewer._linear_ds is not None
        assert viewer._display_u8 is not None
        assert isinstance(viewer._hist, dict)
        assert 'counts' in viewer._hist and 'edges' in viewer._hist
    finally:
        try:
            viewer = getattr(win, 'zeviewer', None)
            if viewer is not None:
                try:
                    viewer._thread_pool.waitForDone(5000)
                except Exception:
                    pass
            win.close()
        except Exception:
            pass
        if created_app:
            app.quit()


@needs_qt
def test_preview_missing_file_witness(tmp_path, monkeypatch):
    app, created_app = _get_app(monkeypatch)

    missing = os.path.join(str(tmp_path), "missing.fits")

    win = mod.ZeAnalyserMainWindow()
    try:
        viewer = win.zeviewer
        assert viewer is not None

        rows = [{'file': 'missing.fits', 'path': missing}]
        win.set_results(rows)

        ok = win.select_result_row_by_file('missing.fits')
        assert ok is True
        # canonical missing path must not be doubled into path/file/file
        assert win._preview_last_path == os.path.abspath(missing)
        # the viewer holds the exact missing path but no image and no histogram
        assert viewer.current_path() == os.path.abspath(missing)
        assert viewer.has_image() is False
        assert viewer._hist is None
        # a visible failure state is reported
        assert viewer.status_label.text().strip() != ""
    finally:
        try:
            win.close()
        except Exception:
            pass
        if created_app:
            app.quit()


@needs_qt
def test_select_results_row_for_path_canonical(tmp_path, monkeypatch):
    app, created_app = _get_app(monkeypatch)

    fits_path = _write_test_fits(str(tmp_path), "nav.fits")

    win = mod.ZeAnalyserMainWindow()
    try:
        rows = [{'file': 'nav.fits', 'path': fits_path}]
        win.set_results(rows)

        # canonical path must map back to the matching row (no path/file/file)
        assert win._select_results_row_for_path(fits_path) is True
        # an unknown path must not select anything
        assert win._select_results_row_for_path(os.path.join(str(tmp_path), "nope.fits")) is False
    finally:
        try:
            win.close()
        except Exception:
            pass
        if created_app:
            app.quit()
