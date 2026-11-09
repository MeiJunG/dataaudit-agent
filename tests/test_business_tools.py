import json

import numpy as np
import pandas as pd
import pytest

from src.tools import build_tools


def run(frame, name, **args):
    return json.loads(next(tool for tool in build_tools(frame) if tool.name == name).invoke(args))


def test_numeric_limits_are_inclusive_and_bad_values_are_separate():
    frame = pd.DataFrame({'amount': ['0', '100', '-1', '101', None, 'bad', 'inf']})
    result = run(frame, 'check_numeric_range', column='amount', minimum=0, maximum=100)
    assert result['checked_values'] == 4
    assert result['below_minimum'] == result['above_maximum'] == 1
    assert result['violation_count'] == 2
    assert result['missing_values'] == 1
    assert result['invalid_numeric_values'] == 2
    assert result['violation_ratio_of_checked'] == .5


@pytest.mark.parametrize('kwargs', [{}, {'minimum': 2, 'maximum': 1}, {'maximum': float('inf')}])
def test_invalid_bounds_are_returned_as_observations(kwargs):
    assert 'error' in run(pd.DataFrame({'x': [1]}), 'check_numeric_range', column='x', **kwargs)


def test_reconciliation_uses_absolute_tolerance_and_keeps_missing_pairs_separate():
    frame = pd.DataFrame({'a': [100, 200, None, 10, 'bad', np.inf],
                          'b': [100.004, 199, None, None, 5, np.inf]})
    result = run(frame, 'compare_columns', left_column='a', right_column='b', mode='numeric', tolerance=.01)
    assert result['compared_rows'] == 2
    assert result['matched_rows'] == 1
    assert result['mismatched_rows'] == 1
    assert result['both_missing_rows'] == 1
    assert result['one_side_missing_rows'] == 1
    assert result['invalid_numeric_pair_rows'] == 2


def test_exact_comparison_does_not_normalize_strings_or_expose_values():
    frame = pd.DataFrame({'account': ['secret-A', 'secret-B'], 'account_copy': ['secret-A', 'secret-b']})
    result = run(frame, 'compare_columns', left_column='account', right_column='account_copy')
    assert result['matched_rows'] == result['mismatched_rows'] == 1
    assert 'secret' not in json.dumps(result)
    assert 'error' in run(frame, 'compare_columns', left_column='account', right_column='account_copy', mode='exact', tolerance=1)


def test_numeric_tolerance_can_be_used_without_explicit_mode():
    result = run(pd.DataFrame({'a': ['100', 'bad'], 'b': ['100.004', '100']}),
                 'compare_columns', left_column='a', right_column='b', tolerance=.01)
    assert result['mode'] == 'numeric'
    assert result['matched_rows'] == 1 and result['invalid_numeric_pair_rows'] == 1


def test_weekly_buckets_start_monday_and_keep_empty_numeric_bucket_null():
    frame = pd.DataFrame({'date': ['2026-10-04', '2026-10-05', 'bad', None],
                          'amount': [10, None, 500, 700]})
    result = run(frame, 'summarize_time_series', date_column='date', metric_column='amount', frequency='week')
    assert result['periods'] == [
        {'period_start': '2026-09-28', 'rows': 1, 'metric_non_null': 1, 'value': 10},
        {'period_start': '2026-10-05', 'rows': 1, 'metric_non_null': 0, 'value': None}]
    assert result['invalid_date_rows'] == result['missing_date_rows'] == 1


def test_time_counts_accept_text_and_dates_are_normalized_to_utc():
    frame = pd.DataFrame({'date': ['2026-10-01T00:30:00+02:00', '2026-10-01T01:00:00Z'],
                          'status': ['done', 'pending']})
    result = run(frame, 'summarize_time_series', date_column='date', metric_column='status', frequency='day', method='count')
    assert [row['period_start'] for row in result['periods']] == ['2026-09-30', '2026-10-01']
    assert [row['value'] for row in result['periods']] == [1, 1]


def test_time_aggregation_is_bounded_and_rejects_ambiguous_dates():
    many = pd.DataFrame({'date': pd.date_range('2026-01-01', periods=31).astype(str), 'amount': [1] * 31})
    assert 'error' in run(many, 'summarize_time_series', date_column='date', metric_column='amount', frequency='day')
    numeric = pd.DataFrame({'date': [1, 2], 'amount': [1, 2]})
    assert 'error' in run(numeric, 'summarize_time_series', date_column='date', metric_column='amount')
    all_bad = pd.DataFrame({'date': ['bad'], 'amount': [1]})
    assert 'error' in run(all_bad, 'summarize_time_series', date_column='date', metric_column='amount')
