"""Live import and model checks with synthetic Excel/TSV/GB18030 files."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import time
from urllib.parse import urljoin
from urllib.request import urlopen

from gradio_client import Client, handle_file
from evaluation.table_fixtures import diverse_workbook, write_xls


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',default='http://127.0.0.1:7860')
    parser.add_argument('--output',type=Path,default=Path('results/table-imports-web.json'))
    args=parser.parse_args()
    directory=args.output.parent/'table-fixtures';directory.mkdir(parents=True,exist_ok=True)
    workbook=diverse_workbook(directory/'多样表格.xlsx')
    client=Client(args.url,verbose=False)
    result={'complete':False,'cases':[],'scope':'Synthetic live development checks, not held-out evaluation.'}
    def save(): args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n', encoding='utf-8')
    def request(name,question,check):
        start=time.perf_counter()
        answer,trace,_=client.predict(question,api_name='/on_submit')
        ok=bool(trace) and check(answer,trace)
        result['cases'].append({'id':name,'question':question,'success':bool(ok),'seconds':round(time.perf_counter()-start,3),'answer':answer,'trace':trace})
        save();print(name,ok,flush=True)
        return trace
    def distribution_mean(trace,column,mean):
        return any(e['tool']=='analyze_distribution' and e['status']=='ok' and e.get('structured_result',{}).get('column')==column and e.get('structured_result',{}).get('mean')==mean for e in trace)
    client.predict(handle_file(str(workbook)),api_name='/on_upload')
    assert '说明' in client.predict(api_name='/on_import_settings')[0]['choices'][0]
    client.predict('十月订单',3,api_name='/on_read_table')
    preview=client.predict(api_name='/on_preview')
    assert '金额（元）__2' in preview and 'column_5' in preview and '已隐藏' in preview
    assert client.predict(api_name='/on_history_choices')['choices']==[]
    request('xlsx-chinese-mean','金额（元）的平均值是多少？',lambda a,t: distribution_mean(t,'金额（元）',15))
    trace=request('xlsx-chinese-chart','按地区分组，用金额（元）的平均值画柱状图。',lambda a,t:any(e['tool']=='create_chart' and e['status']=='ok' and e.get('structured_result',{}).get('x')=='地区' and e.get('structured_result',{}).get('y')=='金额（元）' and e.get('structured_result',{}).get('data')==[{'x':'华东','y':10.0},{'x':'华西','y':20.0}] for e in t))
    client.predict(handle_file(str(workbook)),api_name='/on_reference_upload')
    client.predict(api_name='/on_reference_settings')
    client.predict('九月订单',1,api_name='/on_read_reference')
    trace=request('xlsx-reference-sheets','对照参考表，只比较金额（元）的缺失率和均值。',lambda a,t:any(e['tool']=='compare_datasets' and e['status']=='ok' and e.get('structured_result',{}).get('current',{}).get('rows')==3 and e.get('structured_result',{}).get('reference',{}).get('rows')==2 and any(c['column']=='金额（元）' and c.get('numeric',{}).get('current_mean')==15 and c.get('numeric',{}).get('reference_mean')==8 for c in e.get('structured_result',{}).get('columns',[])) for e in t))
    exported=client.predict(trace,api_name='/on_current_export')
    href=re.search(r'href="([^"]+)"',exported['value']).group(1)
    with urlopen(urljoin(args.url,href),timeout=30) as response: record=json.loads(response.read())
    assert record['metadata']['dataset']['import']['sheet']=='十月订单'
    assert record['metadata']['dataset']['import']['header_row']==3
    assert record['metadata']['reference']['import']['sheet']=='九月订单'
    assert record['metadata']['dataset']['sha256']==hashlib.sha256(workbook.read_bytes()).hexdigest()
    assert 'path' not in record['metadata']['dataset']['import']
    result['excel_export_sheet_header_and_hash']=True
    client.predict('九月订单',1,api_name='/on_read_table')
    assert client.predict(api_name='/on_history_choices')['choices']==[]
    assert '尚未' in client.predict(api_name='/on_reference_status')
    assert not client.predict([],api_name='/on_current_export')['visible']
    result['worksheet_change_resets_previous_analysis_reference_and_export']=True
    for suffix,encoding,sep in [('.tsv','utf-8','\t'),('.csv','gb18030',',')]:
        path=directory/('销售'+suffix)
        path.write_text(f'门店{sep}销售额\n甲店{sep}12\n乙店{sep}18\n',encoding=encoding)
        client.predict(handle_file(str(path)),api_name='/on_upload')
        request(suffix[1:]+'-'+encoding,'销售额的平均值是多少？',lambda a,t:distribution_mean(t,'销售额',15))
    legacy=write_xls(directory/'legacy.xls')
    client.predict(handle_file(str(legacy)),api_name='/on_upload')
    request('xls-mean','What is the average amount?',lambda a,t:distribution_mean(t,'amount',15))
    result['passed']=sum(c['success'] for c in result['cases']);result['total']=len(result['cases']);result['complete']=True;save()
    print('TABLE_IMPORTS',result['passed'],result['total'],flush=True)
    return 0 if result['passed']==result['total'] else 1


if __name__=='__main__': raise SystemExit(main())
