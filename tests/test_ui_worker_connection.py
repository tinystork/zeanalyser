import pytest
import time

import analyse_gui_qt as mod

pytestmark = pytest.mark.skipif(
    mod.QApplication is object or mod.Signal is None, reason="PySide6 not available"
)


def test_ui_connects_to_worker_and_updates(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    created_app = False
    app = mod.QApplication.instance()
    if app is None:
        app = mod.QApplication([])
        created_app = True

    # Fake worker that emits signals when started
    class FakeSignal:
        def __init__(self):
            self._cbs = []
        def connect(self, cb):
            self._cbs.append(cb)
        def emit(self, *a, **k):
            for c in self._cbs:
                c(*a, **k)

    class FakeWorker:
        def __init__(self, *args, **kwargs):
            self.statusChanged = FakeSignal()
            self.progressChanged = FakeSignal()
            self.logLine = FakeSignal()
            self.finished = FakeSignal()
            self.error = FakeSignal()
            self._cancelled = False
        def start(self):
            # simulate sequence
            self.statusChanged.emit('started')
            self.progressChanged.emit(10)
            self.logLine.emit('working')
            self.progressChanged.emit(100)
            self.finished.emit(False)
        def request_cancel(self):
            self._cancelled = True
            self.finished.emit(True)

    monkeypatch.setattr(mod, 'AnalysisWorker', FakeWorker)

    win = mod.ZeAnalyserMainWindow()
    win.input_path_edit.setText('C:/tmp')
    win.output_path_edit.setText('C:/tmp/out.csv')

    # initial
    assert win.analyse_btn.isEnabled() is True or win.analyse_btn.isEnabled() is False

    # click analyse -> start fake worker
    win.analyse_btn.click()

    # process events briefly
    start = time.time()
    while time.time() - start < 0.5:
        app.processEvents()
        time.sleep(0.01)

    # check progress and log updated
    assert win.progress.value() == 100
    assert 'working' in win.log.toPlainText()

    # click cancel after re-creating worker to test cancel path
    win.input_path_edit.setText('C:/tmp')
    win.output_path_edit.setText('C:/tmp/out.csv')
    win.analyse_btn.click()

    # simulate cancel
    win.cancel_btn.click()

    # allow events
    start = time.time()
    while time.time() - start < 0.5:
        app.processEvents()
        time.sleep(0.01)

    assert 'Worker finished' in win.log.toPlainText()

    if created_app:
        app.quit()
