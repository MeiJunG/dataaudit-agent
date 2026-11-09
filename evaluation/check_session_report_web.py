"""Verify report creation after a chart, and restore the exact report after another task."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from gradio_client import Client


def file_path(download):
    value = download['value']
    return Path(value['path'] if isinstance(value, dict) else value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:7860')
    parser.add_argument('--output', type=Path, default=Path('results/session-report-web.json'))
    args = parser.parse_args()
    client = Client(args.url, verbose=False)
    client.predict(api_name='/on_office_example')
    client.predict('按 region 分组，用 amount 合计画柱状图。',api_name='/on_submit')
    answer, trace, download = client.predict('帮我生成完整的数据检查报告。',api_name='/on_submit')
    report = next(e['report_markdown'] for e in trace if e.get('report_markdown'))
    assert file_path(download).read_text(encoding='utf-8') == report
    choices = client.predict(api_name='/on_history_choices')['choices']
    report_id = choices[0][1]
    client.predict('画 amount 的直方图。',api_name='/on_submit')
    client.predict(api_name='/on_history_choices')
    restored = client.predict(report_id,api_name='/on_restore_analysis')
    assert restored[1] == answer and restored[2] == trace
    assert file_path(restored[3]).read_text(encoding='utf-8') == report
    result = {'report_after_chart':True,'exact_report_restored':True,'report_characters':len(report),
              'scope':'Live model calls and report download/restore callbacks; not browser rendering'}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n', encoding='utf-8')
    print('SESSION_REPORT_WEB_OK',flush=True)


if __name__=='__main__':
    main()
