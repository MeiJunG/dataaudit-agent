"""Turn the latest computed table result into a CSV download (UTF-8 with BOM for Excel)."""
from __future__ import annotations

import csv
import hashlib
import io
from pathlib import Path

from .i18n import tr

CALCULATIONS = {'row_query', 'table_aggregate', 'row_metric'}
MAX_ROWS = 5000


def _safe(value):
    """Neutralise spreadsheet formulas in text cells; numbers stay numbers."""
    if isinstance(value, str) and value[:1] in {'=', '+', '-', '@', '\t', '\r'}:
        return "'" + value
    return '' if value is None else value


def result_table(trace):
    """(headers, rows) of the most recent calculation, or None."""
    for entry in reversed(trace or []):
        x = entry.get('structured_result') or {}
        if entry.get('status') != 'ok' or x.get('kind') not in CALCULATIONS:
            continue
        kind = x['kind']
        if kind == 'row_query':
            cols = x.get('columns', [])
            return ([tr('数据行')] + cols, [[r.get('table_row')] + [r['values'].get(c) for c in cols] for r in x.get('rows', [])])
        if kind == 'table_aggregate':
            if x.get('group_by'):
                g = x['group_by']
                return (g + [tr('结果'), tr('记录数'), tr('缺失'), tr('无效数值')],
                        [[r['keys'].get(c) for c in g] + [r.get('value'), r.get('rows'), r.get('missing_values'), r.get('invalid_values')]
                         for r in x.get('groups', [])])
            s = x.get('summary', {})
            return ([tr('指标'), tr('结果'), tr('有效值'), tr('缺失'), tr('无效数值')],
                    [[x.get('metric'), s.get('value'), s.get('valid_values'), s.get('missing_values'), s.get('invalid_values')]])
        if x.get('group_by'):
            g = x['group_by']
            return (g + [tr('结果'), tr('记录数')], [[r['keys'].get(c) for c in g] + [r.get('value'), r.get('rows')] for r in x.get('groups', [])])
        return ([tr('数据行'), tr('计算结果')], [[r.get('table_row'), r.get('value')] for r in x.get('rows', [])])
    return None


def save_result_csv(trace, directory):
    table = result_table(trace)
    if table is None:
        return None
    headers, rows = table
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator='\n')
    writer.writerow([_safe(h) for h in headers])
    for row in rows[:MAX_ROWS]:
        writer.writerow([_safe(v) for v in row])
    payload = ('﻿' + buffer.getvalue()).encode('utf-8')
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / ('result-' + hashlib.sha256(payload).hexdigest()[:24] + '.csv')
    if not path.exists():
        path.write_bytes(payload)
    return path
