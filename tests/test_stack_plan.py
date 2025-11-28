import os
from stack_plan import generate_stacking_plan
from stack_plan import write_stacking_plan_csv


def test_generate_stacking_plan_basic(tmp_path):
    results = [
        {
            'status': 'ok',
            'mount': 'EQ',
            'bortle': '3',
            'telescope': 'C11',
            'date_obs': '2024-07-13T22:00:00',
            'filter': 'R',
            'exposure': 180,
            'path': '/astro/C11/2024-07-13/img1.fit',
            'ra': '12:34:56.7',
            'dec': '+12:34:56.7',
        },
        {
            'status': 'ok',
            'mount': 'EQ',
            'bortle': '3',
            'telescope': 'C11',
            'date_obs': '2024-07-13T22:10:00',
            'filter': 'R',
            'exposure': 180,
            'path': '/astro/C11/2024-07-13/img2.fit',
        },
        {
            'status': 'ok',
            'mount': 'ALTZ',
            'bortle': '5',
            'telescope': 'Seestar',
            'date_obs': '2024-07-12T20:00:00',
            'filter': 'N/A',
            'exposure': 10,
            'path': '/astro/Seestar/2024-07-12/img99.fit',
        },
    ]
    plan = generate_stacking_plan(
        results,
        include_exposure_in_batch=False,
        criteria={},
        sort_spec=[('telescope', False), ('session_date', False)],
    )
    assert len(plan) == 3
    assert plan[0]['batch_id'] == 'C11_2024-07-13_R'
    assert plan[2]['batch_id'] == 'Seestar_2024-07-12_N/A'
    # RA/DEC must be present in the generated rows (filled or empty string)
    assert 'ra' in plan[0] and 'dec' in plan[0]
    assert plan[0]['ra'] == '12:34:56.7'
    assert plan[0]['dec'] == '+12:34:56.7'
    assert plan[1].get('ra', '') == '' and plan[1].get('dec', '') == ''


def test_write_stacking_plan_csv_includes_ra_dec(tmp_path):
    rows = [
        {
            'order': 1,
            'batch_id': 'B1',
            'mount': 'EQ',
            'bortle': '3',
            'telescope': 'C11',
            'session_date': '2024-07-13',
            'filter': 'R',
            'exposure': '180',
            'file_path': '/astro/C11/2024-07-13/img1.fit',
            'ra': '12:34:56.7',
            'dec': '+12:34:56.7',
        }
    ]

    csv_path = tmp_path / "plan.csv"
    write_stacking_plan_csv(str(csv_path), rows)

    content = csv_path.read_text(encoding='utf-8')
    # header must include ra and dec, and the row must contain the values
    assert 'ra' in content.splitlines()[0]
    assert 'dec' in content.splitlines()[0]
    assert '12:34:56.7' in content
    assert '+12:34:56.7' in content

