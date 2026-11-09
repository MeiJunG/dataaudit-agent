"""Render only validated chart-tool observations; never execute model-written code."""
from __future__ import annotations

import hashlib
import json
import math
import re
from html import escape
from pathlib import Path

import plotly.graph_objects as go
from .chart_limits import MAX_CATEGORY_GROUPS, MAX_LINE_PERIODS

from .i18n import tr


def chart_spec_from_trace(trace):
    for entry in reversed(trace or []):
        if entry.get('tool') != 'create_chart' or entry.get('status') != 'ok':
            continue
        spec = entry.get('structured_result')
        if not isinstance(spec, dict) or spec.get('version') != 1:
            continue
        kind, data = spec.get('chart_type'), spec.get('data')
        if kind not in {'bar', 'line', 'histogram'} or not isinstance(data, list) or not 1 <= len(data) <= (MAX_LINE_PERIODS if kind=='line' else MAX_CATEGORY_GROUPS):
            continue
        if not isinstance(spec.get('x'), str) or not 1 <= len(spec['x']) <= 256:
            continue
        if spec.get('y') is not None and (not isinstance(spec['y'], str) or len(spec['y']) > 256):
            continue
        if spec.get('method') not in {'count', 'sum', 'mean'}:
            continue
        if any(not isinstance(spec.get(k), int) or isinstance(spec.get(k), bool) or spec[k] < 0
               for k in ('rows', 'plotted_rows', 'excluded_x_rows')):
            continue
        if spec['plotted_rows'] + spec['excluded_x_rows'] != spec['rows']:
            continue
        def finite(v):
            return isinstance(v, (float, int)) and not isinstance(v, bool) and math.isfinite(v)
        valid = True
        for row in data:
            if not isinstance(row, dict) or (row.get('y') is not None and not finite(row['y'])):
                valid = False
                break
            if kind == 'histogram':
                valid = all(finite(row.get(k)) for k in ('low', 'high', 'y')) and row['low'] < row['high'] and row['y'] >= 0
            else:
                valid = isinstance(row.get('x'), str) and len(row['x']) <= 256
            if not valid:
                break
        if valid:
            return spec
    return None


def chart_figure(spec):
    kind, data = spec['chart_type'], spec['data']
    xlabel = escape(spec['x'])
    metric = escape(spec.get('y') or '')
    ylabel = {'count': tr('记录数'), 'sum': f'{metric} · ' + tr('合计'), 'mean': f'{metric} · ' + tr('平均')}[spec['method']]
    if kind == 'histogram':
        figure = go.Figure(go.Bar(x=[(p['low'] + p['high']) / 2 for p in data], y=[p['y'] for p in data],
                                 width=[p['high'] - p['low'] for p in data], marker_color='#0071e3',
                                 customdata=[[p['low'], p['high']] for p in data],
                                 hovertemplate=tr('区间') + ': %{customdata[0]:.5g}–%{customdata[1]:.5g}<br>' + tr('记录数') + ': %{y}<extra></extra>'))
    elif kind == 'line':
        figure = go.Figure(go.Scatter(x=[escape(p['x']) for p in data], y=[p['y'] for p in data],
                                     mode='lines+markers', connectgaps=False, line_color='#0071e3',
                                     hovertemplate='%{x}<br>%{y:,.6g}<extra></extra>'))
    else:
        figure = go.Figure(go.Bar(x=[escape(p['x']) for p in data], y=[p['y'] for p in data],
                                 marker_color='#0071e3', hovertemplate='%{x}<br>%{y:,.6g}<extra></extra>'))
        figure.update_xaxes(type='category')
    figure.update_layout(template='plotly_white', height=330, showlegend=False, bargap=.15,
                         paper_bgcolor='white', plot_bgcolor='white',
                         margin={'l': 20, 'r': 15, 't': 20, 'b': 60}, xaxis_title=xlabel, yaxis_title=ylabel,
                         font={'family': 'system-ui, PingFang SC, sans-serif', 'color': '#718098', 'size': 11})
    figure.update_xaxes(gridcolor='#f0f0f3')
    figure.update_yaxes(gridcolor='#f0f0f3', rangemode='tozero' if kind != 'line' else 'normal')
    return figure


def save_chart(spec, directory):
    """Content-addressed export: repeated display callbacks reuse a server-side file."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(json.dumps(spec, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    path = directory / f'chart-{digest}.html'
    if not path.exists():
        figure = chart_figure(spec)
        # Inline plotly.js makes the exported chart work offline; no CDN dependency.
        note = (f'<p>Rows with valid x: {spec["plotted_rows"]}; excluded x: {spec["excluded_x_rows"]}; '
                f'excluded metric: {spec.get("excluded_metric_rows", 0)}. '
                f'{escape(str(spec.get("note", "")))}</p>')
        figure.write_html(path, include_plotlyjs=True, full_html=True,
                          post_script=None, config={'displaylogo': False})
        html = path.read_text(encoding='utf-8')
        path.write_text(html.replace('</body>', note + '</body>'), encoding='utf-8')
    return path


def render_chart_answer(trace, question):
    spec = chart_spec_from_trace(trace)
    if spec is None:
        return None
    for entry in trace:
        if entry.get('status') != 'ok' or entry.get('tool') in {'create_chart', 'inspect_schema'}:
            continue
        # A matching time aggregate is supporting evidence for the same line chart.
        observed = entry.get('structured_result', {})
        if (entry.get('tool') == 'summarize_time_series' and spec['chart_type'] == 'line'
            and observed.get('date_column') == spec['x'] and observed.get('metric_column') == spec.get('y')
            and observed.get('method') == spec['method'] and observed.get('frequency') == spec.get('frequency')):
            continue
        return None
    chinese = bool(re.search(r'[\u3400-\u9fff]', question))
    excluded_x, excluded_y = spec.get('excluded_x_rows', 0), spec.get('excluded_metric_rows', 0)
    if chinese:
        label = {'bar': '柱状图', 'histogram': '直方图', 'line': '折线图'}[spec['chart_type']]
        return (f'{label}已生成，见左侧「生成的图表」。横轴有效的有 {spec["plotted_rows"]} 行；'
                f'横轴为空或无效的 {excluded_x} 行已排除，数值为空或无效的 {excluded_y} 行未参与计算。'
                '重复行仍计入。可下载 HTML，离线打开和查看各点数值。')
    return (f'Chart created in the chart panel from {spec["plotted_rows"]} rows. '
            f'Excluded x: {excluded_x} rows; excluded metric: {excluded_y} rows. '
            'Duplicates are retained. Download the HTML for offline interactive viewing.')
