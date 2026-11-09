import json
from datetime import date,timedelta

import pandas as pd
import pytest
from langchain_core.messages import AIMessage,ToolMessage

import app
from evaluation.table_fixtures import domain_workbook
from src import agent
from src.data_manager import load_table
from src.tools import build_tools
from src.agent_charts import chart_spec_from_trace,chart_figure
from src.chart_tools import compact_chart_observation
from src.value_hints import value_hints


def invoke(frame,name,**kwargs):
    return json.loads(next(t for t in build_tools(frame) if t.name==name).invoke(kwargs))


@pytest.fixture
def workbook(tmp_path): return domain_workbook(tmp_path/'domains.xlsx')


def test_grades_use_actual_subject_names_and_user_supplied_threshold(workbook):
    frame=load_table(workbook,sheet='成绩')
    assert invoke(frame,'analyze_distribution',column='数学')['mean']==74
    assert invoke(frame,'filter_and_aggregate',filter_column='数学',operator='ge',value=60)['matched_rows']==4
    assert invoke(frame,'check_numeric_range',column='数学',minimum=0,maximum=100)['violation_count']==0
    assert frame['学号'].tolist()==['001','002','003','004','005','006']


def test_sales_keep_refunds_missing_values_and_underlying_percent(workbook):
    frame=load_table(workbook,sheet='销售')
    result=invoke(frame,'filter_and_aggregate',filter_column='状态',operator='eq',value='已完成',metric_column='销售额（元）',method='sum')
    assert result['aggregate_value']==3500 and result['matched_rows']==3
    assert frame['销售额（元）'].sum()==3300 and frame['销售额（元）'].isna().sum()==1
    assert frame['税率'].tolist()==[.13]*5


def test_stock_line_has_45_points_and_preserves_missing_price(workbook):
    frame=load_table(workbook,sheet='股价')
    result=invoke(frame,'create_chart',chart_type='line',x='日期',y='收盘价',method='mean',frequency='day')
    assert len(result['data'])==45 and result['excluded_metric_rows']==1
    assert result['data'][0]=={'x':'2026-01-01','y':100.0} and result['data'][-1]=={'x':'2026-02-14','y':122.0}
    assert result['data'][20]['y'] is None
    spec=chart_spec_from_trace([{'tool':'create_chart','status':'ok','structured_result':result}])
    assert spec is not None and len(chart_figure(spec).data[0].x)==45
    compact=json.loads(compact_chart_observation(json.dumps(result)))
    assert compact['point_count']==45 and compact['null_points']==1 and 'data' not in compact
    assert len(compact['first_points'])==len(compact['last_points'])==2


def test_line_and_category_limits_are_distinct():
    dates=[str(date(2025,1,1)+timedelta(days=i)) for i in range(367)]
    frame=pd.DataFrame({'日期':dates,'值':range(367)})
    result=invoke(frame.iloc[:366],'create_chart',chart_type='line',x='日期',y='值',method='mean',frequency='day')
    assert len(result['data'])==366
    assert chart_spec_from_trace([{'tool':'create_chart','status':'ok','structured_result':result}]) is not None
    assert 'error' in invoke(frame,'create_chart',chart_type='line',x='日期',y='值',method='mean',frequency='day')
    assert 'error' in invoke(frame.iloc[:31],'create_chart',chart_type='bar',x='日期')


def test_inventory_and_survey_tools_remain_domain_agnostic(workbook):
    inventory=load_table(workbook,sheet='库存')
    assert invoke(inventory,'filter_and_aggregate',filter_column='库存数量',operator='lt',value=10)['matched_rows']==3
    key=invoke(inventory,'check_key_uniqueness',columns=['商品编码'])
    assert key['duplicate_key_rows']==2 and key['redundant_rows']==1
    survey=load_table(workbook,sheet='问卷')
    assert invoke(survey,'analyze_distribution',column='满意评分')['mean']==3.4
    assert survey['愿意推荐'].tolist()==[True,False,True,True,False,False]


def test_formatted_values_are_flagged_without_implicit_currency_or_unit_conversion(workbook):
    frame=load_table(workbook,sheet='格式与单位')
    hints=frame.attrs['import_info']['value_hints']
    assert {h['kind'] for h in hints}=={'percent_text','currency_or_grouping_text','unit_suffix_text','non_iso_date_text'}
    assert frame['金额文字'].tolist()==['￥1,200.00','$800.00','1,500元']
    assert invoke(frame,'analyze_distribution',column='金额文字')['kind']=='categorical'
    assert invoke(frame,'validate_data_types')['representation_hints']==hints
    assert '货币' in app.import_notes({'format':'xlsx','info':frame.attrs['import_info']})
    assert value_hints(pd.DataFrame({'正常数值':[1,2],'文字':['甲','乙']}))==[]


@pytest.mark.parametrize('domain',app.DOMAIN_EXAMPLES)
def test_domain_menu_loads_real_sheet_and_resets_context(domain):
    result=app.on_domain_example(domain)
    assert len(result)==12 and result[0].attrs['import_info']['sheet']==domain
    assert result[9]['sample'] and result[-2]['entries']==[] and result[-1] is None
    assert '示例' in result[1]
    loaded=app.on_domain_load(domain)
    assert len(loaded)==13 and loaded[-1]==app.DOMAIN_QUESTIONS[domain]


def test_long_chart_observation_returns_to_model_with_full_trace_preserved(workbook,monkeypatch):
    frame=load_table(workbook,sheet='股价')
    class Model:
        def __init__(self,**kwargs): self.calls=0
        def bind_tools(self,tools): return self
        def invoke(self,messages):
            self.calls+=1
            if self.calls==1:
                return AIMessage(content='',tool_calls=[{'id':'line','name':'create_chart','args':{'chart_type':'line','x':'日期','y':'收盘价','method':'mean','frequency':'day'}}])
            assert isinstance(messages[-1],ToolMessage)
            result=json.loads(messages[-1].content)
            assert result['point_count']==45 and 'data' not in result
            return AIMessage(content='Chart computed.')
    monkeypatch.setattr(agent,'ChatOpenAI',Model)
    answer,trace=agent.run_agent('画每日收盘价折线图',frame)
    assert '折线图已生成' in answer and len(trace[0]['structured_result']['data'])==45


def test_unambiguous_width_aliases_preserve_literals_and_reject_collisions():
    from src.tool_selection import resolve_field_arguments
    args={'metric_column':'销售额（元)','filter_column':'状态','value':'Ａ','method':'sum'}
    resolved,mapping=resolve_field_arguments(args,['销售额（元）','状态'])
    assert resolved['metric_column']=='销售额（元）' and resolved['value']=='Ａ'
    assert mapping[0]['requested']=='销售额（元)'
    with pytest.raises(ValueError,match='Ambiguous'):
        resolve_field_arguments({'column':' 金额(元) '},['金额(元)','金额（元）'])
    assert resolve_field_arguments({'column':'金额(元)'},['金额(元)','金额（元）'])[0]['column']=='金额(元)'


def test_routed_application_still_runs_observation_to_model_loop(workbook,monkeypatch):
    frame=load_table(workbook,sheet='库存')
    class Model:
        def __init__(self,**kwargs): self.calls=0
        def bind_tools(self,tools,**kwargs):
            self.mode_selection=tools[0].name=='select_analysis_mode'
            self.routing=tools[0].name=='select_tool_family'
            if not self.routing and not self.mode_selection:
                assert 'filter_and_aggregate' in [t.name for t in tools] and 'compare_columns' not in [t.name for t in tools]
            return self
        def invoke(self,messages):
            self.calls+=1
            if self.mode_selection:
                return AIMessage(content='',tool_calls=[{'name':'select_analysis_mode','id':'mode','args':{'mode':'quality'}}])
            if self.routing:
                return AIMessage(content='',tool_calls=[{'name':'select_tool_family','id':'route','args':{'family':'filter'}}])
            if self.calls==1:
                return AIMessage(content='',tool_calls=[{'name':'filter_and_aggregate','id':'count','args':{'filter_column':'库存数量','operator':'lt','value':10}}])
            assert isinstance(messages[-1],ToolMessage) and json.loads(messages[-1].content)['matched_rows']==3
            return AIMessage(content='Computed.')
    monkeypatch.setattr(agent,'ChatOpenAI',Model)
    answer,trace=agent.run_routed_agent('库存数量小于10的有多少条记录？',frame)
    assert '3' in answer and trace[0]['tool_routing']['family']=='filter'
