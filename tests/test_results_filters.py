import time
import pytest

import analyse_gui_qt as mod

pytestmark = pytest.mark.skipif(
    mod.QApplication is object or mod.QTableView is object, reason="PySide6 not available"
)


def _pump(app, wait=0.3):
    start = time.time()
    while time.time() - start < wait:
        app.processEvents()
        time.sleep(0.01)


def test_numeric_and_boolean_filters(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    created_app = False
    app = mod.QApplication.instance()
    if app is None:
        app = mod.QApplication([])
        created_app = True

    win = mod.ZeAnalyserMainWindow()

    rows = [
        {'file': 'imgA.fit', 'path': '/data/a', 'snr': 5.0, 'fwhm': 2.0, 'ecc': 0.1, 'has_trails': False},
        {'file': 'imgB.fit', 'path': '/data/b', 'snr': 20.0, 'fwhm': 1.2, 'ecc': 0.05, 'has_trails': True},
        {'file': 'imgC.fit', 'path': '/data/c', 'snr': 12.0, 'fwhm': 2.5, 'ecc': 0.3, 'has_trails': False},
        {'file': 'imgD.fit', 'path': '/data/d', 'snr': None, 'fwhm': None, 'ecc': None, 'has_trails': False},
    ]

    win.set_results(rows)

    _pump(app)

    proxy = win._results_proxy
    assert proxy.rowCount() == 4

    # SNR >= 10 -> B and C
    win.snr_min_edit.setText('10')
    _pump(app)
    assert proxy.rowCount() == 2

    # Clear and test SNR <= 10 -> A only
    win.snr_min_edit.setText('')
    win.snr_max_edit.setText('10')
    _pump(app)
    assert proxy.rowCount() == 1

    # Clear SNR, test FWHM <= 2.0 -> A and B
    win.snr_max_edit.setText('')
    win.fwhm_max_edit.setText('2.0')
    _pump(app)
    assert proxy.rowCount() == 2

    # Clear FWHM, test ECC <= 0.1 -> A and B (0.1 and 0.05)
    win.fwhm_max_edit.setText('')
    win.ecc_max_edit.setText('0.1')
    _pump(app)
    assert proxy.rowCount() == 2

    # Test has_trails = Yes -> only B
    win.ecc_max_edit.setText('')
    win.has_trails_box.setCurrentText('Yes')
    _pump(app)
    assert proxy.rowCount() == 1

    # Test has_trails = No -> A,C,D
    win.has_trails_box.setCurrentText('No')
    _pump(app)
    assert proxy.rowCount() == 3

    if created_app:
        app.quit()
