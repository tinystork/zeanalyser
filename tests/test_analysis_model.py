import pytest

import analysis_schema
import analysis_model

if analysis_model.Qt is not None:
    from PySide6.QtCore import Qt


pytestmark = pytest.mark.skipif(
    analysis_model.QAbstractTableModel is object, reason="Qt not available"
)


def sample_rows():
    return [
        {
            'file': 'img1.fit',
            'path': '/data/img1.fit',
            'status': 'ok',
            'snr': 12.3,
            'ra': '12:34:56.7',
            'dec': '+12:34:56.7',
        },
        {
            'file': 'img2.fit',
            'path': '/data/img2.fit',
            'status': 'ok',
            'snr': 5.0,
            'ra': None,
            'dec': None,
        },
    ]


def test_model_shape_and_headers():
    rows = sample_rows()
    model = analysis_model.AnalysisResultsModel(rows)

    assert model.rowCount() == 2
    keys = analysis_schema.get_result_keys()
    assert model.columnCount() == len(keys)

    # check header names for first few columns
    header0 = model.headerData(0, Qt.Horizontal)
    assert header0 == keys[0]

    header1 = model.headerData(1, Qt.Horizontal)
    assert header1 == keys[1]


def test_model_data_display():
    rows = sample_rows()
    model = analysis_model.AnalysisResultsModel(rows)

    # first row, file column
    idx = model.index(0, analysis_schema.get_result_keys().index('file'))
    assert model.data(idx) == 'img1.fit'

    # first row, snr
    idx2 = model.index(0, analysis_schema.get_result_keys().index('snr'))
    assert model.data(idx2) == '12.3'

    # second row, ra should display empty string when None
    idx3 = model.index(1, analysis_schema.get_result_keys().index('ra'))
    assert model.data(idx3) == ''
