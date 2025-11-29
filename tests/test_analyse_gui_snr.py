import pytest

import analyse_gui_qt as mod


pytestmark = pytest.mark.skipif(
    mod.QApplication is object, reason="PySide6 not installed in this environment"
)


def test_snr_ui_and_options(monkeypatch):
    # Force headless Qt (CI)
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    created_app = False
    app = mod.QApplication.instance()
    if app is None:
        app = mod.QApplication([])
        created_app = True

    win = mod.ZeAnalyserMainWindow()

    # widgets should exist on the window
    assert hasattr(win, 'analyze_snr_cb')
    assert hasattr(win, 'snr_mode_percent_rb')
    assert hasattr(win, 'snr_mode_threshold_rb')
    assert hasattr(win, 'snr_mode_none_rb')
    assert hasattr(win, 'snr_value_spin')
    assert hasattr(win, 'snr_reject_dir_edit')
    assert hasattr(win, 'snr_apply_btn')
    assert hasattr(win, 'snr_apply_immediately_cb')

    # set a threshold mode and values
    win.analyze_snr_cb.setChecked(True)
    win.snr_mode_threshold_rb.setChecked(True)
    win.snr_value_spin.setValue(3.5)
    win.snr_reject_dir_edit.setText("C:/tmp/reject_snr")
    win.snr_apply_immediately_cb.setChecked(True)

    opts = win._build_options_from_ui()

    assert opts['analyze_snr'] is True
    assert opts['snr_mode'] == 'threshold'
    assert pytest.approx(opts['snr_value'], rel=1e-6) == 3.5
    assert opts['snr_reject_dir'] == 'C:/tmp/reject_snr'
    assert opts['apply_snr_action_immediately'] is True

    # pressing the apply button should populate _snr_last_applied for tests
    win.snr_apply_btn.click()
    assert hasattr(win, '_snr_last_applied')
    assert isinstance(win._snr_last_applied, dict)
    assert win._snr_last_applied.get('snr_mode') == 'threshold'

    if created_app:
        app.quit()


def test_qt_and_tk_apply_parity(monkeypatch):
    # Ensure both frontends pass the expected set of rows to the logic
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    # sample rows
    rows_template = [
        {'file': 'a.fits', 'snr': 2.0, 'status': 'ok', 'path': 'C:/tmp/a.fits'},
        {'file': 'b.fits', 'snr': 10.0, 'status': 'ok', 'path': 'C:/tmp/b.fits'},
    ]

    called_snapshots = []

    def fake_apply(results_list, path, delete_rejected_flag, move_rejected_flag, log_callback, status_callback, progress_callback, input_dir_abs):
        # record which files were flagged as pending when apply was called
        pending = [r.get('file') for r in results_list if r.get('rejected_reason') == 'low_snr_pending_action']
        called_snapshots.append({'pending': pending, 'path': path, 'delete': delete_rejected_flag, 'move': move_rejected_flag})
        return 0

    import analyse_logic
    monkeypatch.setattr(analyse_logic, 'apply_pending_snr_actions', fake_apply)

    # 1) TK-like behavior (call method directly with a dummy self)
    import analyse_gui as tkmod

    class DummyTk:
        pass

    tk = DummyTk()
    tk.analysis_results = [dict(r) for r in rows_template]
    # configure range so we reject values < 5.0
    tk.current_snr_min = 5.0
    tk.current_snr_max = 1e9
    tk.snr_reject_dir = type('X', (), {'get': lambda self: 'C:/tmp/reject'})()
    tk.reject_action = type('X', (), {'get': lambda self: 'move'})()
    tk.input_dir = type('X', (), {'get': lambda self: 'C:/tmp/input'})()
    tk.apply_snr_button = None
    tk.snr_range_slider = type('X', (), {'disconnect_events': lambda self: None})()
    tk._refresh_treeview = lambda: None

    # call Tk method; it should mark low-snr files as pending and call fake_apply
    tkmod.ZeAnalyserMainWindow.apply_pending_snr_actions_gui(tk)

    # 2) Qt behavior
    created_app = False
    app = mod.QApplication.instance()
    if app is None:
        app = mod.QApplication([])
        created_app = True

    win = mod.ZeAnalyserMainWindow()
    # put the same rows into results model
    win.set_results([dict(r) for r in rows_template])
    win.snr_mode_threshold_rb.setChecked(True)
    win.snr_value_spin.setValue(5.0)
    win.snr_reject_dir_edit.setText('C:/tmp/reject')

    # run apply synchronously by making threads immediate
    import threading

    class ImmediateThread:
        def __init__(self, target=None, daemon=True):
            self._target = target

        def start(self):
            if self._target:
                self._target()

    monkeypatch.setattr(threading, 'Thread', ImmediateThread)

    win.snr_apply_btn.click()
    app.processEvents()

    # ensure fake_apply saw exactly the same pending file(s)
    assert len(called_snapshots) >= 2
    assert called_snapshots[0]['pending'] == called_snapshots[1]['pending']

    if created_app:
        app.quit()


def test_apply_snr_calls_logic(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    created_app = False
    app = mod.QApplication.instance()
    if app is None:
        app = mod.QApplication([])
        created_app = True

    win = mod.ZeAnalyserMainWindow()

    # create small results dataset
    rows = [
        {'file': 'a.fits', 'snr': 2.0, 'status': 'ok', 'path': 'C:/tmp/a.fits'},
        {'file': 'b.fits', 'snr': 10.0, 'status': 'ok', 'path': 'C:/tmp/b.fits'},
        {'file': 'c.fits', 'snr': None, 'status': 'ok', 'path': 'C:/tmp/c.fits'},
    ]
    win.set_results(rows)

    # set threshold so only a.fits is flagged (snr < 5.0)
    win.snr_mode_threshold_rb.setChecked(True)
    win.snr_value_spin.setValue(5.0)
    win.snr_reject_dir_edit.setText("C:/tmp/reject")

    called = {}

    def fake_apply(results_list, path, delete_rejected_flag, move_rejected_flag, log_callback, status_callback, progress_callback, input_dir_abs):
        called['args'] = {
            'count': len(results_list),
            'path': path,
            'delete': delete_rejected_flag,
            'move': move_rejected_flag,
        }
        # emulate modifying list in-place (mark first file as moved)
        for r in results_list:
            if r.get('file') == 'a.fits':
                r['action'] = 'moved_snr'
                r['rejected_reason'] = 'low_snr'
        return 1

    import analyse_logic
    monkeypatch.setattr(analyse_logic, 'apply_pending_snr_actions', fake_apply)

    # Make background thread run synchronously for the test
    import threading

    class ImmediateThread:
        def __init__(self, target=None, daemon=True):
            self._target = target

        def start(self):
            if self._target:
                self._target()

    monkeypatch.setattr(threading, 'Thread', ImmediateThread)

    # click apply - this should call our fake_apply synchronously
    win.snr_apply_btn.click()

    # process events so QTimer callbacks are delivered
    app.processEvents()

    assert 'args' in called
    assert called['args']['path'] == 'C:/tmp/reject'

    # ensure model was updated in-place
    # find the row for a.fits in the model
    found = [r for r in win._results_model._rows if r.get('file') == 'a.fits']
    assert found and found[0].get('action') == 'moved_snr'

    if created_app:
        app.quit()
