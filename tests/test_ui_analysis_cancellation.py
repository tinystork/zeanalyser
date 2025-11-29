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


def test_ui_perform_analysis_respects_cancel(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    created_app = False
    app = mod.QApplication.instance()
    if app is None:
        app = mod.QApplication([])
        created_app = True

    # A long-running perform_analysis that checks callbacks['is_cancelled']
    def long_perform(input_dir, output_log, options, callbacks=None):
        # report start
        if callbacks:
            callbacks['status']('starting_long')
            callbacks['log']('entering long perform')
        # simulate many steps but react to cancellation
        for i in range(100):
            # check for cancellation via callback helper
            if callbacks and callbacks.get('is_cancelled') and callbacks['is_cancelled']():
                if callbacks:
                    callbacks['log']('fake_perform_detect_cancel')
                    callbacks['status']('cancelled_by_request')
                # return early due to cancellation
                return ['cancelled']
            if callbacks:
                callbacks['progress'](i)
                callbacks['log'](f'step_{i}')
            time.sleep(0.005)
        return ['ok']

    import analyse_logic as logic_mod
    # monkeypatch the real logic to our long running implementation
    monkeypatch.setattr(logic_mod, 'perform_analysis', long_perform, raising=False)

    win = mod.ZeAnalyserMainWindow()
    win.input_path_edit.setText('C:/tmp')
    win.output_path_edit.setText('C:/tmp/out.csv')

    # start analysis
    win.analyse_btn.click()

    # wait until some progress logged
    ok = _wait_for(lambda: 'entering long perform' in win.log.toPlainText(), timeout=2.0)
    assert ok, "Long perform did not start"

    # get worker and request cancel
    worker = getattr(win, '_current_worker')
    assert worker is not None

    # request cancel and ensure the perform loop detects cancellation
    worker.request_cancel()

    ok2 = _wait_for(lambda: 'fake_perform_detect_cancel' in win.log.toPlainText(), timeout=2.0)
    assert ok2, "perform_analysis did not detect cancel via callbacks['is_cancelled']"

    # final finished notification must indicate cancelled True (per AnalysisWorker behavior)
    ok3 = _wait_for(lambda: 'Worker finished: cancelled=True' in win.log.toPlainText(), timeout=2.0)
    assert ok3, "Worker did not finish with cancelled=True"

    if created_app:
        app.quit()
