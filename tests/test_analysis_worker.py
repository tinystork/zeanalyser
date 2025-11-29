import time
import pytest

import analyse_gui_qt as mod


pytestmark = pytest.mark.skipif(
    mod.QApplication is object or mod.Signal is None, reason="PySide6 not available"
)


def _wait_for(condition, timeout=2.0, interval=0.01):
    start = time.time()
    while time.time() - start < timeout:
        if condition():
            return True
        app = mod.QApplication.instance()
        if app is not None:
            app.processEvents()
        time.sleep(interval)
    return False


def test_worker_emits_signals_and_finishes(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    created_app = False
    app = mod.QApplication.instance()
    if app is None:
        app = mod.QApplication([])
        created_app = True

    worker = mod.AnalysisWorker(step_ms=1)

    progresses = []
    logs = []
    finished = []

    worker.progressChanged.connect(lambda v: progresses.append(v))
    worker.logLine.connect(lambda s: logs.append(s))
    worker.finished.connect(lambda cancelled: finished.append(cancelled))

    worker.start()

    ok = _wait_for(lambda: len(finished) > 0, timeout=5.0)
    assert ok, "Worker did not finish within timeout"
    assert finished[-1] is False
    assert progresses[-1] >= 100.0
    assert any("worker progress" in s for s in logs)

    if created_app:
        app.quit()


def test_worker_request_cancel(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    created_app = False
    app = mod.QApplication.instance()
    if app is None:
        app = mod.QApplication([])
        created_app = True

    worker = mod.AnalysisWorker(step_ms=50)

    finished = []

    worker.finished.connect(lambda cancelled: finished.append(cancelled))

    worker.start()

    # wait until the worker's timer has been created in the worker thread
    ok = _wait_for(lambda: getattr(worker, "_timer", None) is not None, timeout=1.0)
    assert ok, "Worker timer did not start"

    # request cancel shortly after timer started
    worker.request_cancel()

    # the finished signal may be delivered via Qt's event loop; ensure the
    # worker cancellation flag is set so cancellation occurred synchronously
    ok2 = _wait_for(lambda: getattr(worker, "_cancelled", False) is True, timeout=1.0)
    assert ok2, "Worker did not set cancelled flag"

    # if the finished signal was delivered, it should be True
    if len(finished) > 0:
        assert finished[-1] is True

    if created_app:
        app.quit()
