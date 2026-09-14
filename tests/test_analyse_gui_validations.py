import pytest

import zeanalyser.analyse_gui_qt as mod
from zeanalyser.zone import translations
pytestmark = pytest.mark.skipif(
    mod.QApplication is object, reason="PySide6 not installed in this environment"
)


def test_move_rejected_requires_dirs(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    created_app = False
    app = mod.QApplication.instance()
    if app is None:
        app = mod.QApplication([])
        created_app = True

    win = mod.ZeAnalyserMainWindow()

    # configure project paths so start_analysis will try to validate
    win.input_path_edit.setText("C:/data/input")
    win.output_path_edit.setText("C:/data/output.log")

    # Explicitly select the mutating action; the fresh default is now none.
    win.reject_move_rb.setChecked(True)
    if win.detect_trails_cb is not None:
        win.detect_trails_cb.setChecked(True)
    # ensure trail_reject_dir is empty
    win.trail_reject_dir_edit.setText("")

    # try to start analysis - because move_rejected=True but trail_reject_dir empty
    # _start_analysis should log an error and not start a worker
    win.analyse_btn.click()

    assert getattr(win, '_current_worker', None) is None
    log_text = win.log.toPlainText()
    assert (
        translations["fr"]["gui_trail_reject_dir_required"] in log_text
        or translations["en"]["gui_trail_reject_dir_required"] in log_text
    )

    if created_app:
        app.quit()
