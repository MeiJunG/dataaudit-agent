"""Live sequential follow-ups, history restore/branch, fresh context and session isolation."""
from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

from gradio_client import Client


def chart(trace):
    return next((e['structured_result'] for e in reversed(trace) if e['tool']=='create_chart' and e['status']=='ok'), {})


def close_values(data, expected):
    actual = {p['x']:p['y'] for p in data}
    return set(actual)==set(expected) and all(math.isclose(actual[k],v,rel_tol=1e-8) for k,v in expected.items())


def completed(answer):
    return bool(answer.strip()) and not any(s in answer for s in [
        'tool-call limit', 'model repeated a tool call', '回答未完成', '没有取得可用的工具结果', '最后一轮检查没有成功'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:7860')
    parser.add_argument('--output', type=Path, default=Path('results/session-web.json'))
    args = parser.parse_args()
    client = Client(args.url, verbose=False)
    record = {'complete':False, 'cases':[], 'scope':'Synthetic development requests; server callbacks, not browser rendering'}
    def checkpoint():
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n', encoding='utf-8')
    def submit(question):
        answer, trace, download = client.predict(question, api_name='/on_submit')
        return answer, trace, download
    cases = [
        ('bar-zh','按 region 分组，用 amount 合计画柱状图。','改成平均值，其他不变。','bar','region', 'mean',None, {'East':120,'North':270,'West':160/3}),
        ('bar-en','Draw a bar chart of total amount by department.','Keep the same fields and chart, but use the average instead.','bar','department','mean',None, {'Sales':120,'Operations':270,'Support':160/3}),
        ('line-zh','按 order_date 每天汇总 amount 合计，画折线图。','改成按月，其他不变。','line','order_date','sum','month',{'2026-10-01':760}),
        ('line-en','Draw a daily line chart of total amount by order_date.','Make it monthly instead, keeping the metric and sum.','line','order_date','sum','month',{'2026-10-01':760}),
    ]
    for name, initial, followup, kind, x, method, frequency, expected in cases:
        client.predict(api_name='/on_office_example')
        start = time.perf_counter()
        first_answer, first_trace, _ = submit(initial)
        answer, trace, _ = submit(followup)
        spec = chart(trace)
        success = (bool(chart(first_trace)) and completed(first_answer) and completed(answer)
                   and spec.get('chart_type')==kind and spec.get('x')==x
                   and spec.get('y')=='amount' and spec.get('method')==method
                   and spec.get('frequency')==frequency and close_values(spec.get('data',[]),expected))
        result = {'id':name, 'initial':initial, 'followup':followup, 'success':success,
                  'seconds':round(time.perf_counter()-start,3), 'initial_answer':first_answer,
                  'answer':answer,'initial_trace':first_trace,'trace':trace}
        record['cases'].append(result)
        checkpoint()
        print(f'{name}: {success}',flush=True)

    # Reopening an old result sets the follow-up parent. No model call is involved in restore.
    client.predict(api_name='/on_office_example')
    old_answer, old_trace, _ = submit('按 region 分组，用 amount 合计画柱状图。')
    choices = client.predict(api_name='/on_history_choices')['choices']
    old_id = choices[0][1]
    submit('按 department 分组，用 amount 合计画柱状图。')
    client.predict(api_name='/on_history_choices')
    restored = client.predict(old_id,api_name='/on_restore_analysis')
    assert restored[1] == old_answer and restored[2] == old_trace
    answer, trace, _ = submit('改成平均值，其他不变。')
    spec = chart(trace)
    branched = completed(answer) and spec.get('x')=='region' and spec.get('method')=='mean' and close_values(spec.get('data',[]),{'East':120,'North':270,'West':160/3})
    record['restore_and_branch'] = {'success':branched,'trace':trace,'answer':answer}
    checkpoint()
    assert branched

    archived = client.predict(api_name='/on_history_choices')['choices']
    fresh = client.predict(api_name='/on_new_question')
    assert fresh[:3] == ('','',[]) and fresh[3]['value'] is None
    assert client.predict(api_name='/on_history_choices')['choices'] == archived
    record['fresh_keeps_archive'] = True
    client.predict(api_name='/on_consistency_example')
    assert client.predict(api_name='/on_history_choices')['choices'] == []
    record['dataset_reset'] = True
    # A second client receives its own empty server-side history.
    second = Client(args.url,verbose=False)
    assert second.predict(api_name='/on_history_choices')['choices'] == []
    record['separate_session_empty'] = True
    client.predict(api_name='/on_clear')
    assert client.predict(api_name='/on_history_choices')['choices'] == []
    record['clear_reset'] = True
    record['complete'] = True
    record['passed'] = sum(c['success'] for c in record['cases']) + int(branched)
    record['total'] = len(record['cases'])+1
    checkpoint()
    print(f'SESSION_WEB {record["passed"]}/{record["total"]}',flush=True)
    return 0 if record['passed']==record['total'] else 1


if __name__=='__main__':
    raise SystemExit(main())
