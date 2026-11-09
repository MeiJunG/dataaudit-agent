import json
import numpy as np
import pandas as pd
import pytest
from langchain_core.messages import AIMessage,ToolMessage
from evaluation.table_fixtures import write_xlsx
from src.data_manager import load_table
from src.table_tools import build_table_tools,compact_table_observation
from src.table_results import render_table_answer
from src import agent
import app


def generic_workbook(path):
    return write_xlsx(path,{'empty-7B':[], 'Measure_41':[['Readings, synthetic fixture'],[],['Segment α','Batch β','Metric A','Metric B','Flag'],
        ['L','u',10,2,'ok'],['L','u',20,4,'hold'],['L','v',30,0,'ok'],['R','u',None,5,'ok'],['R','v','bad',2,'hold'],['R','v',40,8,'ok']],
        'Lookup-Z':[['key!?','value!'],['k1',99],['k2',101]]})


@pytest.fixture
def frame(tmp_path):
    return load_table(generic_workbook(tmp_path/'arbitrary.xlsx'),sheet='Measure_41',header_row=3)


def call(frame,name,**args):
    return json.loads(next(t for t in build_table_tools(frame) if t.name==name).invoke(args))


def test_actual_sheets_layout_and_target_provenance(frame):
    result=call(frame,'list_workbook_sheets',limit=2)
    assert result['sheets']==['empty-7B','Measure_41'] and result['next_offset']==2
    layout=call(frame,'inspect_sheet_layout',sheet='Measure_41')
    assert layout['header_candidates'][0]['header_row']==3
    other=call(frame,'aggregate_rows',sheet='Lookup-Z',header_row=1,metric='sum',value_column='value!')
    assert other['summary']['value']==200 and other['origin']['sheet']=='Lookup-Z' and other['origin']['header_row']==1
    assert other['origin']['sha256']==frame.attrs['source_sha256']
    assert frame.attrs['import_info']['sheet']=='Measure_41'
    assert 'error' in call(frame,'query_rows',sheet='invented worksheet')
    assert all('path' not in t.args for t in build_table_tools(frame))


def test_empty_cover_still_allows_agent_discovery(frame):
    initial=app.on_import_upload(frame.attrs['_source_path'])
    assert initial[0] is not None and initial[0].attrs['import_info']['unselected']
    assert call(initial[0],'list_workbook_sheets')['total_sheets']==3
    assert call(initial[0],'aggregate_rows',sheet='Lookup-Z',header_row=1,metric='count')['summary']['value']==2


def test_and_or_filter_sort_and_selected_columns(frame):
    filters=[{'column':'Metric A','operator':'ge','value':20},{'column':'Flag','operator':'eq','value':'ok'}]
    x=call(frame,'query_rows',columns=['Metric A','Flag'],conditions=filters,sort_by='Metric A',ascending=False)
    assert x['matched_rows']==2 and [r['table_row'] for r in x['rows']]==[6,3]
    assert set(x['rows'][0]['values'])=={'Metric A','Flag'}
    assert call(frame,'query_rows',conditions=filters,match='any')['matched_rows']==5
    null=call(frame,'query_rows',conditions=[{'column':'Metric A','operator':'is_null'}])
    assert null['matched_rows']==1
    assert 'error' in call(frame,'query_rows',columns=['invented field'])
    with pytest.raises(ValueError):
        call(frame,'query_rows',limit=21)


def test_multi_group_count_and_empty_numeric_aggregate(frame):
    x=call(frame,'aggregate_rows',metric='count',group_by=['Segment α','Batch β'])
    assert x['group_count']==4 and sum(g['value'] for g in x['groups'])==6
    x=call(frame,'aggregate_rows',metric='sum',value_column='Metric A',conditions=[{'column':'Flag','operator':'eq','value':'absent'}])
    assert x['matched_rows']==0 and x['summary']['value'] is None
    x=call(frame,'aggregate_rows',metric='mean',value_column='Metric A')
    assert x['summary']=={'rows':6,'value':25.0,'valid_values':4,'missing_values':1,'invalid_values':1}


@pytest.mark.parametrize('operation,expected',[('sum',114),('product',420),('difference',86),('ratio',15)])
def test_row_operations_are_computed_and_source_unchanged(frame,operation,expected):
    before=frame.copy(deep=True)
    x=call(frame,'calculate_row_metric',columns=['Metric A','Metric B'],operation=operation)
    assert x['summary']['sum']==expected
    assert x['summary']['missing_input_rows']==1 and x['summary']['invalid_input_rows']==1
    assert x['summary']['zero_denominator_rows']==(1 if operation=='ratio' else 0)
    pd.testing.assert_frame_equal(frame,before)


def test_explicit_weights_grouping_and_bad_weights(frame):
    x=call(frame,'calculate_row_metric',columns=['Metric A','Metric B'],operation='weighted_mean',weights=[.25,.75],group_by=['Segment α'],aggregation='sum')
    assert x['groups'][0]['value']==19.5 and x['groups'][1]['value']==16
    assert 'error' in call(frame,'calculate_row_metric',columns=['Metric A','Metric B'],operation='weighted_mean',weights=[1,-1])
    assert 'error' in call(frame,'calculate_row_metric',columns=['Metric A','Metric B'],operation='product',weights=[1,1])


def test_int_overflow_and_nonfinite_are_not_silent():
    frame=pd.DataFrame({'a':[10**12,1e308],'b':[10**12,1e308]})
    x=call(frame,'calculate_row_metric',columns=['a','b'],operation='product')
    assert x['rows'][0]['value']==1e24 and x['summary']['nonfinite_result_rows']==1
    empty=call(pd.DataFrame({'a':[None],'b':[None]}),'calculate_row_metric',columns=['a','b'],operation='sum')
    assert empty['summary']['sum'] is None and empty['summary']['valid_results']==0


def test_sensitive_preview_and_reserved_user_field():
    frame=pd.DataFrame({'email':['private@example.test'],'_row_position_internal':[3]})
    x=call(frame,'query_rows')
    assert x['rows'][0]['values']=={'email':'[hidden]','_row_position_internal':3}
    assert 'private@example.test' not in json.dumps(x)


def test_bounded_observation_full_trace_and_render_origin(frame,monkeypatch):
    class Model:
        def __init__(self,**kwargs): self.calls=0
        def bind_tools(self,tools): return self
        def invoke(self,messages):
            self.calls+=1
            if self.calls==1:
                return AIMessage(content='',tool_calls=[{'id':'read','name':'aggregate_rows','args':{'sheet':'Lookup-Z','header_row':1,'metric':'sum','value_column':'value!'}}])
            assert isinstance(messages[-1],ToolMessage) and json.loads(messages[-1].content)['summary']['value']==200
            return AIMessage(content='Computed.')
    monkeypatch.setattr(agent,'ChatOpenAI',Model)
    answer,trace=agent.run_agent('读取另一个工作表',frame,tool_family='tables')
    assert '200' in answer and 'Lookup-Z' in answer
    assert trace[0]['data_origin']['sheet']=='Lookup-Z'
    assert '_source_path' not in json.dumps(trace)
    value=call(frame,'query_rows',limit=20)
    compact=json.loads(compact_table_observation(json.dumps(value),budget=400))
    assert compact['matched_rows']==6
    assert render_table_answer([{'status':'ok','step':1,'structured_result':value}])


def test_blank_start_and_optional_samples():
    demo=app.build_demo()
    config=demo.get_config_file()
    states=[c for c in config['components'] if c['type']=='state']
    assert states[0]['props'].get('value') is None
    assert any(c['type']=='accordion' and c['props'].get('label')=='示例文件 · 可选' and not c['props']['open'] for c in config['components'])


def test_text_table_does_not_accept_invented_worksheet(tmp_path):
    path=tmp_path/'any.csv';path.write_text('a,b\n1,2\n', encoding='utf-8')
    frame=load_table(path)
    assert 'error' in call(frame,'query_rows',sheet='Sheet1')
    assert call(frame,'query_rows')['rows'][0]['values']=={'a':1,'b':2}


@pytest.mark.parametrize('label,expected',[('tables','tables'),('chart','chart'),('tables please',None)])
def test_router_accepts_only_exact_category_text(label,expected,monkeypatch):
    class Model:
        def bind_tools(self,*args,**kwargs): return self
        def invoke(self,messages): return AIMessage(content=label)
    monkeypatch.setattr(agent,'_base_llm',lambda **kwargs:Model())
    if expected:
        family,routing=agent._choose_tool_family('a request',None)
        assert family==expected and routing['mode_response_format']=='exact_text_label'
    else:
        with pytest.raises(ValueError): agent._choose_tool_family('a request',None)


def test_quality_router_has_a_separate_focused_selection(monkeypatch):
    class Model:
        def bind_tools(self,tools,**kwargs): self.name=tools[0].name;return self
        def invoke(self,messages): return AIMessage(content='quality' if self.name=='select_analysis_mode' else 'profile')
    monkeypatch.setattr(agent,'_base_llm',lambda **kwargs:Model())
    family,routing=agent._choose_tool_family('a request',None)
    assert family=='profile' and routing['mode']=='quality'
