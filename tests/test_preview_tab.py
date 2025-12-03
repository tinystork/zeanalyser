import os
import tempfile
import numpy as np
from astropy.io import fits
from PIL import Image

import sys
import pathlib
# Ensure repository root is on sys.path so top-level modules import reliably during test runs
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import analyse_gui_qt as mod


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


def test_preview_loader_headless(tmp_path):
    # Create sample FITS and PNG files
    fits_path = _write_test_fits(str(tmp_path), "test_img.fits")
    png_path = _write_test_png(str(tmp_path), "test_img.png")

    # If Qt is available we must ensure a QApplication exists before constructing widgets
    created_app = False
    app = getattr(mod, 'QApplication', None)
    if app is not None and app is not object:
        current = app.instance()
        if current is None:
            app = mod.QApplication([])
            created_app = True

    win = mod.ZeAnalyserMainWindow()

    # set results using file_path so loader can find files
    rows = [
        {'file': 'test_img.fits', 'file_path': fits_path},
        {'file': 'test_img.png', 'file_path': png_path},
    ]

    win.set_results(rows)

    # headless: use the convenience helper
    ok = win.select_result_row_by_file('test_img.fits')
    assert ok is True
    assert getattr(win, '_preview_last_path', None) is not None
    assert win._preview_last_path == fits_path
    assert getattr(win, '_preview_last_histogram', None) is not None
    assert isinstance(win._preview_last_histogram, tuple)

    ok2 = win.select_result_row_by_file('test_img.png')
    assert ok2 is True
    assert win._preview_last_path == png_path
    assert getattr(win, '_preview_last_histogram', None) is not None
    assert isinstance(win._preview_last_histogram, tuple)

    if created_app:
        app.quit()
