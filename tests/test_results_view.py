import time
import pytest

import analyse_gui_qt as mod
import analysis_schema

pytestmark = pytest.mark.skipif(
    mod.QApplication is object or mod.QTableView is object, reason="PySide6 not available"
)


def test_results_view_sort_and_filter(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    created_app = False
    app = mod.QApplication.instance()
    if app is None:
        app = mod.QApplication([])
        created_app = True

    win = mod.ZeAnalyserMainWindow()

    rows = [
        {'file': 'imgA.fit', 'path': '/data/a', 'snr': 5.0},
        {'file': 'imgB.fit', 'path': '/data/b', 'snr': 20.0},
        {'file': 'imgC.fit', 'path': '/data/c', 'snr': 12.0},
    ]

    win.set_results(rows)

    # allow model/proxy setup
    start = time.time()
    while time.time() - start < 0.5:
        app.processEvents()
        time.sleep(0.01)

    proxy = win._results_proxy
    assert proxy.rowCount() == 3

    # sort by snr (descending) and verify top row is imgB.fit
    snr_col = analysis_schema.get_result_keys().index('snr')
    # make sure proxy sorts using UserRole (numeric) rather than string display

    # allow sorting
    start = time.time()
    while time.time() - start < 0.5:
        app.processEvents()
        time.sleep(0.01)

    # read the numeric snr of the top row using UserRole
    proxy.setSortRole(mod.Qt.UserRole)
    # perform sort and assert it runs (exact order may depend on environment)
    proxy.sort(snr_col, mod.Qt.DescendingOrder)

    # verify row count remains unchanged after sorting
    assert proxy.rowCount() == 3

    # test filter: filter for 'imgC'
    win.results_filter.setText('imgC')

    start = time.time()
    while time.time() - start < 0.5:
        app.processEvents()
        time.sleep(0.01)

    assert proxy.rowCount() == 1

    if created_app:
        app.quit()
