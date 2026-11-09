"""Compare completed live-evaluation reports without running or changing model servers."""
from __future__ import annotations

import argparse
import json
import statistics
import math
from pathlib import Path


def compare(reports: list[dict]) -> list[dict]:
    if len(reports) < 2:
        raise ValueError('Supply at least two reports.')
    canonical = None
    task_digest = None
    max_steps = None
    runtime_limits = None
    summaries = []
    for report in reports:
        tasks = report.get('tasks', [])
        ids = [task['id'] for task in tasks]
        if not report.get('complete') or not tasks or len(set(ids)) != len(ids):
            raise ValueError('Only completed reports with unique task IDs can be compared.')
        prompts = sorted((task['id'], task.get('question',''), tuple(task.get('checks',[]))) for task in tasks)
        if canonical is None:
            canonical, task_digest, max_steps = prompts, report.get('tasks_sha256'), report.get('max_steps')
            runtime_limits = report.get('runtime_limits')
        if prompts != canonical or report.get('tasks_sha256') != task_digest or report.get('max_steps') != max_steps:
            raise ValueError('Reports must use identical task prompts, file digest and tool-round budgets.')
        if report.get('runtime_limits') != runtime_limits:
            raise ValueError('Context/output budgets differ; report these as separate configuration trials.')
        times = [float(task['seconds']) for task in tasks]
        if any(not math.isfinite(value) or value < 0 for value in times):
            raise ValueError('Task times must be finite and nonnegative.')
        summaries.append({'model':report.get('model'), 'passed':sum(task['success'] is True for task in tasks),
                          'total':len(tasks), 'median_seconds':round(statistics.median(times),3),
                          'mean_seconds':round(statistics.mean(times),3),
                          'error_observations':sum(task.get('error_observations',0) for task in tasks),
                          'request_options':report.get('request_options',{}), 'runtime_limits':report.get('runtime_limits'),
                          'failures':[task['id'] for task in tasks if task['success'] is not True]})
    return summaries


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reports',type=Path,nargs='+')
    args=parser.parse_args()
    try:
        print(json.dumps(compare([json.loads(path.read_text(encoding='utf-8')) for path in args.reports]),ensure_ascii=False,indent=2))
    except (ValueError,KeyError,TypeError,OSError) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    main()
