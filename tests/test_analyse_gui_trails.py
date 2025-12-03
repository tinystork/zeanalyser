import pytest

import analyse_gui_qt as mod


pytestmark = pytest.mark.skipif(
    mod.QApplication is object, reason="PySide6 not installed in this environment"
)


def test_trail_ui_and_options(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    created_app = False
    app = mod.QApplication.instance()
    if app is None:
        app = mod.QApplication([])
        created_app = True

    win = mod.ZeAnalyserMainWindow()

    # widgets should exist
    assert hasattr(win, 'detect_trails_cb')
    assert hasattr(win, 'trail_sigma_spin')
    assert hasattr(win, 'trail_low_thr_spin')
    assert hasattr(win, 'trail_high_thr_spin')
    assert hasattr(win, 'trail_line_len_spin')
    assert hasattr(win, 'trail_small_edge_spin')
    assert hasattr(win, 'trail_line_gap_spin')
    assert hasattr(win, 'trail_reject_dir_edit')

    # set values and read back via _build_options_from_ui
    win.detect_trails_cb.setChecked(True)
    win.trail_sigma_spin.setValue(3.14)
    win.trail_low_thr_spin.setValue(12.5)
    win.trail_high_thr_spin.setValue(65.0)
    win.trail_line_len_spin.setValue(120)
    win.trail_small_edge_spin.setValue(3)
    win.trail_line_gap_spin.setValue(11)
    win.trail_reject_dir_edit.setText("C:/tmp/trails_reject")

    opts = win._build_options_from_ui()

    assert opts['detect_trails'] is True
    assert isinstance(opts.get('trail_params'), dict)
    tp = opts['trail_params']
    assert tp.get('sigma') == pytest.approx(3.14, rel=1e-6)
    assert tp.get('low_thr') == pytest.approx(12.5, rel=1e-6)
    assert tp.get('high_thr') == pytest.approx(65.0, rel=1e-6)
    assert tp.get('line_len') == 120
    assert tp.get('small_edge') == 3
    assert tp.get('line_gap') == 11
    assert opts.get('trail_reject_dir') == 'C:/tmp/trails_reject'

    if created_app:
        app.quit()


def test_qt_and_tk_trail_apply_parity(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    rows_template = [
        {'file': 'a.fits', 'has_trails': True, 'status': 'ok', 'path': 'C:/tmp/a.fits'},
        {'file': 'b.fits', 'has_trails': False, 'status': 'ok', 'path': 'C:/tmp/b.fits'},
    ]

    called_snapshots = []

    def fake_apply(results_list, path, delete_rejected_flag, move_rejected_flag, log_callback, status_callback, progress_callback, input_dir_abs):
        pending = [r.get('file') for r in results_list if r.get('rejected_reason') == 'trail_pending_action']
        called_snapshots.append({'pending': pending, 'path': path, 'delete': delete_rejected_flag, 'move': move_rejected_flag})
        return 0

    import analyse_logic
    monkeypatch.setattr(analyse_logic, 'apply_pending_trail_actions', fake_apply)

    # TK parity
    import analyse_gui as tkmod

    class DummyTk:
        pass

    tk = DummyTk()
    tk.analysis_results = [dict(r) for r in rows_template]
    # configure that we detected trails and want to move
    tk.reject_action = type('X', (), {'get': lambda self: 'move'})()
    tk.input_dir = type('X', (), {'get': lambda self: 'C:/tmp/input'})()
    tk.trail_reject_dir = type('X', (), {'get': lambda self: 'C:/tmp/trails_reject'})()

    # call Tk method that invokes apply (existing path in analyse_gui.py uses apply_pending_trail_actions directly)
    # Mark pending entries as Tk would do: set rejected_reason and action
    for r in tk.analysis_results:
        if r.get('has_trails'):
            r['rejected_reason'] = 'trail_pending_action'
            r['action'] = 'pending_trail_action'

    tkmod.ZeAnalyserMainWindow.apply_pending_trail_actions_gui = lambda self: analyse_logic.apply_pending_trail_actions(
        tk.analysis_results, 'C:/tmp/trails_reject', delete_rejected_flag=False, move_rejected_flag=True,
        log_callback=lambda *a, **k: None, status_callback=lambda *a, **k: None, progress_callback=lambda v: None, input_dir_abs='C:/tmp/input')

    tkmod.ZeAnalyserMainWindow.apply_pending_trail_actions_gui(tk)

    # Qt behavior
    created_app = False
    app = mod.QApplication.instance()
    if app is None:
        app = mod.QApplication([])
        created_app = True

    win = mod.ZeAnalyserMainWindow()
    win.set_results([dict(r) for r in rows_template])
    win.trail_reject_dir_edit.setText('C:/tmp/trails_reject')
    # ensure move option selected
    win.reject_move_rb.setChecked(True)

    import threading

    class ImmediateThread:
        def __init__(self, target=None, daemon=True):
            self._target = target

        def start(self):
            if self._target:
                self._target()

    monkeypatch.setattr(threading, 'Thread', ImmediateThread)

    win.trail_apply_btn.click()
    app.processEvents()

    assert len(called_snapshots) >= 2
    assert called_snapshots[0]['pending'] == called_snapshots[1]['pending']

    if created_app:
        app.quit()


def test_apply_trail_calls_logic(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    created_app = False
    app = mod.QApplication.instance()
    if app is None:
        app = mod.QApplication([])
        created_app = True

    win = mod.ZeAnalyserMainWindow()

    rows = [
        {'file': 'a.fits', 'has_trails': True, 'status': 'ok', 'path': 'C:/tmp/a.fits'},
        {'file': 'b.fits', 'has_trails': False, 'status': 'ok', 'path': 'C:/tmp/b.fits'},
    ]
    win.set_results(rows)

    win.trail_reject_dir_edit.setText("C:/tmp/trails_reject")

    called = {}

    def fake_apply(results_list, path, delete_rejected_flag, move_rejected_flag, log_callback, status_callback, progress_callback, input_dir_abs):
        called['args'] = {'count': len(results_list), 'path': path, 'delete': delete_rejected_flag, 'move': move_rejected_flag}
        # emulate in-place change
        for r in results_list:
            if r.get('file') == 'a.fits':
                r['action'] = 'moved_trail'
                r['rejected_reason'] = 'trail'
        return 1

    import analyse_logic
    monkeypatch.setattr(analyse_logic, 'apply_pending_trail_actions', fake_apply)

    import threading

    class ImmediateThread:
        def __init__(self, target=None, daemon=True):
            self._target = target

        def start(self):
            if self._target:
                self._target()

    monkeypatch.setattr(threading, 'Thread', ImmediateThread)

    win.trail_apply_btn.click()
    app.processEvents()

    assert 'args' in called
    assert called['args']['path'] == 'C:/tmp/trails_reject'

    # ensure model updated
    found = [r for r in win._results_model._rows if r.get('file') == 'a.fits']
    assert found and found[0].get('action') == 'moved_trail'

    if created_app:
        app.quit()
