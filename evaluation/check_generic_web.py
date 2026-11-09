"""Live generic-workbook development checks; no domain sheet/field whitelist."""
import argparse
import json
import time
from pathlib import Path
from gradio_client import Client,handle_file
from evaluation.table_fixtures import write_xlsx


def fixture(path):
    return write_xlsx(path,{'empty-7B':[], 'Measure_41':[['Readings, synthetic fixture'],[],['Segment α','Batch β','Metric A','Metric B','Flag'],
        ['L','u',10,2,'ok'],['L','u',20,4,'hold'],['L','v',30,0,'ok'],['R','u',None,5,'ok'],['R','v','bad',2,'hold'],['R','v',40,8,'ok']],
        'Lookup-Z':[['key!?','value!'],['k1',99],['k2',101]]})


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--url',default='http://127.0.0.1:7860');args=parser.parse_args()
    args.output.parent.mkdir(parents=True,exist_ok=True);path=fixture(args.output.parent/'generic-arbitrary.xlsx')
    client=Client(args.url,verbose=False)
    record={'complete':False,'scope':'Eight synthetic development prompts with actual Qwen2.5 + LangGraph + Gradio API; not held-out reliability.','cases':[]}
    cases=[
        ('discover',None,'这个文件里实际有哪些工作表？',lambda rs:any(r.get('sheets')==['empty-7B','Measure_41','Lookup-Z'] for r in rs)),
        ('autonomous-header',None,'先检查 Measure_41 的表头在哪一行，再计算其中 Metric B 的合计。',lambda rs:any(r.get('kind')=='sheet_layout' for r in rs) and any(r.get('kind')=='table_aggregate' and r.get('summary',{}).get('value')==21 and r['origin']['header_row']==3 for r in rs)),
        ('and-query','Measure_41','找出 Metric A 不低于20 且 Flag 等于 ok 的记录，只显示 Metric A、Flag，按 Metric A 降序。',lambda rs:any(r.get('kind')=='row_query' and r.get('matched_rows')==2 and [v['table_row'] for v in r['rows']]==[6,3] for r in rs)),
        ('or-query','Measure_41','查找 Flag 等于 hold 或 Metric A 缺失的记录，两个条件是或关系。',lambda rs:any(r.get('kind')=='row_query' and r.get('match')=='any' and r.get('matched_rows')==3 for r in rs)),
        ('multi-group','Measure_41','按 Segment α 和 Batch β 两个字段一起分组，统计每组记录数，包含 Metric A 缺失的行。',lambda rs:any(r.get('kind')=='table_aggregate' and r.get('group_by')==['Segment α','Batch β'] and sum(g['value'] for g in r.get('groups',[]))==6 and len(r['groups'])==4 for r in rs)),
        ('derived-product','Measure_41','将 Metric A 与 Metric B 逐行相乘，再按 Segment α 分组计算这些乘积的合计，不修改原表。',lambda rs:any(r.get('kind')=='row_metric' and r.get('operation')=='product' and {g['keys']['Segment α']:g['value'] for g in r.get('groups',[])}=={'L':100,'R':320} for r in rs)),
        ('weighted-metric','Measure_41','逐行计算 Metric A 与 Metric B 的加权均值，权重分别是0.25和0.75。缺失和非法值不要补零。',lambda rs:any(r.get('kind')=='row_metric' and r.get('operation')=='weighted_mean' and r.get('weights')==[.25,.75] and r['summary']['sum']==35.5 for r in rs)),
        ('ratio','Measure_41','逐行计算 Metric A 除以 Metric B，按计算值降序；说明缺失、非法输入和除零分别排除了多少行。',lambda rs:any(r.get('kind')=='row_metric' and r.get('operation')=='ratio' and r['summary']['valid_results']==3 and r['summary']['zero_denominator_rows']==1 for r in rs)),
    ]
    for name,sheet,question,check in cases:
        client.predict(handle_file(str(path)),api_name='/on_upload')
        client.predict(api_name='/on_import_settings')
        if sheet: client.predict(sheet,3,api_name='/on_read_table')
        start=time.perf_counter()
        try:
            answer,trace,_=client.predict(question,api_name='/on_submit')
            results=[e.get('structured_result',{}) for e in trace if e['status']=='ok']
            success=bool(check(results)) and not any(x in answer for x in ['回答未完成','model repeated','tool-call limit','这次没有算完'])
            case={'id':name,'question':question,'success':success,'seconds':round(time.perf_counter()-start,3),'answer':answer,'trace':trace}
        except Exception as exc: case={'id':name,'question':question,'success':False,'error':str(exc)}
        record['cases'].append(case);args.output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n', encoding='utf-8');print(name,case['success'],flush=True)
    record.update(complete=True,passed=sum(c['success'] for c in record['cases']),total=len(cases));args.output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n', encoding='utf-8')
    print('GENERIC',record['passed'],record['total'],flush=True)
    return 0 if record['passed']==record['total'] else 1


if __name__=='__main__': raise SystemExit(main())
