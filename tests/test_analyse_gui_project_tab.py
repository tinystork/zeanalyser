import pytest

import analyse_gui_qt as mod


pytestmark = pytest.mark.skipif(
    mod.QApplication is object, reason="PySide6 not installed in this environment"
)


def test_project_tab_file_pickers_and_analyse_enable(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    # Mock file dialogs
    monkeypatch.setattr(mod.QFileDialog, "getExistingDirectory", lambda *_: "C:/data/input_folder")
    monkeypatch.setattr(mod.QFileDialog, "getSaveFileName", lambda *_: ("C:/data/output.log", "Log Files (*.log)"))

    created_app = False
    app = mod.QApplication.instance()
    if app is None:
        app = mod.QApplication([])
        created_app = True
    win = mod.ZeAnalyserMainWindow()

    # initial state: analyse disabled
    assert win.analyse_btn.isEnabled() is False

    # press input button - Qt should prefill a default log path inside the input folder
    win.input_btn.click()
    assert win.input_path_edit.text() == "C:/data/input_folder"
    import os
    expected_default = os.path.join("C:/data/input_folder", "analyse_resultats.log")
    assert win.output_path_edit.text() == expected_default
    assert win.analyse_btn.isEnabled() is True

    # press output button (user chooses their own log file)
    win.output_btn.click()
    assert win.output_path_edit.text() == "C:/data/output.log"

    # now analysis should be enabled
    assert win.analyse_btn.isEnabled() is True

    # start analysis and finish immediately by driving _tick
    win.analyse_btn.click()
    while win._progress_value < 100:
        win._tick()

    assert win.progress.value() == 100

    if created_app:
        app.quit()
