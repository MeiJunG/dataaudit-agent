"""Exercise new consistency tools and preview/trace callbacks against a running Gradio app."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from gradio_client import Client

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',default='http://127.0.0.1:7860')
    parser.add_argument('--output',type=Path,default=ROOT/'results'/'consistency-web.json')
    args=parser.parse_args()
    client=Client(args.url,verbose=False)
    client.predict(api_name='/on_consistency_example')
    cases=[
        ('检查 status 的首尾空格和大小写混用。','check_text_quality',['文字格式检查','status']),
        ('status 等于 completed 时，amount 和 recorded_amount 必填。检查缺失情况。','check_required_if',['符合条件 3 行','2 行存在必填项缺失']),
        ('核对 order_date 不能晚于 ship_date，允许相同日期。','check_date_order',['比较 4 行','共 1 行不符合规则']),
    ]
    results=[]
    for question,tool,phrases in cases:
        answer,trace,_=client.predict(question,api_name='/on_submit')
        success=any(entry['tool']==tool and entry['status']=='ok' for entry in trace) and all(phrase in answer for phrase in phrases)
        execution=client.predict(trace,api_name='/execution_html')
        success=success and '完成' in execution
        results.append({'tool':tool,'success':success,'answer':answer,'execution_summary':execution})
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(results[-1],ensure_ascii=False),flush=True)
    # Explicit event endpoint exercises the actual state-to-preview callback.
    preview=client.predict(api_name='/on_preview')
    assert '已隐藏' in preview and '<table' in preview and 'A001' not in preview
    cleared=client.predict(api_name='/on_clear')
    assert cleared[-3]=='' and cleared[-2]==[] and cleared[-1]['value'] is None
    preview=client.predict(api_name='/on_preview')
    assert '上传表格后' in preview
    print('PREVIEW_AND_CLEAR_OK',flush=True)
    return 0 if all(result['success'] for result in results) else 1


if __name__=='__main__':
    raise SystemExit(main())
