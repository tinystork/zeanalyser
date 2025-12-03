import time
import pytest

import analyse_gui_qt as mod

pytestmark = pytest.mark.skipif(
    mod.QApplication is object or mod.Signal is None, reason="PySide6 not available"
)


def _wait_for(cond, timeout=5.0, interval=0.01):
    start = time.time()
    while time.time() - start < timeout:
        if cond():
            return True
        app = mod.QApplication.instance()
        if app is not None:
            app.processEvents()
        time.sleep(interval)
    return False


def test_ui_runs_real_analysis_without_freeze(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    created_app = False
    app = mod.QApplication.instance()
    if app is None:
        app = mod.QApplication([])
        created_app = True

    # Fake perform_analysis executed in worker thread (sleeps to simulate work)
    def fake_perform(input_dir, output_log, options, callbacks=None):
        callbacks['status']('starting')
        callbacks['progress'](5)
        callbacks['log']('phase1')
        time.sleep(0.05)
        callbacks['progress'](50)
        callbacks['log']('phase2')
        time.sleep(0.05)
        callbacks['progress'](100)
        return ['ok']

    # monkeypatch perform_analysis into analyse_logic so worker.start will use it
    import analyse_logic as logic_mod

    monkeypatch.setattr(logic_mod, 'perform_analysis', fake_perform, raising=False)

    win = mod.ZeAnalyserMainWindow()
    win.input_path_edit.setText('C:/tmp')
    win.output_path_edit.setText('C:/tmp/out.csv')

    # start analysis
    win.analyse_btn.click()

    # wait until progress > 0 and log contains 'phase1'
    ok = _wait_for(lambda: win.progress.value() >= 5 and 'phase1' in win.log.toPlainText(), timeout=3.0)
    assert ok, "UI did not update from worker callbacks"

    # finally wait for finished state AND that results were set in the UI
    ok2 = _wait_for(lambda: 'Worker finished' in win.log.toPlainText() and hasattr(win, '_results_model') and win._results_model.rowCount() >= 1, timeout=5.0)
    assert ok2

    if created_app:
        app.quit()
