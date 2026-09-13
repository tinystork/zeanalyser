"""Regression gates for the GUI UX contract cleanup.

The obsolete "Analyze and Stack" (``analyse_and_stack_btn``) and
"Send / Use Best Reference" (``send_save_ref_btn``) actions were removed
from the supported Qt GUI (``src/zeanalyser/analyse_gui_qt.py``).

These gates lock that removal in place and confirm the retained actions are
still wired.  Gates T1-T4 require Qt; gate T5 is a pure source lock and runs
without Qt.
"""

from pathlib import Path

import pytest

import zeanalyser.analyse_gui_qt as mod

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "zeanalyser" / "analyse_gui_qt.py"

# Same guard used elsewhere in the suite: skip Qt-dependent tests when
# PySide6 is not importable (the module falls back to QApplication = object).
requires_qt = pytest.mark.skipif(
    mod.QApplication is object, reason="PySide6 not installed in this environment"
)

REMOVED_IDENTIFIERS = (
    "analyse_and_stack_btn",
    "send_save_ref_btn",
    "_start_analysis_and_stack",
    "_start_stacking_after_analysis",
)


def _make_win(monkeypatch):
    """Create the main window offscreen, reusing the QApplication singleton."""
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = mod.QApplication.instance()
    created_app = False
    if app is None:
        app = mod.QApplication([])
        created_app = True
    win = mod.ZeAnalyserMainWindow()
    return win, created_app


@requires_qt
def test_T1_removed_actions_absent(monkeypatch):
    """T1: the two removed actions must not leave any attribute behind."""
    win, created_app = _make_win(monkeypatch)
    try:
        assert not hasattr(win, "analyse_and_stack_btn")
        assert not hasattr(win, "send_save_ref_btn")
    finally:
        if created_app:
            app = mod.QApplication.instance()
            if app is not None:
                app.quit()


@requires_qt
def test_T2_preserved_actions_present(monkeypatch):
    """T2: every retained bottom-row action must still exist."""
    win, created_app = _make_win(monkeypatch)
    try:
        for name in (
            "analyse_images_btn",
            "open_log_btn",
            "create_stack_plan_btn",
            "manage_markers_btn",
            "visualise_results_btn",
            "apply_recos_btn",
            "quit_btn",
        ):
            assert hasattr(win, name), name
    finally:
        if created_app:
            app = mod.QApplication.instance()
            if app is not None:
                app.quit()


@requires_qt
def test_T3_analyse_wired_to_plain_analysis_only(monkeypatch):
    """T3: ``analyse_images_btn`` drives plain analysis, never stacking.

    Observable behaviour: patch the class slot before construction so the
    construction-time signal connection binds to the recorder, then click the
    button.  No stacking flag may appear, before or after a simulated run.
    """
    calls = []
    monkeypatch.setattr(
        mod.ZeAnalyserMainWindow,
        "_start_analysis",
        lambda self: calls.append(self),
        raising=True,
    )
    win, created_app = _make_win(monkeypatch)
    try:
        win.analyse_images_btn.click()
        assert calls, "analyse_images_btn must be wired to _start_analysis"
        assert not hasattr(win, "_stack_after_analysis")

        # Drive a simulated run to completion; stacking must never be injected.
        win._start_fake_run()
        while win._progress_value < 100:
            win._tick()
        assert getattr(win, "_stack_after_analysis", False) is False
        assert not hasattr(win, "_stack_after_analysis")
    finally:
        if created_app:
            app = mod.QApplication.instance()
            if app is not None:
                app.quit()


@requires_qt
def test_T4_stack_plan_entry_point_available(monkeypatch):
    """T4: the stack-plan entry point survives independent of the removals."""
    win, created_app = _make_win(monkeypatch)
    try:
        assert hasattr(win, "create_stack_plan_btn")
        assert callable(getattr(win, "open_stack_plan_window"))
    finally:
        if created_app:
            app = mod.QApplication.instance()
            if app is not None:
                app.quit()


def test_T5_source_lock_no_stale_wiring():
    """T5: no removed identifier may remain anywhere in the GUI source."""
    src = SOURCE.read_text(encoding="utf-8")
    for identifier in REMOVED_IDENTIFIERS:
        assert identifier not in src, f"stale identifier still present: {identifier}"
