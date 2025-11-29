import time
import os
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


def test_start_with_empty_output_defaults_to_input_log(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    # mock folder choose
    monkeypatch.setattr(mod.QFileDialog, "getExistingDirectory", lambda *_: "C:/data/input_folder")

    created_app = False
    app = mod.QApplication.instance()
    if app is None:
        app = mod.QApplication([])
        created_app = True

    win = mod.ZeAnalyserMainWindow()

    # simulate user selecting input folder; Qt should prefill default log path
    win.input_btn.click()
    expected_default = os.path.join("C:/data/input_folder", "analyse_resultats.log")
    assert win.output_path_edit.text() == expected_default

    # clear output explicitly, then start analysis - start should default again
    win.output_path_edit.setText("")
    assert win.analyse_btn.isEnabled() is True

    win.analyse_btn.click()

    # run ticks until complete
    while win._progress_value < 100:
        win._tick()

    assert win.progress.value() == 100
    # after starting, the output field should be set to the default again
    assert win.output_path_edit.text() == expected_default

    if created_app:
        app.quit()
