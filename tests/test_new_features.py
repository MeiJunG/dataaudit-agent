import csv

import pandas as pd

import app
from src.grounding import check_grounding
from src.presentation import execution_html
from src.result_tables import result_table, save_result_csv
from src.suggestions import column_kinds, profile_html, suggest_questions


def ok(tool, result, **args):
    return {'step': 1, 'tool': tool, 'arguments': args, 'status': 'ok', 'result': str(result), 'structured_result': result if isinstance(result, dict) else None}


def test_grounding_accepts_rounded_percent_and_argument_numbers():
    trace = [ok('x', {'mean': 12.3456, 'share': 0.125, 'rows': 120}, threshold=45.5)]
    g = check_grounding('平均值约 12.35，占比 12.5%，共 120 行，阈值 45.5。', trace)
    assert g['unverified'] == [] and g['checked'] == 4


def test_grounding_flags_invented_numbers_and_skips_tiny_integers():
    trace = [ok('x', {'total': 100.0})]
    g = check_grounding('合计 100，其中第 2 类是 37.5。', trace)
    assert g['unverified'] == ['37.5']
    assert check_grounding('没有数字', trace) is None
    assert check_grounding('合计 100', [{'status': 'error', 'tool': 'x'}]) is None


def test_execution_html_shows_grounding_note():
    trace = [ok('x', {'a': 1.0})]
    trace[0]['grounding'] = {'checked': 2, 'unverified': ['9.99']}
    assert '9.99' in execution_html(trace) and 'grounding warn' in execution_html(trace)
    trace[0]['grounding'] = {'checked': 2, 'unverified': []}
    assert 'grounding ok' in execution_html(trace)


def frame():
    return pd.DataFrame({'区域': ['东', '西', '东', '西', '北', '东'], '数量': [1.5, 2, 3, 4, 5, 6.5],
                         '日期': ['2024-01-03', '2024-02-10', '2024-02-11', '2024-03-01', '2024-03-05', '2024-04-01'],
                         '备注': list('abcdef'), 'user_id': range(6)})


def test_column_kinds_and_suggestions_are_type_driven():
    kinds = column_kinds(frame())
    assert kinds['区域'] == 'category' and kinds['数量'] == 'number' and kinds['日期'] == 'date'
    assert kinds['user_id'] == 'sensitive'
    qs = suggest_questions(frame())
    assert 0 < len(qs) <= 5 and any('区域' in q and '数量' in q for q in qs)
    assert all('user_id' not in q for q in qs)
    assert suggest_questions(None) == [] and suggest_questions(pd.DataFrame()) == []


def test_suggestions_do_not_assume_any_column_names():
    other = pd.DataFrame({'foo': [1, 2, 3, 4], 'bar': ['a', 'b', 'a', 'b']})
    qs = suggest_questions(other)
    assert any('bar' in q and 'foo' in q for q in qs)


def test_profile_hides_sensitive_and_escapes_html():
    df = pd.DataFrame({'<b>x</b>': [1, 2, None], 'user_id': [11, 22, 33]})
    html = profile_html(df)
    assert '&lt;b&gt;' in html and '<b>x</b>' not in html and '11' not in html and '已隐藏' in html
    assert '上传表格后' in profile_html(None)


def test_result_csv_for_group_query_and_formula_safety(tmp_path):
    trace = [ok('aggregate_rows', {'kind': 'table_aggregate', 'metric': 'sum', 'group_by': ['g'],
                                   'groups': [{'keys': {'g': '=cmd|x'}, 'value': 5.5, 'rows': 2, 'missing_values': 0, 'invalid_values': 0},
                                              {'keys': {'g': '乙'}, 'value': -3, 'rows': 1, 'missing_values': 0, 'invalid_values': 0}]})]
    path = save_result_csv(trace, tmp_path)
    raw = path.read_bytes()
    assert raw.startswith(b'\xef\xbb\xbf')
    rows = list(csv.reader(raw.decode('utf-8-sig').splitlines()))
    assert rows[0] == ['g', '结果', '记录数', '缺失', '无效数值']
    assert rows[1][0] == "'=cmd|x" and rows[2][1] == '-3'  # text neutralised, numbers untouched


def test_result_csv_row_query_and_none(tmp_path):
    q = ok('query_rows', {'kind': 'row_query', 'columns': ['a'], 'rows': [{'table_row': 2, 'values': {'a': 7}}]})
    assert result_table([q]) == (['数据行', 'a'], [[2, 7]])
    assert save_result_csv([ok('inspect_schema', {'kind': 'other'})], tmp_path) is None
    assert save_result_csv([], tmp_path) is None


def test_app_handlers_for_new_features(tmp_path, monkeypatch):
    monkeypatch.setattr(app, 'EXPORT_DIR', tmp_path)
    assert app.on_table_download([])['visible'] is False
    update = app.on_suggestions(frame())
    assert update['visible'] and update['choices']
    assert not app.on_suggestions(None)['visible']
    assert app.on_suggestion_pick('问题') == '问题'
