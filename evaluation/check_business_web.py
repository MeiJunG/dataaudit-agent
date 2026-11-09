"""Opt-in real upload and answer checks; requires running web and model services."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from gradio_client import Client, handle_file

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:7860')
    parser.add_argument('--output', type=Path, default=ROOT / 'results' / 'business-web.json')
    args = parser.parse_args()
    client = Client(args.url, verbose=False)
    client.predict(handle_file(str(ROOT / 'examples' / 'reconciliation.csv')), api_name='/on_upload')
    cases = [
        ('检查 amount 是否在闭区间 0 到 250 内，缺失单独统计。', 'check_numeric_range',
         ['低于下限 1 个，高于上限 2 个，共 3 个超限', '缺失 1 个']),
        ('逐行核对 amount 和 recorded_amount，允许绝对误差 0.01，缺失单独统计。', 'compare_columns',
         ['一致 5 行，不一致 1 行', '单边缺失 1 行，双边缺失 1 行']),
        ('按 order_date 的自然月汇总 amount 总额，无效日期单独统计。', 'summarize_time_series',
         ['670', '无效日期 1 行', '指标缺失或无效 1 行']),
    ]
    results = []
    for question, tool, phrases in cases:
        answer, trace, _ = client.predict(question, api_name='/on_submit')
        success = all(phrase in answer for phrase in phrases) and any(
            entry['tool'] == tool and entry['status'] == 'ok' for entry in trace)
        results.append({'tool': tool, 'success': success, 'answer': answer})
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(results[-1], ensure_ascii=False), flush=True)
    return 0 if all(result['success'] for result in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
