import pytest

import analyse_gui_qt as mod


pytestmark = pytest.mark.skipif(
    mod.QApplication is object, reason="PySide6 not installed in this environment"
)


def test_main_runs_and_exits_headless(monkeypatch):
    """Call main() with run_for so the event loop quits automatically.

    This test uses the offscreen platform to avoid needing a display in CI.
    """
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    # main should return an integer exit code (0 on normal exit)
    rc = mod.main(argv=[], run_for=20)
    assert isinstance(rc, int)
    assert rc == 0
