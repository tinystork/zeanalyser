import os
import tempfile
import pytest

from stack_plan import generate_stacking_plan, write_stacking_plan_csv
from analysis_model import StackPlanModel


def _sample_results():
    return [
        {
            'mount': 'M1', 'bortle': '3', 'telescope': 'T1',
            'date_obs': '2025-01-01T00:00:00', 'filter': 'L', 'exposure': 30,
            'path': '/tmp/a.fits'
        },
        {
            'mount': 'M1', 'bortle': '3', 'telescope': 'T1',
            'date_obs': '2025-01-01T00:00:00', 'filter': 'L', 'exposure': 30,
            'path': '/tmp/b.fits'
        }
    ]


def test_stackplan_model_reads_csv(tmp_path):
    rows = generate_stacking_plan(_sample_results())
    csv_file = tmp_path / "plan.csv"
    write_stacking_plan_csv(str(csv_file), rows)

    model = StackPlanModel(str(csv_file))
    assert model.rowCount() == len(rows)
    # header order should match CSV column headers
    assert model.columnCount() > 0
    # round-trip: first row file_path should equal generated
    assert model._rows[0]['file_path'] == rows[0]['file_path']
