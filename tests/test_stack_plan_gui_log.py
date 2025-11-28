import zone


def test_translations_have_stack_plan_keys():
    fr = zone.translations.get('fr', {})
    assert 'stack_plan_summary' in fr
    assert 'stack_plan_summary_no_total' in fr
    assert 'stack_plan_reminder' in fr


def test_stack_plan_summary_formats():
    fr = zone.translations.get('fr', {})
    tpl = fr['stack_plan_summary']
    formatted = tpl.format(selected=24, total=30, pct=80.0, filename='stack_plan.csv')
    assert 'Plan d'empilement créé' in formatted
    assert '24' in formatted
    assert '30' in formatted
    assert '80.0' in formatted


def test_stack_plan_summary_no_total_formats():
    fr = zone.translations.get('fr', {})
    tpl = fr['stack_plan_summary_no_total']
    formatted = tpl.format(selected=24, filename='stack_plan.csv')
    assert 'Plan d'empilement créé' in formatted
    assert '24' in formatted
    assert 'stack_plan.csv' in formatted
