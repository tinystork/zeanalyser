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
        app = mod.QApplication.instance()
        if app is not None:
            app.processEvents()
        time.sleep(interval)
    return False


def test_qrunnable_worker_emits_signals(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    created_app = False
    app = mod.QApplication.instance()
    if app is None:
        app = mod.QApplication([])
        created_app = True

    def fake_analysis(*args, callbacks=None, **kwargs):
        callbacks['status']('s')
        callbacks['progress'](25)
        callbacks['log']('hello')
        callbacks['progress'](100)
        return 0

    runnable = mod.AnalysisRunnable(fake_analysis, 'a', 'b')

    progresses = []
    logs = []
    finished = []

    runnable.signals.progressChanged.connect(lambda v: progresses.append(v))
    runnable.signals.logLine.connect(lambda s: logs.append(s))
    runnable.signals.finished.connect(lambda c: finished.append(c))

    pool = mod.QThreadPool.globalInstance()
    pool.start(runnable)

    # wait for pool tasks to finish (timeout in milliseconds)
    pool.waitForDone(3000)

    # give Qt main loop a moment to dispatch queued signals
    app = mod.QApplication.instance()
    start = time.time()
    while time.time() - start < 0.5 and len(finished) == 0:
        if app is not None:
            app.processEvents()
        time.sleep(0.01)

    assert len(finished) > 0
    assert finished[-1] is False
    assert 100.0 in progresses
    assert 'hello' in logs

    if created_app:
        app.quit()
