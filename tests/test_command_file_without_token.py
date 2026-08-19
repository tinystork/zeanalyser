"""Regression tests: modern command-file channel must not depend on token.zsss.

When ZeAnalyser is launched with a valid public command-file channel
(``ZEANALYSER_COMMAND_FILE`` env var or ``command_file_path`` constructor
arg), the REFERENCE= return channel must be available even when the legacy
``token.zsss`` file is absent.  The legacy token only gates the historical
direct-stacking workflow.
"""

import os
import pytest

import zeanalyser.analyse_gui_qt as mod

pytestmark = pytest.mark.skipif(
    mod.QApplication is object, reason="PySide6 not installed in this environment"
)


def _make_win(monkeypatch, tmp_path, command_file_path=None):
    """Build a ZeAnalyserMainWindow with no token anywhere and a clean
    command-file state, in offscreen mode."""
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    # Isolate token discovery: point the explicit token dir at an empty
    # folder and give HOME a fresh empty temp dir so no ~/token.zsss leaks.
    monkeypatch.setenv("ZEANALYSER_ZSSS_TOKEN_DIR", str(tmp_path / "no_token"))
    monkeypatch.setenv("HOME", str(tmp_path / "fake_home"))
    os.makedirs(tmp_path / "no_token", exist_ok=True)
    os.makedirs(tmp_path / "fake_home", exist_ok=True)
    if command_file_path is not None:
        monkeypatch.setenv("ZEANALYSER_COMMAND_FILE", command_file_path)
    else:
        monkeypatch.delenv("ZEANALYSER_COMMAND_FILE", raising=False)
    app = mod.QApplication.instance() or mod.QApplication([])
    win = mod.ZeAnalyserMainWindow(command_file_path=command_file_path)
    return win


def test_command_channel_available_without_token(monkeypatch, tmp_path):
    """token absent + command file present → channel available, token not."""
    cmd_file = str(tmp_path / "analyzer_stack_command.txt")
    win = _make_win(monkeypatch, tmp_path, command_file_path=cmd_file)

    assert win.parent_token_available is False
    assert win.command_channel_available is True


def test_send_reference_writes_command_file_without_token(monkeypatch, tmp_path):
    """REFERENCE= must be returned through the command file even without
    token.zsss (this is the Zsss → ZeAnalyser integration path)."""
    cmd_file = str(tmp_path / "analyzer_stack_command.txt")
    win = _make_win(monkeypatch, tmp_path, command_file_path=cmd_file)

    # Simulate completed analysis results with a best reference.
    win.set_results(
        [
            {"status": "ok", "snr": 12.5, "path": "/data/best_ref.fit"},
            {"status": "ok", "snr": 8.1, "path": "/data/other.fit"},
        ]
    )

    win.send_reference_to_main()

    content = ""
    with open(cmd_file, "r", encoding="utf-8") as f:
        content = f.read()
    assert "REFERENCE=/data/best_ref.fit" in content


def test_send_reference_button_enabled_without_token(monkeypatch, tmp_path):
    """The send-reference button must be enabled when a command-file channel
    exists, even if token.zsss is absent."""
    cmd_file = str(tmp_path / "analyzer_stack_command.txt")
    win = _make_win(monkeypatch, tmp_path, command_file_path=cmd_file)

    win.set_results(
        [
            {"status": "ok", "snr": 12.5, "path": "/data/best_ref.fit"},
        ]
    )
    # Re-run the state update the GUI performs after analysis.
    win._update_buttons_after_analysis()

    assert win.send_save_ref_btn.isEnabled() is True


def test_command_channel_unavailable_without_token_and_file(monkeypatch, tmp_path):
    """Without token and without a command file, the channel is unavailable
    and the reference button stays disabled."""
    win = _make_win(monkeypatch, tmp_path, command_file_path=None)

    assert win.parent_token_available is False
    assert win.command_channel_available is False

    win.set_results(
        [
            {"status": "ok", "snr": 12.5, "path": "/data/best_ref.fit"},
        ]
    )
    win._update_buttons_after_analysis()
    assert win.send_save_ref_btn.isEnabled() is False
