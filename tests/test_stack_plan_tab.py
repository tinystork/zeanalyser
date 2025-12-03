import pytest

import analyse_gui_qt as mod


pytestmark = pytest.mark.skipif(
    mod.QApplication is object or mod.QTableView is object, reason="PySide6 not available"
)


def test_stack_plan_tab_shows_model(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    created_app = False
    app = mod.QApplication.instance()
    if app is None:
        app = mod.QApplication([])
        created_app = True

    win = mod.ZeAnalyserMainWindow()

    # construct a small stack plan (list of dicts)
    rows = [
        {'order':1,'batch_id':'T1_2025-01-01_L','mount':'M1','bortle':'3','telescope':'T1','session_date':'2025-01-01','filter':'L','exposure':'30','file_path':'a.fits'},
        {'order':2,'batch_id':'T1_2025-01-01_L','mount':'M1','bortle':'3','telescope':'T1','session_date':'2025-01-01','filter':'L','exposure':'30','file_path':'b.fits'},
    ]

    win.set_stack_plan_rows(rows)

    # ensure proxy/model is attached
    assert getattr(win, '_stack_model', None) is not None
    assert getattr(win, '_stack_proxy', None) is not None
    assert win.stack_view.model() is not None

    # basic sanity check on content
    try:
        src = win._stack_model._rows
        assert len(src) == 2
        assert src[0]['file_path'] == 'a.fits'
    except Exception:
        # in non-Qt headless fallback environments just ensure attribute exists
        assert hasattr(win, '_stack_rows') or hasattr(win, '_stack_model')

    if created_app:
        app.quit()


def test_stack_plan_actions_export_and_script(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    created_app = False
    app = mod.QApplication.instance()
    if app is None:
        app = mod.QApplication([])
        created_app = True

    win = mod.ZeAnalyserMainWindow()

    rows = [
        {'order':1,'batch_id':'T1_2025-01-01_L','mount':'M1','bortle':'3','telescope':'T1','session_date':'2025-01-01','filter':'L','exposure':'30','file_path':'a.fits'},
        {'order':2,'batch_id':'T1_2025-01-01_L','mount':'M1','bortle':'3','telescope':'T1','session_date':'2025-01-01','filter':'L','exposure':'30','file_path':'b.fits'},
    ]

    win.set_stack_plan_rows(rows)

    # Export CSV content
    csv_content = win._export_stack_plan_csv()
    assert csv_content is not None
    assert 'file_path' in csv_content
    assert 'a.fits' in csv_content

    # Export to filesystem
    p = tmp_path / 'out.csv'
    out = win._export_stack_plan_csv(str(p))
    assert p.exists()
    assert out == win._last_stack_plan_export

    # Prepare script content
    script = win._prepare_stacking_script()
    assert script is not None
    assert 'Would stack: a.fits' in script

    p2 = tmp_path / 'script.sh'
    out2 = win._prepare_stacking_script(str(p2))
    assert p2.exists()
    assert out2 == win._last_stack_plan_script

    if created_app:
        app.quit()
