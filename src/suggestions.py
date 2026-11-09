"""Generic, schema-driven starting questions and a per-column overview.

Questions are built only from detected column *types* (numeric / category / date-like); there are no
business templates and no model calls. Sensitive-looking column names are left out.
"""
from __future__ import annotations

import warnings
from html import escape

import pandas as pd

from .tools import is_sensitive_column

from .i18n import tr

MAX_SUGGESTIONS = 5


def _numeric(series):
    if pd.api.types.is_bool_dtype(series):
        return False
    if pd.api.types.is_numeric_dtype(series):
        return True
    values = series.dropna()
    return len(values) > 0 and pd.to_numeric(values, errors='coerce').notna().all()


def _datelike(series):
    if pd.api.types.is_datetime64_any_dtype(series):
        return True
    if _numeric(series) or pd.api.types.is_bool_dtype(series):
        return False
    sample = series.dropna().astype(str).head(40)
    if len(sample) < 3:
        return False
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        return pd.to_datetime(sample, errors='coerce').notna().mean() >= 0.9


def column_kinds(frame):
    kinds = {}
    for column in frame.columns:
        series = frame[column]
        if is_sensitive_column(column):
            kinds[column] = 'sensitive'
        elif _datelike(series):
            kinds[column] = 'date'
        elif _numeric(series):
            kinds[column] = 'number'
        elif 2 <= series.nunique(dropna=True) <= min(20, max(2, len(series) // 2)):
            kinds[column] = 'category'
        else:
            kinds[column] = 'text'
    return kinds


def suggest_questions(frame):
    if frame is None or frame.empty or len(frame.columns) == 0:
        return []
    kinds = column_kinds(frame)
    pick = lambda kind: [str(c) for c, k in kinds.items() if k == kind]
    numbers, categories, dates = pick('number'), pick('category'), pick('date')
    questions = []
    if categories and numbers:
        questions.append(tr('按 {cat} 分组，用 {num} 合计画柱状图。', cat=categories[0], num=numbers[0]))
    if dates and numbers:
        questions.append(tr('按月汇总 {num} 的合计，画折线图。', num=numbers[0]))
    if numbers:
        questions.append(tr('{num} 的平均值、最大值和最小值分别是多少？', num=numbers[0]))
        questions.append(tr('{num} 有没有明显偏离其他值的记录？', num=numbers[0]))
    if categories:
        questions.append(tr('统计 {cat} 每种取值的记录数。', cat=categories[0]))
    questions.append(tr('哪些列有空值？请统计数量和比例。'))
    seen, unique = set(), []
    for q in questions:
        if q not in seen:
            seen.add(q)
            unique.append(q)
    return unique[:MAX_SUGGESTIONS]


KIND_LABEL = {'number': '数值', 'category': '类别', 'date': '日期', 'text': '文字', 'sensitive': '已隐藏'}


def profile_html(frame, limit=30):
    if frame is None or len(frame.columns) == 0:
        return '<div class="preview-empty">' + tr('上传表格后，这里会列出每一列的类型、空值和取值范围。') + '</div>'
    kinds = column_kinds(frame)
    rows = []
    for column in list(frame.columns)[:limit]:
        series, kind = frame[column], kinds[column]
        missing = int(series.isna().sum())
        unique = int(series.nunique(dropna=True))
        if kind == 'sensitive':
            detail = tr('按列名隐藏')
        elif kind == 'number':
            nums = pd.to_numeric(series, errors='coerce').dropna()
            detail = f'{nums.min():.6g} ~ {nums.max():.6g}' if len(nums) else '—'
        elif kind == 'category':
            top = series.value_counts().head(3)
            detail = tr('、').join(tr('{v}（{n}）', v=v, n=n) for v, n in top.items())
        else:
            detail = '—'
        rows.append(f'<tr><td>{escape(str(column))}</td><td>{tr(KIND_LABEL[kind])}</td>'
                    f'<td>{missing}</td><td>{unique}</td><td>{escape(detail[:60])}</td></tr>')
    more = '<div class="context-hint">' + tr('只显示前 {n} 列。', n=limit) + '</div>' if len(frame.columns) > limit else ''
    head = ''.join('<th>' + tr(h) + '</th>' for h in ['列名', '类型', '空值', '不同取值', '范围 / 常见取值'])
    return ('<div class="preview-scroll"><table class="preview-table"><thead><tr>' + head + '</tr></thead><tbody>'
            + ''.join(rows) + '</tbody></table></div>' + more
            + '<div class="context-hint">' + tr('类型由取值推断，仅用于概览和推荐提问；不会作为分析规则保存。') + '</div>')
