import pytest

import analyse_gui_qt as mod


pytestmark = pytest.mark.skipif(
    mod.QApplication is object, reason="PySide6 not installed in this environment"
)


def test_create_mainwindow_and_simulate_run(monkeypatch):
    # Force headless Qt (CI environments)
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    # reuse existing QApplication singleton if present (tests may run in same process)
    created_app = False
    app = mod.QApplication.instance()
    if app is None:
        app = mod.QApplication([])
        created_app = True
    win = mod.ZeAnalyserMainWindow()

    # basic UI elements exist
    assert hasattr(win, "analyse_btn")
    assert hasattr(win, "progress")
    assert hasattr(win, "log")

    # start simulated run and drive it manually to completion
    win._start_fake_run()

    # ensure progress increments and we can finish without real timer
    while win._progress_value < 100:
        # call _tick directly to avoid timer/waiting
        win._tick()

    assert win._progress_value >= 100
    assert win.progress.value() == 100

    # Ensure UI toggles back to non-running state
    assert win.analyse_btn.isEnabled() is True

    # tidy up only if we created the QApplication
    if created_app:
        app.quit()
