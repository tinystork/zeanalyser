import time
import pytest

import analyse_gui_qt as mod


pytestmark = pytest.mark.skipif(
    mod.QApplication is object or mod.Signal is None, reason="PySide6 not available"
)


def _wait_for(cond, timeout=2.0, interval=0.01):
    start = time.time()
    while time.time() - start < timeout:
        if cond():
            return True
        # process Qt events so queued signals are delivered
        app = mod.QApplication.instance()
        if app is not None:
            app.processEvents()
        time.sleep(interval)
    return False


def test_worker_runs_integration_callable(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    created_app = False
    app = mod.QApplication.instance()
    if app is None:
        app = mod.QApplication([])
        created_app = True

    # create a fake analysis function which uses the callbacks
    def fake_analysis(input_dir, output_log, options, callbacks=None):
        callbacks['status']('starting')
        callbacks['progress'](10)
        callbacks['log']('step1')
        callbacks['progress'](50)
        callbacks['log']('step2')
        callbacks['progress'](100)
        return ['result']

    worker = mod.AnalysisWorker()

    progresses = []
    logs = []
    finished = []

    worker.progressChanged.connect(lambda v: progresses.append(v))
    worker.logLine.connect(lambda s: logs.append(s))
    worker.finished.connect(lambda c: finished.append(c))

    # pass the analysis callable as the first positional argument so start()
    # receives it in the 'analysis_callable' slot and following args are forwarded
    worker.start(fake_analysis, 'in', 'out', {})

    ok = _wait_for(lambda: len(finished) > 0, timeout=3.0)
    assert ok
    assert finished[-1] is False
    assert 100.0 in progresses
    assert 'step1' in logs and 'step2' in logs

    if created_app:
        app.quit()
