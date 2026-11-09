import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest
from langchain_core.messages import AIMessage, ToolMessage

import app
from src import agent
from src.analysis_export import save_analysis_record
from src.comparison_tools import compare_frames
from src.comparison_view import comparison_from_trace, comparison_figure, render_comparison_answer
from src.data_manager import load_csv
from src.session_history import add_analysis, empty_history
from src.tools import build_tools


def frames():
    return (pd.DataFrame({'region':['East','East','West'],'amount':[10,None,50],'quantity':[1,2,3]}),
            pd.DataFrame({'region':['East','West'],'amount':[20,40],'legacy':['old','old']}))


def trace(result):
    return [{'tool':'compare_datasets','status':'ok','structured_result':result}]


def test_compares_schema_missingness_and_exact_distribution_metrics():
    current,reference = frames()
    result = compare_frames(current,reference)
    assert result['schema'] == {'added':['quantity'],'removed':['legacy'],'added_count':1,
        'removed_count':1,'shared_count':2,'dtype_change_count':1}
    values = {v['column']:v for v in result['columns']}
    assert values['amount']['missing']['current'] == 1
    assert values['amount']['missing']['gap_pp'] == pytest.approx(100/3)
    assert values['amount']['numeric']['current_mean'] == values['amount']['numeric']['reference_mean'] == 30
    assert values['region']['categorical']['tvd'] == pytest.approx(1/6)
    shares = {v['label']:v for v in values['region']['categorical']['levels']}
    assert shares['East']['current_rate'] == pytest.approx(2/3)
    assert shares['East']['reference_rate'] == .5
    assert result['current']['rows'] == 3 and result['reference']['rows'] == 2


def test_numeric_comparison_preserves_tiny_nonzero_spread():
    result = compare_frames(pd.DataFrame({'x':[3e-9,5e-9]}),pd.DataFrame({'x':[1e-9,3e-9]}))
    assert result['columns'][0]['numeric']['standardized_change'] == pytest.approx(2)


def test_zero_spread_and_empty_tables_have_undefined_rates_not_fabricated_zeroes():
    current = pd.DataFrame({'x':[10.0,20.0]})
    constant = compare_frames(current,pd.DataFrame({'x':[5.0,5.0]}))
    assert constant['columns'][0]['numeric']['standardized_change'] is None
    empty = compare_frames(current,pd.DataFrame({'x':pd.Series(dtype=float)}))
    assert empty['columns'][0]['missing']['reference_rate'] is None
    assert empty['columns'][0]['numeric']['reference_mean'] is None
    json.dumps(empty,allow_nan=False)


def test_infinite_metrics_are_excluded_but_not_relabeled_as_missing():
    result = compare_frames(pd.DataFrame({'x':[1,float('inf'),None]}),pd.DataFrame({'x':[2.0]}))
    row = result['columns'][0]
    assert row['missing']['current'] == 1 and row['numeric']['valid_current'] == 1
    assert row['numeric']['current_mean'] == 1


def test_sensitive_fields_and_high_cardinality_do_not_expose_values():
    a = pd.DataFrame({'email':['private@example.test'],'salary':[1200]})
    result = compare_frames(a,a)
    assert all(r['distribution']=='omitted_sensitive_name' for r in result['columns'])
    assert 'private@example.test' not in json.dumps(result)
    large = pd.DataFrame({'category':[str(x) for x in range(1001)]})
    assert compare_frames(large,large)['columns'][0]['categorical']['tvd'] is None


@pytest.mark.parametrize('columns',[[],['absent'],['amount','amount'],list('abcdefg')])
def test_invalid_field_selections_are_explicit_errors(columns):
    a,b = frames()
    assert 'error' in compare_frames(a,b,columns)


def test_default_field_limit_and_incompatible_types_are_explicit():
    a = pd.DataFrame({f'c{i}':[i] for i in range(9)})
    result = compare_frames(a,a)
    assert len(result['columns']) == 6 and result['unexamined_shared_columns'] == 3
    mixed = compare_frames(pd.DataFrame({'x':['bad']}),pd.DataFrame({'x':[2]}))
    assert mixed['columns'][0]['distribution'] == 'incompatible_numeric_and_text_types'
    assert 'error' in compare_frames(a,None)


def test_comparison_tool_only_registers_when_a_reference_exists():
    a,b = frames()
    assert len(build_tools(a)) == 25
    tools = {t.name:t for t in build_tools(a,reference_frame=b)}
    assert len(tools) == 26
    focused = json.loads(tools['compare_datasets'].invoke({'columns':['amount']}))
    assert [c['column'] for c in focused['columns']] == ['amount']


def test_comparison_chart_and_answer_use_the_observation(tmp_path,monkeypatch):
    a,b = frames()
    result = compare_frames(a,b)
    chart = comparison_figure(result)
    assert list(chart.data[0].y) == pytest.approx([0,100/3])
    assert list(chart.data[1].y) == [0,0]
    assert chart.layout.yaxis.range[0] == 0
    zero_chart = comparison_figure(compare_frames(b,b))
    assert zero_chart.layout.yaxis.range == (0,5)
    assert '均无缺失值' in zero_chart.layout.annotations[0].text
    focused = comparison_figure(compare_frames(a,b,['region']))
    assert focused.layout.yaxis.title.text == '非空值占比（%）'
    assert dict(zip(focused.data[0].x,focused.data[0].y)) == pytest.approx({'East':200/3,'West':100/3})
    answer = render_comparison_answer(trace(result),'对照两份表')
    assert '当前表 3 行' in answer and '33.3%' in answer and 'quantity' in answer
    assert render_comparison_answer(trace(result)+[{'tool':'check_missing_values','status':'ok'}],'Compare') is None
    monkeypatch.setattr(app,'CHART_DIR',tmp_path)
    fig,download,tabs = app.on_agent_chart(trace(result))
    assert len(fig.data)==2 and download['visible'] and tabs['selected']=='agent-chart'
    assert Path(download['value']).is_file()


def test_csv_fingerprint_and_export_match_the_selected_snapshots(tmp_path,monkeypatch):
    path = tmp_path/'current.csv'
    path.write_text('region,amount\nEast,10\nWest,20\n', encoding='utf-8')
    frame = load_csv(path)
    assert frame.attrs['source_sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
    reference,*cleared = app.on_reference_upload(str(path))
    assert cleared[0:2] == ['',[]] and cleared[-1] == empty_history()
    assert 'current.csv' in app.on_reference_status(reference)
    assert app.on_reference_clear()[0] is None
    assert app.on_reference_upload(str(tmp_path/'missing.csv'))[0]['frame'] is None
    monkeypatch.setattr(app,'run_agent',lambda q,f,**kwargs: ('Compared',trace(compare_frames(f,kwargs['reference_frame']))))
    _,_,_,history = app.on_session_submit('Compare',frame,empty_history(),reference)
    record = json.loads(save_analysis_record(history,tmp_path).read_text(encoding='utf-8'))
    assert record['metadata']['dataset']['sha256'] == record['metadata']['reference']['sha256'] == frame.attrs['source_sha256']
    assert record['question'] == 'Compare'
    monkeypatch.setattr(app,'RECORD_DIR',tmp_path)
    exported = app.on_analysis_export(history)
    assert exported['visible'] and 'href="/analysis-records/analysis-' in exported['value']
    assert ' download="analysis-' in exported['value'] and '.json"' in exported['value']
    assert not app.on_analysis_export(empty_history())['visible']
    assert app.on_current_export(history,history['entries'][-1]['trace'])['visible']
    assert not app.on_current_export(history,[])['visible']
    assert not app.on_current_export(history,[{'tool':'unrelated'}])['visible']


def test_reference_tool_result_is_observed_before_the_agent_finishes(monkeypatch):
    a,b = frames()
    class Model:
        def __init__(self,**kwargs): self.calls=0
        def bind_tools(self,tools,**kwargs):
            self.router = tools[0].name=='select_analysis_scope'
            if self.router:
                return self
            assert any(t.name=='compare_datasets' for t in tools)
            return self
        def invoke(self,messages):
            if self.router:
                return AIMessage(content='',tool_calls=[{'name':'select_analysis_scope','args':{'scope':'reference_comparison'},'id':'scope-1'}])
            self.calls+=1
            if self.calls==1:
                return AIMessage(content='',tool_calls=[{'name':'compare_datasets','args':{},'id':'compare-1'}])
            assert isinstance(messages[-1],ToolMessage)
            assert json.loads(messages[-1].content)['rows']==[3,2]
            assert len(messages[-1].content) < len(json.dumps(compare_frames(a,b)))
            return AIMessage(content='999 rows changed.')
    monkeypatch.setattr(agent,'ChatOpenAI',Model)
    answer,logs = agent.run_agent('对照两份表',a,reference_frame=b)
    assert '999' not in answer and '当前表 3 行' in answer
    assert comparison_from_trace(logs)['schema']['added']==['quantity']
    assert logs[0]['routing']['scope']=='reference_comparison'
