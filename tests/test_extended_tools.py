import json

import pandas as pd
import pytest

from src.tools import build_tools


def tools(frame):
    return {tool.name: tool for tool in build_tools(frame)}


def test_count_includes_text_values_and_missing_group():
    frame = pd.DataFrame({'region': ['A', 'A', 'B', None], 'status': ['open', None, 'done', 'open']})
    result = json.loads(tools(frame)['compare_groups'].invoke(
        {'group_column': 'region', 'metric_column': 'status', 'method': 'count'}))
    counts = {row['group']: row['count'] for row in result['groups']}
    assert counts == {'A': 1, 'B': 1, '[missing]': 1}


def test_groups_average_excludes_invalid_numeric_values():
    frame = pd.DataFrame({'region': ['A', 'A', 'B'], 'amount': ['10', 'invalid', '30']})
    result = json.loads(tools(frame)['compare_groups'].invoke(
        {'group_column': 'region', 'metric_column': 'amount'}))
    assert result['groups'][0]['group'] == 'B'
    assert result['groups'][1]['mean'] == 10
    assert result['groups'][1]['metric_non_null'] == 1


def test_mixed_dates_invalid_dates_and_numeric_epoch_ambiguity():
    frame = pd.DataFrame({'date': ['2026-10-01', '2026-10-02T12:00:00Z', 'bad', None], 'number': [1, 2, 3, 4]})
    registered = tools(frame)
    result = json.loads(registered['inspect_date_column'].invoke({'column': 'date'}))
    assert result['parsed_dates'] == 2
    assert result['invalid_non_null_values'] == 1
    assert result['latest'].startswith('2026-10-02')
    assert 'error' in json.loads(registered['inspect_date_column'].invoke({'column': 'number'}))


def test_correlations_deduplicate_columns_and_skip_constants():
    frame = pd.DataFrame({'x': [1, 2, 3], 'y': [2, 4, 6], 'constant': [5, 5, 5]})
    result = json.loads(tools(frame)['check_correlations'].invoke({'columns': ['x', 'x', 'y', 'constant']}))
    assert len(result['pairs']) == 1
    assert result['pairs'][0]['pearson_r'] == pytest.approx(1)


def test_report_totals_cover_all_fields_when_detail_is_limited():
    frame = pd.DataFrame({f'field_{i}': [1, None] for i in range(35)})
    report = tools(frame)['generate_quality_report'].invoke({})
    assert 'Missing cells: 35 / 70' in report
    assert 'Showing 30 of 35 fields' in report
    assert 'aggregate statistics only' in report


def test_mixed_numeric_text_is_flagged_without_exposing_sensitive_samples():
    frame = pd.DataFrame({'age': ['20', '30', 'unknown'], 'account': ['1', '2', 'private']})
    result = json.loads(tools(frame)['validate_data_types'].invoke({}))
    issues = {row['column']: row for row in result['issues']}
    assert issues['age']['sample_invalid_values'] == ['unknown']
    assert issues['account']['sample_invalid_values'] == []


def test_grouping_text_without_method_infers_counts():
    frame = pd.DataFrame({'status': ['completed','completed','pending'], 'amount': [10,20,90]})
    result = json.loads(tools(frame)['compare_groups'].invoke({'group_column':'status','metric_column':'status'}))
    assert result['method'] == 'count'
    assert {row['group']:row['count'] for row in result['groups']} == {'completed':2,'pending':1}
    error = json.loads(tools(frame)['compare_groups'].invoke({'group_column':'status','metric_column':'count'}))
    assert 'method=count' in error['hint']
