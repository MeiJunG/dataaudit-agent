"""Opt-in live checks of the rule sample, tool selection, and displayed results."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from gradio_client import Client

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:7860')
    parser.add_argument('--output', type=Path, default=ROOT / 'results' / 'rules-web.json')
    args = parser.parse_args()
    client = Client(args.url, verbose=False)
    client.predict(api_name='/on_rule_example')
    cases = [
        ('status 只允许 completed、pending、cancelled，区分大小写。检查列表外的值。', 'validate_categories', ['列表外 2 个']),
        ('检查 order_id 能否作为主键，同时检查缺失和重复键。', 'check_key_uniqueness', ['重复键涉及 2 行', '键有缺失 1 行']),
        ('只保留 status 等于 completed 的记录，区分大小写，计算 amount 总额，缺失单独统计。', 'filter_and_aggregate', ['符合条件 4 行', '330', '指标缺失 1 个']),
    ]
    results = []
    for question, tool, expected in cases:
        answer, trace, _ = client.predict(question, api_name='/on_submit')
        success = all(text in answer for text in expected) and any(entry['tool'] == tool and entry['status'] == 'ok' for entry in trace)
        results.append({'tool': tool, 'success': success, 'answer': answer})
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(results[-1], ensure_ascii=False), flush=True)
    answer, trace, download = client.predict('生成一份检查报告。', api_name='/on_submit')
    path = download.get('value') if isinstance(download, dict) else download
    if isinstance(path, dict):
        path = path.get('path')
    report = Path(path).read_text(encoding='utf-8') if path else ''
    expected_report = next((entry.get('report_markdown') for entry in trace if entry['tool'] == 'generate_quality_report' and entry['status'] == 'ok'), None)
    results.append({'tool':'generate_quality_report','success':bool(report and report == expected_report), 'download_characters':len(report)})
    args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(results[-1], ensure_ascii=False), flush=True)
    return 0 if all(result['success'] for result in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
