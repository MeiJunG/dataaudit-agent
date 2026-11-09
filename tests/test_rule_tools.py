import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.agent import _tool_entry
from src.business_results import render_business_answer
from src.data_manager import load_csv
from src.tools import build_tools


def call(frame, name, **args):
    value = next(tool for tool in build_tools(frame) if tool.name == name).invoke(args)
    return json.loads(value)


def fixture():
    return load_csv(Path(__file__).parents[1] / 'examples' / 'rule_checks.csv')


def test_allowed_categories_are_explicit_and_case_rules_are_respected():
    frame = fixture()
    result = call(frame, 'validate_categories', column='status', allowed_values=['completed','pending','cancelled'])
    assert result['unexpected_values'] == 2 and result['missing_values'] == 0
    insensitive = call(frame, 'validate_categories', column='status', allowed_values=['completed','pending','cancelled'], case_sensitive=False)
    assert insensitive['unexpected_values'] == 1
    assert 'error' in call(frame, 'validate_categories', column='status', allowed_values=[])


def test_missing_and_sensitive_unexpected_categories_are_not_exposed():
    result = call(pd.DataFrame({'account': ['valid','private',None]}), 'validate_categories', column='account', allowed_values=['valid'])
    assert result['unexpected_values'] == result['missing_values'] == 1
    assert result['unexpected_categories'] == []


def test_primary_key_counts_all_duplicate_participants_and_nulls():
    result = call(fixture(), 'check_key_uniqueness', columns=['order_id'])
    assert result['missing_key_rows'] == 1
    assert result['duplicate_key_rows'] == 2 and result['redundant_rows'] == 1
    assert result['distinct_complete_keys'] == 6 and result['usable_key'] is False
    composite = call(fixture(), 'check_key_uniqueness', columns=['order_id','region'])
    assert composite['duplicate_key_rows'] == 0 and composite['unique_among_complete'] is True
    assert composite['usable_key'] is False


def test_empty_keys_and_missing_fields_are_errors_or_explicitly_not_usable():
    frame = pd.DataFrame({'id': []})
    assert not call(frame, 'check_key_uniqueness', columns=['id'])['usable_key']
    assert 'error' in call(frame, 'check_key_uniqueness', columns=[])
    assert 'error' in call(frame, 'check_key_uniqueness', columns=['absent'])


def test_filtered_sum_separates_matched_rows_from_non_null_metrics():
    result = call(fixture(), 'filter_and_aggregate', filter_column='status', operator='eq', value='completed', metric_column='amount', method='sum')
    assert result['matched_rows'] == 4 and result['aggregate_value'] == 330
    assert result['valid_metric_values'] == 3 and result['missing_metric_values'] == 1


def test_numeric_filter_skips_invalid_infinite_and_missing_values():
    frame = pd.DataFrame({'amount': ['100','200','bad',None,np.inf]})
    result = call(frame, 'filter_and_aggregate', filter_column='amount', operator='gt', value=100)
    assert result['matched_rows'] == result['aggregate_value'] == 1
    assert result['missing_filter_values'] == 1 and result['invalid_numeric_filter_values'] == 2


def test_literal_contains_cannot_execute_code_or_regex():
    frame = pd.DataFrame({'text': ['a.b','axb',None,"__import__('os')"]})
    assert call(frame,'filter_and_aggregate',filter_column='text',operator='contains',value='a.b')['matched_rows'] == 1
    assert call(frame,'filter_and_aggregate',filter_column='text',operator='contains',value="__import__('os')")['matched_rows'] == 1
    assert call(frame,'filter_and_aggregate',filter_column='text',operator='ne',value='a.b')['matched_rows'] == 2


def test_empty_numeric_aggregate_is_null_and_boolean_filter_is_literal():
    frame = pd.DataFrame({'flag': [True,False], 'amount': [10,20]})
    result = call(frame,'filter_and_aggregate',filter_column='flag',operator='eq',value='true',metric_column='amount',method='sum')
    assert result['aggregate_value'] == 10
    empty = call(frame,'filter_and_aggregate',filter_column='amount',operator='gt',value=100,metric_column='amount',method='sum')
    assert empty['aggregate_value'] is None
    assert 'error' in call(frame,'filter_and_aggregate',filter_column='amount',operator='eval',value='100')


@pytest.mark.parametrize('name,args,phrases', [
    ('validate_categories', {'column':'status','allowed_values':['completed','pending','cancelled']}, ['列表外 2 个']),
    ('check_key_uniqueness', {'columns':['order_id']}, ['重复键涉及 2 行','键有缺失 1 行']),
    ('filter_and_aggregate', {'filter_column':'status','operator':'eq','value':'completed','metric_column':'amount','method':'sum'}, ['符合条件 4 行','330','指标缺失 1 个']),
])
def test_new_rule_answers_are_rendered_from_observations(name,args,phrases):
    output = next(tool for tool in build_tools(fixture()) if tool.name == name).invoke(args)
    trace = [_tool_entry(name,args,output,'ok',1,1)]
    answer = render_business_answer(trace,'检查这份数据')
    assert all(phrase in answer for phrase in phrases)


def test_primary_key_with_missing_and_duplicate_helpers_stays_evidence_rendered():
    frame = fixture()
    tools = {tool.name:tool for tool in build_tools(frame)}
    calls = [('check_key_uniqueness',{'columns':['order_id']}), ('check_missing_values',{}), ('check_duplicates',{})]
    trace = [_tool_entry(name,args,tools[name].invoke(args),'ok',1,1) for name,args in calls]
    answer = render_business_answer(trace,'检查主键、空值和重复记录')
    assert '重复键涉及 2 行' in answer
    assert '键有缺失 1 行' in answer
    assert '按 整行 查重，多余 0 行' in answer
    assert '`amount`：1 个' in answer
