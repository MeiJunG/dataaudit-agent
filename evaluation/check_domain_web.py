"""Computed-evidence checks across five synthetic domains and representation warnings."""
from pathlib import Path
import argparse
import json
import math
import time
from datetime import date,timedelta
from gradio_client import Client


def successful(trace,name):
    return [e.get('structured_result',{}) for e in trace if e['tool']==name and e['status']=='ok']


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',default='http://127.0.0.1:7860')
    parser.add_argument('--output',type=Path,default=Path('results/domain-web.json'))
    args=parser.parse_args()
    client=Client(args.url,verbose=False)
    record={'complete':False,'cases':[],'scope':'Synthetic development prompts, computed tool evidence; not held-out reliability or domain certification.'}
    def checkpoint():
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n', encoding='utf-8')
    def mean_check(trace,column,value):
        return any(r.get('column')==column and math.isclose(r.get('mean',-999),value,rel_tol=1e-9) for r in successful(trace,'analyze_distribution'))
    def count_check(trace,column,count):
        return any(r.get('filter_column')==column and r.get('matched_rows')==count and r.get('method')=='count' for r in successful(trace,'filter_and_aggregate'))
    def chart(trace,kind,x,y,method,expected):
        return any(r.get('chart_type')==kind and r.get('x')==x and r.get('y')==y and r.get('method')==method and r.get('data')==expected for r in successful(trace,'create_chart'))
    stock_points=[{'x':str(date(2026,1,1)+timedelta(days=i)),'y':None if i==20 else 100+i*.5} for i in range(45)]
    cases=[
        ('grades-mean','成绩','数学的平均分是多少？',lambda t:mean_check(t,'数学',74)),
        ('grades-threshold','成绩','统计数学不低于60的记录数量，缺失分数不计入。',lambda t:count_check(t,'数学',4)),
        ('grades-chart','成绩','按班级分组，用数学的平均分画柱状图。',lambda t:chart(t,'bar','班级','数学','mean',[{'x':'一班','y':200/3},{'x':'二班','y':85.0}])),
        ('sales-filter','销售','只看状态等于已完成的记录，销售额（元）合计是多少？',lambda t:(any(r.get('filter_column')=='状态' and r.get('aggregate_value')==3500 and r.get('matched_rows')==3 for r in successful(t,'filter_and_aggregate')) or any(r.get('metric')=='sum' and r.get('value_column')=='销售额（元）' and r.get('summary',{}).get('value')==3500 and r.get('matched_rows')==3 and r.get('match')=='all' and any(c.get('column')=='状态' and c.get('operator')=='eq' and c.get('value')=='已完成' for c in r.get('conditions',[])) for r in successful(t,'aggregate_rows')))),
        ('sales-monthly','销售','按日期每月汇总销售额（元）的合计，画折线图。保留退款负数。',lambda t:chart(t,'line','日期','销售额（元）','sum',[{'x':'2026-01-01','y':3500.0},{'x':'2026-02-01','y':-200.0}])),
        ('stock-45-days','股价','这是单一虚构股票。按日期每天的收盘价平均值画折线图，保留缺失，不预测。',lambda t:chart(t,'line','日期','收盘价','mean',stock_points)),
        ('inventory-threshold','库存','库存数量小于10的有多少条记录？',lambda t:count_check(t,'库存数量',3)),
        ('inventory-key','库存','商品编码能作为主键吗？检查缺失和重复。',lambda t:any(r.get('columns')==['商品编码'] and r.get('duplicate_key_rows')==2 and r.get('redundant_rows')==1 for r in successful(t,'check_key_uniqueness'))),
        ('survey-mean','问卷','满意评分的平均值是多少？',lambda t:mean_check(t,'满意评分',3.4)),
        ('survey-frequencies','问卷','统计满意度每种取值的记录数。',lambda t:any(r.get('column')=='满意度' and {'满意':2,'非常满意':1,'一般':1,'不满意':1}.items()<=dict((x['value'],x['count']) for x in r.get('top_frequencies',[])).items() for r in successful(t,'analyze_distribution'))),
        ('representation-hints','格式与单位','运行数据类型检查，指出带货币、百分号、单位或非ISO日期的字段；不转换数据。',lambda t:any({h['kind'] for h in r.get('representation_hints',[])}=={'percent_text','currency_or_grouping_text','unit_suffix_text','non_iso_date_text'} for r in successful(t,'validate_data_types'))),
    ]
    for name,domain,question,check in cases:
        if domain=='格式与单位':
            client.predict('成绩',api_name='/on_domain_example')
            client.predict(api_name='/on_import_settings')
            client.predict(domain,1,api_name='/on_read_table')
            settings=client.predict(api_name='/on_import_settings')
            assert '货币' in settings[-1] and '百分号' in settings[-1]
            record['representation_warning_visible_in_settings']=True
        else:
            client.predict(domain,api_name='/on_domain_example')
        assert client.predict(api_name='/on_history_choices')['choices']==[]
        start=time.perf_counter()
        answer,trace,_=client.predict(question,api_name='/on_submit')
        ok=bool(check(trace)) and not any(p in answer for p in ['这次没有算完','回答未完成','tool-call limit','model repeated a tool call'])
        record['cases'].append({'id':name,'domain':domain,'question':question,'success':ok,'seconds':round(time.perf_counter()-start,3),'answer':answer,'trace':trace})
        checkpoint();print(name,ok,flush=True)
    record.update(complete=True,passed=sum(c['success'] for c in record['cases']),total=len(cases));checkpoint()
    print('DOMAINS',record['passed'],record['total'],flush=True)
    return 0 if record['passed']==record['total'] else 1


if __name__=='__main__': raise SystemExit(main())
