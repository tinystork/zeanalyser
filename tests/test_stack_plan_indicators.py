import pytest

from analysis_model import StackPlanModel


def _rows():
    return [
        {'order': 1, 'batch_id': 'T1_2025-01-01_L', 'mount': 'M1', 'bortle': '3',
         'telescope': 'T1', 'session_date': '2025-01-01', 'filter': 'L', 'exposure': '30',
         'file_path': '/tmp/night1/a.fits'},
        {'order': 2, 'batch_id': 'T2_2025-01-02_L', 'mount': 'M1', 'telescope': 'T1',
         'session_date': '2025-01-02', 'filter': 'L', 'exposure': '30', 'file_path': '/tmp/night2/b.fits'},
    ]


def test_indicator_prefers_bortle_when_present():
    model = StackPlanModel(_rows())
    r0 = model._rows[0]
    ind = model._compute_indicator_from_row(r0)
    assert ind == 'bortle:3'
    color = model._indicator_color(ind)
    # color is either a hex string (fallback) or a QColor instance in Qt env
    if isinstance(color, str):
        assert color.startswith('#')
    else:
        # QColor-like object should expose color methods (red/name)
        assert hasattr(color, 'red') or hasattr(color, 'name')


def test_indicator_uses_date_or_dir_fallback():
    model = StackPlanModel(_rows())
    r1 = model._rows[1]
    # this row has no bortle => session_date should be returned
    ind = model._compute_indicator_from_row(r1)
    assert ind == 'date:2025-01-02'
    color = model._indicator_color(ind)
    if isinstance(color, str):
        assert color.startswith('#')
    else:
        assert hasattr(color, 'red') or hasattr(color, 'name')
