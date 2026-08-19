"""Regression test for the ``--lang fr --lock-lang`` launch path.

ZeAnalyserMainWindow.__init__ used to declare a parameter named
``lock_language`` which shadowed the module-level ``lock_language()``
function.  When ``--lock-lang`` was passed, the constructor called the
boolean parameter instead of the function, raising
``TypeError: 'bool' object is not callable``.

The parameter is now named ``lock_language_enabled`` (legacy keyword
``lock_language=`` is still accepted for backward compatibility).  These
tests cover the exact launch combination that triggered the bug.
"""

import pytest

import zeanalyser.analyse_gui_qt as mod

pytestmark = pytest.mark.skipif(
    mod.QApplication is object, reason="PySide6 not installed in this environment"
)


def _ensure_offscreen(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")


def test_cli_main_with_lang_fr_and_lock_lang_does_not_crash(monkeypatch):
    """``main(["--lang", "fr", "--lock-lang"])`` must not raise TypeError.

    Regression: the bool parameter shadowed the module function and made
    ``lock_language(lang_to_apply)`` raise ``'bool' object is not callable``.
    """
    _ensure_offscreen(monkeypatch)
    # Run the real CLI entry with a short auto-quit so the event loop ends.
    mod.main(["--lang", "fr", "--lock-lang"], run_for=100)


def test_lock_language_enabled_flag_is_applied(monkeypatch):
    """``lock_language_enabled=True`` locks the language (module function
    called, not the boolean)."""
    _ensure_offscreen(monkeypatch)
    app = mod.QApplication.instance() or mod.QApplication([])
    win = mod.ZeAnalyserMainWindow(initial_lang="fr", lock_language_enabled=True)
    assert win.language_locked_cli is True
    assert mod._LANGUAGE_LOCKED is True


def test_legacy_lock_language_keyword_still_accepted(monkeypatch):
    """Backward compatibility: historical ``lock_language=`` keyword keeps
    working and maps to the same flag."""
    _ensure_offscreen(monkeypatch)
    app = mod.QApplication.instance() or mod.QApplication([])
    win = mod.ZeAnalyserMainWindow(initial_lang="fr", lock_language=True)
    assert win.language_locked_cli is True
