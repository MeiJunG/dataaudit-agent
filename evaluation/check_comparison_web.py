"""Live reference comparisons, computed chart values, provenance export and resets."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
import re
from urllib.parse import urljoin
from urllib.request import urlopen
from pathlib import Path

from gradio_client import Client, handle_file

ROOT = Path(__file__).resolve().parents[1]


def completed(answer):
    return bool(answer.strip()) and not any(s in answer for s in [
        'tool-call limit','model repeated a tool call','回答未完成','没有取得可用的工具结果','最后一轮检查没有成功','这次没有算完'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',default='http://127.0.0.1:7860')
    parser.add_argument('--output',type=Path,default=Path('results/comparison-web.json'))
    args=parser.parse_args()
    client=Client(args.url,verbose=False)
    client.predict(api_name='/on_office_example')
    # Exercise the real reference upload pipeline, rather than only its example callback.
    client.predict(handle_file(str(ROOT/'examples'/'office_reference.csv')),api_name='/on_reference_upload')
    assert '6 行' in client.predict(api_name='/on_reference_status')
    record={'complete':False,'cases':[],'reference_upload':True,
            'scope':'Synthetic development cases; live Gradio callbacks, separate browser checks required'}
    def checkpoint():
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n', encoding='utf-8')
    cases=[('all-zh','对照当前表和参考表，检查字段、缺失率和分布变化。',None),
           ('amount-en','Compare only amount with the reference: missing rate and mean.','amount'),
           ('region-followup-zh','这次只对照 region 的类别比例。','region'),
           ('schema-en','Compare the schema of the current and reference CSV files.',None)]
    for name,question,focus in cases:
        start=time.perf_counter()
        answer,trace,_=client.predict(question,api_name='/on_submit')
        result=next((e['structured_result'] for e in reversed(trace) if e['tool']=='compare_datasets' and e['status']=='ok'),{})
        fields={v['column']:v for v in result.get('columns',[])}
        valid=(completed(answer) and result.get('current',{}).get('rows')==9 and result.get('reference',{}).get('rows')==6
               and result.get('schema',{}).get('added')==['quantity'] and result.get('schema',{}).get('removed')==['legacy_note'])
        if focus:
            valid=valid and set(fields)=={focus}
        if 'amount' in fields:
            valid=valid and fields['amount']['missing']['current']==1 and fields['amount']['numeric']['current_mean']==132.5 and fields['amount']['numeric']['reference_mean']==100
        if focus=='region' and 'region' in fields:
            valid=valid and math.isclose(fields['region']['categorical']['tvd'],1/9,rel_tol=1e-8) and 'TVD' in answer
        item={'id':name,'question':question,'success':bool(valid),'seconds':round(time.perf_counter()-start,3),
              'answer':answer,'trace':trace}
        record['cases'].append(item)
        checkpoint()
        print(f'{name}: {valid}',flush=True)
    assert all(c['success'] for c in record['cases'])
    final=record['cases'][-1]
    plot,download=client.predict(final['trace'],api_name='/on_agent_chart')
    assert len(json.loads(plot['plot'])['data'])==2 and download['visible']
    exported=client.predict(final['trace'],api_name='/on_current_export')
    href=re.search(r'href="([^"]+)"',exported['value']).group(1)
    with urlopen(urljoin(args.url,href),timeout=30) as response:
        downloaded=response.read().decode('utf-8')
    payload=json.loads(downloaded)
    assert payload['question']==final['question']
    assert payload['metadata']['dataset']['sha256']==hashlib.sha256((ROOT/'examples'/'office_orders.csv').read_bytes()).hexdigest()
    assert payload['metadata']['reference']['sha256']==hashlib.sha256((ROOT/'examples'/'office_reference.csv').read_bytes()).hexdigest()
    assert 'OPENAI_API_KEY' not in downloaded
    assert not client.predict([],api_name='/on_current_export')['visible']
    record['json_export_exact_question_and_hashes']=True
    current_answer,current_trace,_=client.predict('Only analyze the current CSV: draw a histogram of amount.',api_name='/on_submit')
    current_chart=next((e.get('structured_result',{}) for e in current_trace if e['tool']=='create_chart' and e['status']=='ok'),{})
    current_ok=(completed(current_answer) and current_chart.get('chart_type')=='histogram'
                and current_chart.get('plotted_rows')==8 and current_trace[0].get('routing',{}).get('scope')=='current_table')
    record['current_only_with_reference']={'success':current_ok,'answer':current_answer,'trace':current_trace}
    checkpoint()
    assert current_ok
    print('current-only-with-reference: True',flush=True)
    client.predict(api_name='/on_reference_clear')
    assert '尚未' in client.predict(api_name='/on_reference_status')
    assert client.predict(api_name='/on_history_choices')['choices']==[]
    assert not client.predict([],api_name='/on_current_export')['visible']
    record['reference_clear_resets_history_and_export']=True
    client.predict(api_name='/on_reference_example')
    client.predict(api_name='/on_office_example')
    assert '尚未' in client.predict(api_name='/on_reference_status')
    record['current_dataset_switch_resets_reference']=True
    record['complete']=True
    record['passed']=sum(c['success'] for c in record['cases']) + int(current_ok)
    record['total']=len(cases)+1
    checkpoint()
    print('COMPARISON_WEB_OK',flush=True)


if __name__=='__main__':
    main()
