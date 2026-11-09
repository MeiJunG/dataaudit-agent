"""Integration checks for the Pandas adapters; run in the server/CI Python environment."""
import json
from pathlib import Path

import pandas as pd

from src.data_manager import load_csv
from src.tools import build_tools


def registered():
    frame = load_csv(Path(__file__).parents[1] / 'examples' / 'consistency_checks.csv')
    return {tool.name: tool for tool in build_tools(frame)}


def test_text_adapter_reports_the_fixture_variants():
    result = json.loads(registered()['check_text_quality'].invoke({'columns':['status']}))
    field = result['fields'][0]
    assert field['outer_whitespace_values'] == 1
    assert field['normalized_collision_groups'] == 1
    assert field['collision_rows'] == 5


def test_conditional_adapter_preserves_nulls_and_counts_affected_rows():
    result = json.loads(registered()['check_required_if'].invoke({
        'condition_column':'status','equals':'completed','required_columns':['amount','recorded_amount']}))
    assert result['matched_rows'] == 3 and result['affected_rows'] == 2
    assert result['missing_by_column'] == {'amount':1,'recorded_amount':1}


def test_date_adapter_separates_invalid_missing_and_equal_pairs():
    result = json.loads(registered()['check_date_order'].invoke({'start_column':'order_date','end_column':'ship_date'}))
    assert result['compared_rows'] == 4
    assert result['violation_rows'] == 1
    assert result['missing_date_pair_rows'] == result['invalid_date_pair_rows'] == 1


def test_invalid_adapter_arguments_return_errors_without_mutating_the_table():
    tools = registered()
    assert 'error' in json.loads(tools['check_text_quality'].invoke({'columns':[]}))
    assert 'error' in json.loads(tools['check_date_order'].invoke({'start_column':'missing','end_column':'ship_date'}))
    assert 'error' in json.loads(tools['check_required_if'].invoke({'condition_column':'status','equals':'completed','required_columns':[]}))
