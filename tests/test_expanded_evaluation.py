import json

from evaluation.expanded import matches


def entry(tool, result, **args):
    return {'tool': tool, 'status': 'ok', 'result': json.dumps(result), 'arguments': args}


def test_group_checker_rejects_wrong_measure_even_if_numbers_match():
    result = {'method': 'mean', 'group_column': 'region', 'metric_column': 'wrong',
              'groups': [{'group': 'East', 'mean': 120}, {'group': 'North', 'mean': 270},
                         {'group': 'West', 'mean': 160 / 3}]}
    assert not matches('group_mean', [entry('compare_groups', result)])
    result['metric_column'] = 'amount'
    assert matches('group_mean', [entry('compare_groups', result)])


def test_schema_checker_requires_both_dimensions_and_successful_call():
    candidate = entry('inspect_schema', {'rows': 9, 'columns': 8})
    assert matches('schema', [candidate])
    candidate['status'] = 'error'
    assert not matches('schema', [candidate])
    assert not matches('schema', [entry('inspect_schema', {'rows': 9, 'columns': 7})])


def test_category_frequencies_allow_equivalent_computed_group_counts():
    result = {'group_column': 'status', 'metric_column': 'status', 'method': 'count',
              'groups': [{'group': 'completed', 'count': 7}, {'group': 'pending', 'count': 2}]}
    assert matches('status_distribution', [entry('compare_groups', result)])
    result['metric_column'] = 'region'
    assert not matches('status_distribution', [entry('compare_groups', result)])


def test_range_evidence_requires_requested_limits_not_just_correct_count():
    result = {'column': 'amount', 'minimum': 0, 'maximum': 250, 'checked_values': 7,
              'violation_count': 3, 'below_minimum': 1, 'above_maximum': 2, 'missing_values': 1}
    assert matches('numeric_range', [entry('check_numeric_range', result)])
    result['maximum'] = 200
    assert not matches('numeric_range', [entry('check_numeric_range', result)])


def test_allowed_category_evidence_must_use_the_requested_case_rule():
    result = {'column':'status','allowed_values':['completed','pending','cancelled'],
              'case_sensitive':True,'unexpected_values':2,'non_null_values':8,'missing_values':0}
    assert matches('allowed_categories', [entry('validate_categories', result)])
    result['case_sensitive'] = False
    assert not matches('allowed_categories', [entry('validate_categories', result)])


def test_chart_evidence_requires_requested_metric_not_just_matching_heights():
    result = {'chart_type':'bar', 'x':'region', 'y':'amount', 'method':'sum',
              'data':[{'x':'East','y':360},{'x':'North','y':540},{'x':'West','y':160}]}
    assert matches('chart_region_sum', [entry('create_chart', result)])
    result['y'] = 'wrong_measure'
    assert not matches('chart_region_sum', [entry('create_chart', result)])
    result['y'] = 'amount'
    result['data'][0]['y'] = 999
    assert not matches('chart_region_sum', [entry('create_chart', result)])
