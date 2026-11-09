from pathlib import Path

from src.agent import _tool_entry
from src.business_results import render_business_answer
from src.data_manager import load_csv
from src.tools import build_tools


def result(name, args):
    frame = load_csv(Path(__file__).parents[1] / 'examples' / 'reconciliation.csv')
    output = next(tool for tool in build_tools(frame) if tool.name == name).invoke(args)
    return _tool_entry(name, args, output, 'ok', 1, 1)


def test_range_answer_keeps_counts_consistent():
    trace = [result('check_numeric_range', {'column': 'amount', 'minimum': 0, 'maximum': 250})]
    answer = render_business_answer(trace, '检查金额')
    assert '低于下限 1 个，高于上限 2 个，共 3 个超限' in answer
    assert '缺失 1 个' in answer


def test_reconciliation_answer_includes_both_missing_category():
    trace = [result('compare_columns', {'left_column': 'amount', 'right_column': 'recorded_amount', 'tolerance': .01})]
    answer = render_business_answer(trace, '核对金额')
    assert '一致 5 行，不一致 1 行' in answer
    assert '单边缺失 1 行，双边缺失 1 行' in answer
    assert '0.01' in answer


def test_time_answer_does_not_claim_outlier_checks_and_counts_missing_metric():
    trace = [result('summarize_time_series', {'date_column': 'order_date', 'metric_column': 'amount'})]
    answer = render_business_answer(trace, '按月汇总')
    assert '670' in answer and '无效日期 1 行' in answer
    assert '指标缺失或无效 1 行' in answer
    assert '异常值' not in answer


def test_mixed_analysis_and_failed_round_are_not_overridden():
    trace = [result('check_numeric_range', {'column': 'amount', 'minimum': 0})]
    trace.append({'tool': 'analyze_distribution', 'step': 1, 'status': 'ok', 'result': '{}'})
    assert render_business_answer(trace, 'Check everything') is None
    trace[-1]['status'] = 'error'
    assert render_business_answer(trace, 'Check range') is None
