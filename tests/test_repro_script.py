import json

import pandas as pd
import pytest

from src.data_manager import load_table
from src.repro_script import build_script, save_script
from src.table_tools import build_table_tools


@pytest.fixture
def table(tmp_path):
    path = tmp_path / 'orders.csv'
    pd.DataFrame({'region': ['东', '西', '东', '西', '北', '东'], 'amount': [10, 20, 30, 40, None, 60],
                  'qty': [1, 2, 3, 0, 5, 6], 'note': list('abcdef')}).to_csv(path, index=False)
    return path


def entries(path, calls):
    frame = load_table(path)
    tools = {t.name: t for t in build_table_tools(frame)}
    log = []
    for step, (name, args) in enumerate(calls, 1):
        result = json.loads(tools[name].invoke(args))
        log.append({'step': step, 'tool': name, 'arguments': args, 'status': 'ok', 'result': json.dumps(result), 'structured_result': result})
    return log


def same(series, expected):
    # a group with no valid values is None in the tool result and NaN in a pandas Series
    got = series.to_dict()
    assert got.keys() == expected.keys()
    for k, v in expected.items():
        assert (pd.isna(got[k]) if v is None else got[k] == pytest.approx(v)), k


def run(source, path):
    namespace = {}
    exec(compile(source.replace("SOURCE = 'orders.csv'", f"SOURCE = {str(path)!r}"), 'repro', 'exec'), namespace)
    return dict(namespace['RESULTS'])


def test_script_matches_tool_results(table):
    log = entries(table, [
        ('aggregate_rows', {'metric': 'sum', 'value_column': 'amount', 'group_by': ['region']}),
        ('aggregate_rows', {'metric': 'mean', 'value_column': 'amount', 'conditions': [{'column': 'qty', 'operator': 'gt', 'value': 1}]}),
        ('aggregate_rows', {'metric': 'count', 'group_by': ['region']}),
        ('calculate_row_metric', {'columns': ['amount', 'qty'], 'operation': 'ratio'}),
        ('calculate_row_metric', {'columns': ['amount', 'qty'], 'operation': 'weighted_sum', 'weights': [1, 2], 'group_by': ['region'], 'aggregation': 'sum'}),
        ('query_rows', {'columns': ['region', 'amount'], 'conditions': [{'column': 'region', 'operator': 'eq', 'value': '东'}], 'sort_by': 'amount', 'ascending': False}),
    ])
    source = build_script(log, 'orders.csv')
    results = run(source, table)
    grouped = {g['keys']['region']: g['value'] for g in log[0]['structured_result']['groups']}
    same(results['step 1 aggregate_rows'], grouped)
    assert results['step 2 aggregate_rows'] == pytest.approx(log[1]['structured_result']['summary']['value'])
    same(results['step 3 aggregate_rows'], {g['keys']['region']: g['value'] for g in log[2]['structured_result']['groups']})
    summary = log[3]['structured_result']['summary']
    ratio = results['step 4 calculate_row_metric (summary)']
    assert ratio['sum'] == pytest.approx(summary['sum']) and ratio['max'] == pytest.approx(summary['max'])
    by_group = {g['keys']['region']: g['value'] for g in log[4]['structured_result']['groups']}
    same(results['step 5 calculate_row_metric (by group)'], by_group)
    rows = log[5]['structured_result']['rows']
    assert list(results['step 6 query_rows']['amount']) == [r['values']['amount'] for r in rows]


def test_script_is_safe_and_skips_other_steps(table):
    evil = "x'); import os; os.system('echo hi'); ('"
    log = entries(table, [('aggregate_rows', {'metric': 'count'})])
    log[0]['structured_result']['origin']['sheet'] = evil
    log.append({'step': 2, 'tool': 'inspect_schema', 'arguments': {}, 'status': 'ok', 'result': '', 'structured_result': {'kind': 'x'}})
    source = build_script(log, evil + '.csv')
    compile(source, 'repro', 'exec')  # still valid Python
    assert repr(evil) in source and 'step 2: inspect_schema' in source
    assert build_script([log[1]]) is None and build_script([]) is None


def test_save_script_is_content_addressed(table, tmp_path):
    log = entries(table, [('aggregate_rows', {'metric': 'count'})])
    a = save_script(log, tmp_path / 'out', 'orders.csv')
    assert a.suffix == '.py' and a.read_text(encoding='utf-8').startswith('"""Reproduces')
    assert save_script(log, tmp_path / 'out', 'orders.csv') == a
