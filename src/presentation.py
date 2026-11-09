"""Dependency-free HTML presentation for dataset previews and tool execution summaries."""
from __future__ import annotations

from html import escape
import math
from typing import Any, Sequence

from .i18n import tr

TOOL_LABELS = {
    'list_workbook_sheets':'列出工作表','inspect_sheet_layout':'查看表头位置',
    'query_rows':'按条件查行','aggregate_rows':'多字段汇总','calculate_row_metric':'逐行计算',
    'inspect_schema': '查看表格结构', 'check_missing_values': '检查空值',
    'detect_outliers': '检查偏离值', 'check_duplicates': '检查重复',
    'analyze_distribution': '统计数值和类别', 'validate_data_types': '检查字段类型',
    'check_correlations': '计算相关性', 'compare_groups': '分组统计',
    'inspect_date_column': '检查日期', 'generate_quality_report': '整理报告',
    'check_numeric_range': '检查数值范围', 'compare_columns': '核对两列',
    'summarize_time_series': '按时间汇总', 'validate_categories': '检查类别取值',
    'check_key_uniqueness': '检查主键', 'filter_and_aggregate': '筛选后统计',
    'check_text_quality': '检查文字格式', 'check_required_if': '检查条件必填',
    'check_date_order': '核对日期先后',
    'create_chart': '生成图表',
    'compare_datasets': '对照两份表',
}


def execution_html(trace: list[dict[str, Any]] | None) -> str:
    if not trace:
        return '<div class="execution-empty">' + tr('计算完成后，可以在这里查看用到的工具。') + '</div>'
    rows = []
    for index, entry in enumerate(trace[:50], start=1):
        name = str(entry.get('tool', ''))
        label = escape(tr(TOOL_LABELS[name]) if name in TOOL_LABELS else name)
        ok = entry.get('status') == 'ok'
        badge = tr('完成') if ok else tr('未完成')
        css = 'ok' if ok else 'error'
        elapsed = entry.get('duration_ms')
        duration = f'{elapsed:.0f} ms' if isinstance(elapsed, (int, float)) and elapsed >= 0 else '—'
        rows.append(f'<div class="execution-row"><span class="execution-index">{index:02d}</span>'
                    f'<span class="execution-label">{label}</span><span class="execution-time">{duration}</span>'
                    f'<span class="execution-badge {css}">{badge}</span></div>')
    durations = [e.get('duration_ms') for e in trace]
    elapsed = sum(v for v in durations if isinstance(v, (float, int)) and math.isfinite(v) and v >= 0)
    errors = sum(e.get('status') != 'ok' for e in trace)
    note = ' · ' + tr('{n} 次未完成', n=errors) if errors else ''
    summary = ('<summary><span>' + tr('计算过程') + '</span><span class="execution-meta">' + tr('{n} 次调用', n=len(trace))
               + ' · ' + tr('工具用时 {ms} ms', ms=f'{elapsed:.0f}') + note + '</span></summary>')
    more = '<div class="context-hint">' + tr('这里只列出前 50 次调用。') + '</div>' if len(trace) > 50 else ''
    grounding = next((e['grounding'] for e in trace if isinstance(e.get('grounding'), dict)), None)
    if grounding:
        bad = grounding.get('unverified') or []
        if bad:
            more += ('<div class="grounding warn">' + tr('数字核对：回答里有 {n} 个数字没有在工具结果中找到（{values}）。请以计算过程里的结果为准。',
                                                         n=len(bad), values=escape(tr('、').join(map(str, bad[:5])))) + '</div>')
        else:
            more += '<div class="grounding ok">' + tr('数字核对：回答里的 {n} 个数字都能在工具结果中找到。', n=grounding.get("checked", 0)) + '</div>'
    return '<details class="execution-list">' + summary + ''.join(rows) + more + '</details>'


def preview_html(columns: Sequence[str], rows: Sequence[Sequence[Any]], *, hidden: set[str] | None = None) -> str:
    columns = list(columns)[:8]
    if not columns:
        return '<div class="preview-empty">' + tr('上传表格后可以查看前 5 行。') + '</div>'
    hidden = hidden or set()
    header = ''.join(f'<th>{escape(str(column))}</th>' for column in columns)
    body = []
    for row in list(rows)[:5]:
        cells = []
        for index, column in enumerate(columns):
            value = row[index] if index < len(row) else None
            if str(column) in hidden:
                text = tr('已隐藏')
                css = 'redacted'
            elif value is None:
                text = tr('空值')
                css = 'missing'
            else:
                text = str(value)
                text = text[:77] + '…' if len(text) > 80 else text
                css = ''
            cells.append(f'<td class="{css}">{escape(text)}</td>')
        body.append('<tr>' + ''.join(cells) + '</tr>')
    if not body:
        body.append(f'<tr><td colspan="{len(columns)}">' + tr('这份表只有表头，还没有数据行。') + '</td></tr>')
    return '<div class="preview-scroll"><table class="preview-table"><thead><tr>' + header + '</tr></thead><tbody>' + ''.join(body) + '</tbody></table></div>'
