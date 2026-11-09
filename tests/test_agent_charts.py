import copy
import json

import pandas as pd
import pytest
from langchain_core.messages import AIMessage, ToolMessage

import app
from src import agent
from src.agent_charts import chart_figure, chart_spec_from_trace, render_chart_answer, save_chart
from src.tools import build_tools


def invoke(frame, **kwargs):
    tool = next(t for t in build_tools(frame) if t.name == 'create_chart')
    return json.loads(tool.invoke(kwargs))


def trace(spec):
    return [{'tool': 'create_chart', 'status': 'ok', 'structured_result': spec}]


def test_bar_counts_all_rows_and_sum_keeps_all_invalid_groups_null():
    frame = pd.DataFrame({'region': ['East', 'East', 'West', None], 'amount': ['10', None, 'bad', 20]})
    count = invoke(frame, chart_type='bar', x='region')
    assert count['data'] == [{'x': 'East', 'y': 2}, {'x': 'West', 'y': 1}]
    summed = invoke(frame, chart_type='bar', x='region', y='amount', method='sum')
    assert summed['data'] == [{'x': 'East', 'y': 10.0}, {'x': 'West', 'y': None}]
    assert summed['excluded_x_rows'] == 1 and summed['excluded_metric_rows'] == 2
    assert summed['plotted_rows'] == 3
    mean = invoke(frame, chart_type='bar', x='region', y='amount', method='mean')
    assert mean['data'][0]['y'] == 10


def test_histogram_accounts_for_bins_invalid_and_infinite_values():
    frame = pd.DataFrame({'amount': [0, 10, 5, None, 'bad', float('inf')]})
    result = invoke(frame, chart_type='histogram', x='amount')
    assert len(result['data']) == 10
    assert sum(p['y'] for p in result['data']) == 3
    assert result['data'][0]['y'] == 1 and result['data'][-1]['y'] == 1
    assert result['plotted_rows'] == 3 and result['excluded_x_rows'] == 3
    assert chart_spec_from_trace(trace(result)) == result


def test_line_uses_utc_months_excludes_bad_dates_and_keeps_duplicate_rows():
    frame = pd.DataFrame({'when': ['2026-11-01T00:30:00+02:00', '2026-11-02', 'bad', None, '2026-11-02'],
                          'value': [10, 20, 900, 800, 20]})
    result = invoke(frame, chart_type='line', x='when', y='value', method='sum', frequency='month')
    assert result['data'] == [{'x': '2026-10-01', 'y': 10.0}, {'x': '2026-11-01', 'y': 40.0}]
    assert result['plotted_rows'] == 3 and result['excluded_x_rows'] == 2
    counts = invoke(frame, chart_type='line', x='when', frequency='week')
    assert counts['data'] == [{'x': '2026-10-26', 'y': 1}, {'x': '2026-11-02', 'y': 2}]


@pytest.mark.parametrize('arguments', [
    {'chart_type': 'bar', 'x': 'absent'},
    {'chart_type': 'bar', 'x': 'email'},
    {'chart_type': 'bar', 'x': 'region', 'y': 'email', 'method': 'sum'},
    {'chart_type': 'bar', 'x': 'region', 'method': 'sum'},
    {'chart_type': 'bar', 'x': 'region', 'y': 'amount', 'method': 'count'},
    {'chart_type': 'histogram', 'x': 'amount', 'y': 'amount'},
    {'chart_type': 'histogram', 'x': 'region'},
    {'chart_type': 'line', 'x': 'region'},
])
def test_rejects_unsafe_or_ambiguous_chart_requests(arguments):
    frame = pd.DataFrame({'region': ['East'], 'amount': [3], 'email': ['private@example.test']})
    assert 'error' in invoke(frame, **arguments)


def test_group_limits_and_empty_numeric_metric_produce_errors():
    assert 'error' in invoke(pd.DataFrame({'c': list(range(31))}), chart_type='bar', x='c')
    assert 'error' in invoke(pd.DataFrame({'c': ['x' * 257]}), chart_type='bar', x='c')
    assert 'error' in invoke(pd.DataFrame({'c': ['A'], 'v': ['bad']}), chart_type='bar', x='c', y='v', method='sum')
    assert 'error' in invoke(pd.DataFrame({'c': []}), chart_type='bar', x='c')


def test_renderer_escapes_labels_and_export_is_self_contained(tmp_path):
    spec = invoke(pd.DataFrame({'c': ['<b>unsafe</b>'], 'v': [12]}), chart_type='bar', x='c', y='v', method='sum')
    fig = chart_figure(spec)
    assert fig.data[0].x[0] == '&lt;b&gt;unsafe&lt;/b&gt;'
    path = save_chart(spec, tmp_path)
    content = path.read_text(encoding='utf-8')
    assert 'plotly.js v' in content and '<script src=' not in content
    assert 'Rows with valid x: 1' in content
    assert save_chart(spec, tmp_path) == path
    assert len(list(tmp_path.iterdir())) == 1


def test_invalid_or_failed_chart_observations_cannot_be_rendered():
    spec = invoke(pd.DataFrame({'c': ['A']}), chart_type='bar', x='c')
    for mutate in [lambda s: s.update(chart_type='python'), lambda s: s.update(data=[{'x':'A','y':float('nan')}]),
                   lambda s: s.pop('rows'), lambda s: s.update(plotted_rows=999)]:
        bad = copy.deepcopy(spec)
        mutate(bad)
        assert chart_spec_from_trace(trace(bad)) is None
    failed = trace(spec)
    failed[0]['status'] = 'error'
    assert chart_spec_from_trace(failed) is None
    assert render_chart_answer(trace(spec), '画图').startswith('柱状图已生成')
    assert render_chart_answer(trace(spec) + [{'tool':'check_missing_values','status':'ok'}], '画图查空值') is None


def test_chart_web_callback_download_and_reset(tmp_path, monkeypatch):
    monkeypatch.setattr(app, 'CHART_DIR', tmp_path)
    frame = pd.DataFrame({'amount': [1, 2]})
    spec = invoke(frame, chart_type='histogram', x='amount')
    figure, download, tabs = app.on_agent_chart(trace(spec))
    assert sum(figure.data[0].y) == 2 and download['visible']
    assert tabs['selected'] == 'agent-chart'
    _, download, tabs = app.on_agent_chart([])
    assert download['value'] is None and not download['visible'] and tabs['selected'] == 'distribution'
    assert 'amount' in app.on_chart_question(frame)
    assert '上传' in app.on_chart_question(None)


def test_real_chart_tool_observation_is_consumed_by_agent(monkeypatch):
    class Model:
        def __init__(self, **kwargs):
            self.calls = 0
        def bind_tools(self, tools):
            return self
        def invoke(self, messages):
            self.calls += 1
            if self.calls == 1:
                return AIMessage(content='', tool_calls=[{'name':'create_chart', 'id':'chart-1',
                    'args':{'chart_type':'bar','x':'region','y':'amount','method':'sum'}}])
            assert isinstance(messages[-1], ToolMessage)
            assert json.loads(messages[-1].content)['data'] == [{'x':'East','y':30.0}]
            return AIMessage(content='999 rows plotted')
    monkeypatch.setattr(agent, 'ChatOpenAI', Model)
    answer, logs = agent.run_agent('按地区画图', pd.DataFrame({'region':['East','East'], 'amount':[10,20]}))
    assert '999' not in answer and '横轴有效的有 2 行' in answer
    assert logs[0]['structured_result']['data'][0]['y'] == 30


def test_matching_time_aggregate_does_not_force_model_to_rewrite_chart_values():
    spec = invoke(pd.DataFrame({'date':['2026-10-01'], 'v':[12]}), chart_type='line', x='date', y='v', method='sum', frequency='day')
    extra = {'tool':'summarize_time_series', 'status':'ok', 'structured_result':{
        'date_column':'date', 'metric_column':'v', 'method':'sum', 'frequency':'day'}}
    assert render_chart_answer([extra] + trace(spec), '画图').startswith('折线图已生成')
    extra['structured_result']['frequency'] = 'month'
    assert render_chart_answer([extra] + trace(spec), '画图') is None
