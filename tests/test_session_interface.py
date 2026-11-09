import json

import pandas as pd
import pytest
from langchain_core.messages import AIMessage, ToolMessage

import app
from src import agent
from src.session_history import add_analysis, empty_history, selection_context


def chart_log():
    return [{'tool':'create_chart','status':'ok', 'step':1,
             'arguments':{'chart_type':'bar','x':'region','y':'amount','method':'sum'}}]


@pytest.mark.parametrize('callback', [app.on_session_office_example, app.on_session_reconciliation_example,
                                    app.on_session_rule_example, app.on_session_consistency_example, app.on_session_clear])
def test_every_dataset_callback_resets_history_atomically(callback):
    result = callback()
    assert len(result) == 11 and result[-2] == empty_history() and result[-1] is None
    assert result[6] == '' and result[7] == [] and result[8]['value'] is None


def test_invalid_upload_also_resets_history(tmp_path):
    result = app.on_session_upload(str(tmp_path/'missing.csv'))
    assert result[0] is None and result[-2] == empty_history() and result[-1] is None


def test_submission_uses_and_appends_session_context(monkeypatch):
    prior = add_analysis(None, 'First chart', 'First answer', chart_log())
    seen = []
    def model(question, frame, **kwargs):
        seen.append(kwargs['history'])
        return 'Current answer', chart_log()
    monkeypatch.setattr(app, 'run_agent', model)
    answer, trace, download, updated = app.on_session_submit('Change average', pd.DataFrame({'amount':[1]}), prior)
    assert seen == [prior] and answer == 'Current answer' and trace
    assert len(updated['entries']) == 2 and len(prior['entries']) == 1
    assert download['value'] is None
    assert updated['entries'][-1]['parent_id'] == prior['active_id']


def test_restore_and_fresh_question_do_not_invoke_model(tmp_path, monkeypatch):
    def no_model(*args, **kwargs):
        raise AssertionError('Restoring history must not invoke inference')
    monkeypatch.setattr(app, 'run_agent', no_model)
    report = tmp_path/'report.md'
    report.write_text('Complete report', encoding='utf-8')
    state = add_analysis(None, 'Question', 'Answer', chart_log(), str(report))
    entry_id = state['active_id']
    restored = app.on_restore_analysis(entry_id, state)
    assert restored[:3] == ('Question', 'Answer', chart_log())
    assert restored[3]['value'] == str(report) and restored[3]['visible']
    fresh = app.on_new_question(state)
    assert fresh[:3] == ('', '', []) and selection_context(fresh[-1]) == ''
    assert len(fresh[-1]['entries']) == 1
    report.unlink()
    assert app.on_restore_analysis(entry_id, state)[3]['value'] is None
    assert app.on_restore_analysis(None, state) == ({'__type__':'update'},) * 5


def test_blank_or_failed_request_keeps_history(monkeypatch):
    state = add_analysis(None, 'First', '', chart_log())
    result = app.on_session_submit('', pd.DataFrame({'amount':[1]}), state)
    assert result[-1] == state and result[1] == []
    result = app.on_session_submit('Question', None, state)
    assert result[-1] == state and result[1] == []


def test_agent_receives_choices_but_recomputes_current_values(monkeypatch):
    state = add_analysis(None, 'Draw total amount by region', 'OLD_PRIVATE_ANSWER', chart_log())
    seen = []
    class Model:
        def __init__(self, **kwargs):
            self.calls = 0
        def bind_tools(self, tools):
            return self
        def invoke(self, messages):
            self.calls += 1
            seen.append(messages)
            if self.calls == 1:
                context = messages[-2].content
                assert 'Earlier requests' in context and 'region' in context and 'sum' in context
                assert 'OLD_PRIVATE_ANSWER' not in context
                return AIMessage(content='', tool_calls=[{'name':'create_chart','id':'new-chart',
                    'args':{'chart_type':'bar','x':'region','y':'amount','method':'mean'}}])
            assert isinstance(messages[-1], ToolMessage)
            assert json.loads(messages[-1].content)['data'] == [{'x':'East','y':20.0}]
            return AIMessage(content='New result')
    monkeypatch.setattr(agent, 'ChatOpenAI', Model)
    answer, trace = agent.run_agent('改成平均值', pd.DataFrame({'region':['East','East'],'amount':[10,30]}), history=state)
    assert '柱状图已生成' in answer and trace[0]['arguments']['method'] == 'mean'
    assert len(seen) == 2


def test_gradio_binds_shared_history_to_all_dataset_actions():
    config = app.build_demo().config
    components = {c['id']:c['type'] for c in config['components']}
    dependencies = {d['api_name']:d for d in config['dependencies'] if d.get('api_name')}
    submit = dependencies['on_submit']
    assert [components[i] for i in submit['inputs']] == ['textbox','state','state','state']
    history_id = submit['inputs'][2]
    reference_id = submit['inputs'][3]
    assert submit['outputs'][-1] == history_id
    for name in ['on_upload','on_office_example','on_reconciliation_example','on_rule_example','on_consistency_example','on_clear']:
        assert dependencies[name]['outputs'][-2] == history_id
        assert dependencies[name]['outputs'][-1] == reference_id
    assert dependencies['on_restore_analysis']['outputs'][-1] == history_id
