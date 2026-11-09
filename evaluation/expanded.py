"""Sequential live-model evaluation across the registered data tools; synthetic data only."""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / '.env')

from src.agent import run_agent
from src.model_config import request_options
import hashlib


def frames() -> dict[str, pd.DataFrame]:
    office = pd.read_csv(ROOT / 'examples' / 'office_orders.csv')
    office['age_text'] = ['20', '30', 'unknown', '40', '50', '60', '70', '80', '80']
    office['doubled_amount'] = office['amount'] * 2
    return {'office': office, 'outliers': pd.DataFrame({'value': [1, 2, 3, 4, 100]}),
            'reconciliation': pd.read_csv(ROOT / 'examples' / 'reconciliation.csv'),
            'rules': pd.read_csv(ROOT / 'examples' / 'rule_checks.csv'),
            'consistency': pd.read_csv(ROOT / 'examples' / 'consistency_checks.csv')}


def observation(entry: dict) -> dict:
    if isinstance(entry.get('structured_result'), dict):
        return entry['structured_result']
    try:
        parsed = json.loads(entry.get('result', ''))
        return parsed if isinstance(parsed, dict) else {}
    except (ValueError, TypeError):
        return {}


def close(value, expected) -> bool:
    return isinstance(value, (float, int)) and math.isclose(value, expected, rel_tol=1e-7, abs_tol=1e-7)


def matches(check: str, trace: list[dict]) -> bool:
    """Check returned evidence against fixed fixture facts, independently of generated prose."""
    ok = [entry for entry in trace if entry.get('status') == 'ok']
    by_tool = {}
    for entry in ok:
        by_tool.setdefault(entry['tool'], []).append(entry)
    def values(name):
        return [observation(entry) for entry in by_tool.get(name, [])]
    if check.startswith('chart_'):
        for spec in values('create_chart'):
            if check == 'chart_histogram' and spec.get('chart_type') == 'histogram' and spec.get('x') == 'amount':
                if spec.get('plotted_rows') == 8 and spec.get('excluded_x_rows') == 1 and sum(p['y'] for p in spec.get('data', [])) == 8:
                    return True
            elif check in {'chart_region_sum', 'chart_region_count'} and spec.get('chart_type') == 'bar' and spec.get('x') == 'region':
                expected = {'East':360,'North':540,'West':160} if check == 'chart_region_sum' else {'East':3,'North':2,'West':4}
                actual = {p['x']:p['y'] for p in spec.get('data', [])}
                method = 'sum' if check == 'chart_region_sum' else 'count'
                if spec.get('method') == method and actual == expected and (method == 'count' or spec.get('y') == 'amount'):
                    return True
            elif check == 'chart_daily_sum' and spec.get('chart_type') == 'line' and spec.get('x') == 'order_date' and spec.get('y') == 'amount' and spec.get('method') == 'sum' and spec.get('frequency') == 'day':
                expected = {'2026-10-01':120,'2026-10-02':80,'2026-10-03':180,'2026-10-04':None,'2026-10-05':60,'2026-10-06':240,'2026-10-08':80}
                if {p['x']:p['y'] for p in spec.get('data', [])} == expected and spec.get('excluded_x_rows') == 1 and spec.get('excluded_metric_rows') == 1:
                    return True
        return False
    if check == 'text_quality':
        return any(any(field.get('column') == 'status' and field.get('outer_whitespace_values') == 1
                       and field.get('normalized_collision_groups') == 1 and field.get('collision_rows') == 5
                       for field in x.get('fields', [])) for x in values('check_text_quality'))
    if check == 'required_if':
        return any(x.get('condition_column') == 'status' and x.get('equals') == 'completed'
                   and set(x.get('required_columns', [])) == {'amount','recorded_amount'}
                   and x.get('matched_rows') == 3 and x.get('affected_rows') == 2
                   and x.get('missing_by_column') == {'amount':1,'recorded_amount':1}
                   for x in values('check_required_if'))
    if check == 'date_order':
        return any(x.get('start_column') == 'order_date' and x.get('end_column') == 'ship_date'
                   and x.get('allow_equal') is True and x.get('compared_rows') == 4
                   and x.get('violation_rows') == 1 and x.get('missing_date_pair_rows') == 1
                   and x.get('invalid_date_pair_rows') == 1 for x in values('check_date_order'))
    if check == 'allowed_categories':
        return any(x.get('column') == 'status' and set(x.get('allowed_values', [])) == {'completed','pending','cancelled'}
                   and x.get('case_sensitive') is True and x.get('unexpected_values') == 2
                   and x.get('non_null_values') == 8 and x.get('missing_values') == 0
                   for x in values('validate_categories'))
    if check == 'primary_key':
        return any(x.get('columns') == ['order_id'] and x.get('missing_key_rows') == 1
                   and x.get('duplicate_key_rows') == 2 and x.get('redundant_rows') == 1
                   and x.get('distinct_complete_keys') == 6 and x.get('usable_key') is False
                   for x in values('check_key_uniqueness'))
    if check == 'filtered_sum':
        direct = any(x.get('filter_column') == 'status' and x.get('operator') == 'eq'
                     and x.get('filter_value') == 'completed' and x.get('metric_column') == 'amount'
                     and x.get('method') == 'sum' and x.get('matched_rows') == 4
                     and x.get('missing_metric_values') == 1 and close(x.get('aggregate_value'), 330)
                     for x in values('filter_and_aggregate'))
        equivalent = any(x.get('group_column') == 'status' and x.get('metric_column') == 'amount'
                         and x.get('method') == 'sum' and any(row.get('group') == 'completed' and
                         row.get('rows') == 4 and row.get('metric_non_null') == 3 and close(row.get('sum'),330)
                         for row in x.get('groups',[])) for x in values('compare_groups'))
        return direct or equivalent
    if check == 'numeric_range':
        return any(x.get('column') == 'amount' and close(x.get('minimum'), 0) and close(x.get('maximum'), 250)
                   and x.get('checked_values') == 7 and x.get('violation_count') == 3
                   and x.get('below_minimum') == 1 and x.get('above_maximum') == 2
                   and x.get('missing_values') == 1 for x in values('check_numeric_range'))
    if check == 'reconciliation':
        return any({x.get('left_column'), x.get('right_column')} == {'amount', 'recorded_amount'}
                   and x.get('mode') == 'numeric' and close(x.get('absolute_tolerance'), .01)
                   and x.get('compared_rows') == 6 and x.get('matched_rows') == 5
                   and x.get('mismatched_rows') == 1 and x.get('one_side_missing_rows') == 1
                   and x.get('both_missing_rows') == 1 for x in values('compare_columns'))
    if check == 'monthly_total':
        return any(x.get('date_column') == 'order_date' and x.get('metric_column') == 'amount'
                   and x.get('frequency') == 'month' and x.get('method') == 'sum'
                   and x.get('invalid_date_rows') == 1 and len(x.get('periods', [])) == 1
                   and x['periods'][0].get('period_start') == '2026-10-01'
                   and close(x['periods'][0].get('value'), 670) for x in values('summarize_time_series'))
    if check == 'schema':
        return any(x.get('rows') == 9 and x.get('columns') == 8 for x in values('inspect_schema'))
    if check == 'missing':
        for x in values('check_missing_values'):
            counts = {row['column']: row['missing_count'] for row in x.get('by_column', [])}
            if counts == {'order_date': 0, 'region': 0, 'department': 0, 'amount': 1, 'quantity': 0,
                          'status': 0, 'age_text': 0, 'doubled_amount': 1}:
                return True
        return False
    if check in {'duplicates', 'region_duplicates'}:
        subset = None if check == 'duplicates' else ['region']
        return any(entry.get('arguments', {}).get('subset') == subset and
                   observation(entry).get('duplicate_rows') == (1 if subset is None else 6)
                   for entry in by_tool.get('check_duplicates', []))
    if check == 'outliers':
        return any(x.get('column') == 'value' and x.get('outlier_count') == 1 and
                   close(x.get('lower_bound'), -1) and close(x.get('upper_bound'), 7)
                   for x in values('detect_outliers'))
    if check == 'amount_distribution':
        return any(x.get('column') == 'amount' and close(x.get('mean'), 132.5) and
                   close(x.get('median'), 100) for x in values('analyze_distribution'))
    if check == 'status_distribution':
        direct = any(x.get('column') == 'status' and
                   {r['value']: r['count'] for r in x.get('top_frequencies', [])} == {'completed': 7, 'pending': 2}
                   for x in values('analyze_distribution'))
        equivalent = any(x.get('group_column') == x.get('metric_column') == 'status' and
                         x.get('method') == 'count' and
                         {r['group']: r.get('count') for r in x.get('groups', [])} == {'completed': 7, 'pending': 2}
                         for x in values('compare_groups'))
        return direct or equivalent
    if check == 'types':
        return any(any(issue.get('column') == 'age_text' and issue.get('invalid_count') == 1
                       for issue in x.get('issues', [])) for x in values('validate_data_types'))
    if check == 'correlation':
        return any(any({pair.get('left'), pair.get('right')} == {'amount', 'doubled_amount'} and
                       close(pair.get('pearson_r'), 1) for pair in x.get('pairs', []))
                   for x in values('check_correlations'))
    if check in {'group_mean', 'group_sum', 'group_count'}:
        method = {'group_mean': 'mean', 'group_sum': 'sum', 'group_count': 'count'}[check]
        expected = {'mean': {'East': 120, 'West': 160 / 3, 'North': 270},
                    'sum': {'East': 360, 'West': 160, 'North': 540},
                    'count': {'East': 3, 'West': 4, 'North': 2}}[method]
        column = 'status' if method == 'count' else 'amount'
        for x in values('compare_groups'):
            if x.get('method') != method or x.get('group_column') != 'region' or x.get('metric_column') != column:
                continue
            actual = {row['group']: row.get(method) for row in x.get('groups', [])}
            if set(actual) == set(expected) and all(close(actual[key], value) for key, value in expected.items()):
                return True
        return False
    if check == 'dates':
        return any(x.get('column') == 'order_date' and x.get('parsed_dates') == 8 and
                   x.get('invalid_non_null_values') == 1 and str(x.get('earliest')).startswith('2026-10-01') and
                   str(x.get('latest')).startswith('2026-10-08') for x in values('inspect_date_column'))
    if check == 'report':
        return any('- Rows: 9' in entry.get('report_markdown', '') and
                   '- Missing cells: 2 / 72' in entry.get('report_markdown', '') and
                   '- Fully duplicated rows: 1' in entry.get('report_markdown', '') and
                   entry.get('report_markdown', '').endswith('data errors or causation.')
                   for entry in by_tool.get('generate_quality_report', []))
    raise ValueError(f'Unknown evidence check: {check}')


def write_checkpoint(path: Path, record: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    staging = path.with_suffix('.tmp')
    staging.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    staging.replace(path)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit', type=int)
    parser.add_argument('--tasks', type=Path, default=ROOT / 'evaluation' / 'expanded_tasks.json')
    parser.add_argument('--max-steps', type=int, default=3)
    parser.add_argument('--output', type=Path, default=ROOT / 'results' / 'expanded.json')
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit < 1:
        parser.error('--limit must be positive')
    if not 1 <= args.max_steps <= 12:
        parser.error('--max-steps must be in 1..12')
    tasks = json.loads(args.tasks.read_text(encoding='utf-8'))
    if args.limit:
        tasks = tasks[:args.limit]
    datasets = frames()
    record = {'request_options': request_options(), 'tasks_sha256': hashlib.sha256(args.tasks.read_bytes()).hexdigest(), 'suite': args.tasks.stem, 'scorer_revision': 2, 'tasks_file': args.tasks.name, 'model': os.getenv('MODEL_NAME', 'qwen2.5-7b-instruct'),
              'scope': 'Computed tool evidence and termination; generated prose accuracy is not automatically scored.',
              'max_steps': args.max_steps, 'complete': False, 'tasks': []}
    for task in tasks:
        start = time.perf_counter()
        result = {'id': task['id'], 'question': task['question'], 'checks': task['checks']}
        try:
            answer, trace = run_agent(task['question'], datasets[task['dataset']], max_steps=args.max_steps)
            checks = {check: matches(check, trace) for check in task['checks']}
            stopped = any(text in answer for text in ['tool-call limit', 'model repeated a tool call', '回答未完成', '没有取得可用的工具结果', '最后一轮检查没有成功'])
            result.update(answer=answer, trace=trace, checks_passed=checks,
                          success=all(checks.values()) and bool(answer.strip()) and not stopped,
                          error_observations=sum(x['status'] == 'error' for x in trace))
        except Exception as exc:
            result.update(success=False, error=f'{type(exc).__name__}: {exc}')
        result['seconds'] = round(time.perf_counter() - start, 3)
        record['tasks'].append(result)
        record['passed'] = sum(x['success'] for x in record['tasks'])
        record['completed'] = len(record['tasks'])
        record['total'] = len(tasks)
        record['seconds'] = round(sum(x['seconds'] for x in record['tasks']), 3)
        write_checkpoint(args.output, record)
        print(f"{task['id']}: success={result['success']} time={result['seconds']} checks={result.get('checks_passed', {})}", flush=True)
    record['complete'] = True
    write_checkpoint(args.output, record)
    print(json.dumps({key: value for key, value in record.items() if key != 'tasks'}, ensure_ascii=False))
    return 0 if record['passed'] == len(tasks) else 1


if __name__ == '__main__':
    raise SystemExit(main())
