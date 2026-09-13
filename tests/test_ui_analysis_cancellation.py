import time
import pytest

import zeanalyser.analyse_gui_qt as mod
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

    import zeanalyser.analyse_logic as logic_mod
    # monkeypatch the real logic to our long running implementation
    monkeypatch.setattr(logic_mod, 'perform_analysis', long_perform, raising=False)

    win = mod.ZeAnalyserMainWindow()
    win.input_path_edit.setText('C:/tmp')
    win.output_path_edit.setText('C:/tmp/out.csv')
    win.reject_delete_rb.setChecked(True)

    # start analysis
    win.analyse_btn.click()

    # wait until some progress logged
    ok = _wait_for(lambda: 'entering long perform' in win.log.toPlainText(), timeout=2.0)
    assert ok, "Long perform did not start"

    # get worker and request cancel
    worker = getattr(win, '_current_worker')
    assert worker is not None
    finished = []
    published_results = []
    progress = []
    worker.finished.connect(finished.append)
    worker.resultsReady.connect(published_results.append)
    worker.progressChanged.connect(progress.append)

    # The GUI transition is immediate, but completion is not: request_cancel
    # only sets the cooperative token while the callable is still active.
    win._cancel_current_worker()
    assert worker._cancel_event.is_set()
    assert finished == []
    assert win.cancel_btn.isEnabled() is False
    assert win.analyse_btn.isEnabled() is False
    assert win.statusBar().currentMessage() == mod._("status_analysis_cancelling")

    ok2 = _wait_for(lambda: 'fake_perform_detect_cancel' in win.log.toPlainText(), timeout=2.0)
    assert ok2, "perform_analysis did not detect cancel via callbacks['is_cancelled']"

    # final finished notification must indicate cancelled True (per AnalysisWorker behavior)
    ok3 = _wait_for(lambda: 'Worker finished: cancelled=True' in win.log.toPlainText(), timeout=2.0)
    if not ok3:
        ok3 = _wait_for(lambda: mod._("logic_analysis_cancelled") in win.log.toPlainText(), timeout=2.0)
    assert ok3, "Worker did not finish with cancelled=True"
    assert finished == [True]
    assert published_results == []
    assert 100.0 not in progress
    assert win.progress.value() < 100
    assert win.analyse_btn.isEnabled() is True

    if created_app:
        app.quit()
