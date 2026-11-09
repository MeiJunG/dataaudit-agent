"""Export the table calculations of one analysis as a standalone pandas script.

Only the three calculation tools (query_rows, aggregate_rows, calculate_row_metric) are exported;
every other step is listed in a comment. The script re-reads the original file, so numbers can be
checked outside this application. It mirrors the tool semantics (numeric coercion, missing/invalid
handling) but not every import heuristic, so a differently formatted file may read differently.
Every value taken from the analysis is written with repr(), never pasted as raw text.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

EXPORTED = {'query_rows', 'aggregate_rows', 'calculate_row_metric'}

PRELUDE = '''import numpy as np
import pandas as pd

RESULTS = []  # (label, value) pairs, also printed below


def load(sheet=None, header_row=1):
    if str(SOURCE).lower().endswith(('.csv', '.tsv', '.txt')):
        return pd.read_csv(SOURCE, sep=None, engine='python', encoding='utf-8-sig', header=header_row - 1)
    return pd.read_excel(SOURCE, sheet_name=sheet if sheet is not None else 0, header=header_row - 1)


def num(series):
    return pd.to_numeric(series, errors='coerce').astype(float).replace([np.inf, -np.inf], np.nan)


def stat(values, method):
    values = values.dropna()  # an all-missing group has no result, like the tool (not 0)
    return float(getattr(values, method)()) if len(values) else None


def select(df, conditions, match='all'):
    masks = []
    for c in conditions:
        s, op, v = df[c['column']], c['operator'], c.get('value')
        if op == 'is_null':
            m = s.isna()
        elif op == 'not_null':
            m = s.notna()
        elif op == 'contains':
            m = s.astype('string').str.contains(str(v), regex=False, na=False)
        elif op in ('gt', 'ge', 'lt', 'le') or (op in ('eq', 'ne') and pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s)):
            n = num(s)
            m = n.notna() & getattr(n, op)(float(v))
        elif pd.api.types.is_bool_dtype(s):
            m = s.notna() & getattr(s, op)(v)
        else:
            m = s.notna() & getattr(s.astype('string'), op)(str(v))
        masks.append(m.fillna(False))
    if not masks:
        return pd.Series(True, index=df.index)
    out = masks[0]
    for m in masks[1:]:
        out = (out & m) if match == 'all' else (out | m)
    return out


def show(label, value):
    RESULTS.append((label, value))
    print(f'--- {label}')
    print(value)
'''


def _origin(entry):
    x = entry.get('structured_result') or {}
    o = x.get('origin') or {}
    return o.get('sheet'), o.get('header_row') or 1


def _step_code(entry, number):
    x = entry.get('structured_result') or {}
    args = entry.get('arguments') or {}
    sheet, header = _origin(entry)
    conds = [dict(c) for c in (args.get('conditions') or [])]
    match = args.get('match', 'all')
    lines = [f'# Step {entry.get("step", number)}: {entry["tool"]}', f'df = load({sheet!r}, {header!r})',
             f'mask = select(df, {conds!r}, {match!r})', 'work = df.loc[mask]']
    label = f'step {entry.get("step", number)} {entry["tool"]}'
    if entry['tool'] == 'query_rows':
        cols, sort_by = x.get('columns') or args.get('columns') or [], x.get('sort_by')
        lines.append(f'out = work[{list(cols)!r}]')
        if sort_by:
            lines.append(f'out = df.loc[mask].sort_values({sort_by!r}, ascending={bool(x.get("ascending", True))!r}, kind="stable", na_position="last")[{list(cols)!r}]')
        lines.append(f'show({label!r}, out.head({int(args.get("limit", 5))}))')
    elif entry['tool'] == 'aggregate_rows':
        metric, col, groups = args['metric'], args.get('value_column'), list(x.get('group_by') or args.get('group_by') or [])
        if metric == 'count':
            lines.append(f'result = work.groupby({groups!r}, dropna=False, sort=False).size() if {groups!r} else len(work)')
        else:
            lines.append(f'vals = num(work[{col!r}])')
            lines.append(f'result = vals.groupby([work[c] for c in {groups!r}], dropna=False, sort=False).agg(lambda s: stat(s, {metric!r})) if {groups!r} else stat(vals, {metric!r})')
        lines.append(f'show({label!r}, result)')
    else:  # calculate_row_metric
        cols, op = list(x.get('columns') or args.get('columns') or []), args['operation']
        weights, groups = args.get('weights'), list(x.get('group_by') or args.get('group_by') or [])
        agg = args.get('aggregation', 'mean')
        lines += [f'nums = work[{cols!r}].apply(num)', 'valid = nums.notna().all(axis=1)']
        expr = {'sum': 'nums.sum(axis=1, skipna=False)', 'mean': 'nums.mean(axis=1, skipna=False)', 'product': 'nums.prod(axis=1, skipna=False)',
                'difference': 'nums.iloc[:, 0] - nums.iloc[:, 1]', 'ratio': 'nums.iloc[:, 0] / nums.iloc[:, 1]',
                'weighted_sum': f'nums.mul({weights!r}, axis=1).sum(axis=1, skipna=False)',
                'weighted_mean': f'nums.mul({weights!r}, axis=1).sum(axis=1, skipna=False) / {sum(weights or [0])!r}'}[op]
        lines += ['with np.errstate(all="ignore"):', f'    values = {expr}']
        if op == 'ratio':
            lines.append('valid &= nums.iloc[:, 1] != 0')
        lines.append('values = values.where(valid & np.isfinite(values))')
        lines.append(f'show({label + " (summary)"!r}, pd.Series({{m: stat(values, m) for m in ["sum", "mean", "min", "max"]}}))')
        if groups:
            lines.append(f'show({label + " (by group)"!r}, values.groupby([work[c] for c in {groups!r}], dropna=False, sort=False).agg(lambda s: stat(s, {agg!r})))')
    return '\n'.join(lines)


def build_script(trace, filename='your_table.xlsx'):
    """Python source for the exported steps, or None when the analysis has none."""
    steps = [e for e in trace or [] if e.get('status') == 'ok' and e.get('tool') in EXPORTED and (e.get('structured_result') or {}).get('kind')]
    if not steps:
        return None
    skipped = [f'#   step {e.get("step")}: {e.get("tool")}' for e in trace if e not in steps]
    head = ['"""Reproduces the table calculations of one DataAudit analysis.', '',
            'Edit SOURCE if the file moved. Only row queries, aggregations and per-row metrics are exported;',
            'checks, charts and reports are not. Hidden-column masking and 120-character cell caps are not applied here."""', '',
            f'SOURCE = {filename!r}  # path to the original file']
    if skipped:
        head += ['', '# Not exported (no script form):'] + skipped
    return '\n'.join(head) + '\n\n' + PRELUDE + '\n\n' + '\n\n'.join(_step_code(e, i) for i, e in enumerate(steps, 1)) + '\n'


def save_script(trace, directory, filename='your_table.xlsx'):
    source = build_script(trace, filename)
    if source is None:
        return None
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / ('reproduce-' + hashlib.sha256(source.encode('utf-8')).hexdigest()[:24] + '.py')
    if not path.exists():
        path.write_text(source, encoding='utf-8')
    return path
