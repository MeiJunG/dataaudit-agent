"""Present comparison observations without model-estimated numbers."""
from __future__ import annotations

import hashlib
import json
import re
from html import escape
from pathlib import Path

import plotly.graph_objects as go

from .i18n import tr


def comparison_from_trace(trace):
    for entry in reversed(trace or []):
        value = entry.get('structured_result')
        if entry.get('tool') == 'compare_datasets' and entry.get('status') == 'ok' and isinstance(value, dict):
            if value.get('kind') == 'dataset_comparison' and value.get('version') == 1 and isinstance(value.get('columns'), list) and len(value['columns']) <= 6:
                return value
    return None


def comparison_figure(value):
    rows = value['columns']
    levels = rows[0].get('categorical',{}).get('levels',[]) if len(rows)==1 else []
    plotted = levels if levels else rows
    figure = go.Figure()
    labels = [escape(str(r['label'] if levels else r['column'])) for r in plotted]
    for key, name, color in [('current_rate','当前表','#6278db'),('reference_rate','参考表','#9caebe')]:
        figure.add_bar(name=tr(name), x=labels,
                       y=[(r[key] if levels else r['missing'][key])*100 if (r[key] if levels else r['missing'][key]) is not None else None for r in plotted],
                       marker_color=color, hovertemplate='%{x}<br>' + tr('占比') + ': %{y:.2f}%<extra>%{fullData.name}</extra>')
    figure.update_layout(template='plotly_white', barmode='group', height=330,
                         paper_bgcolor='white', plot_bgcolor='white', yaxis_title=tr('非空值占比（%）') if levels else tr('缺失率（%）'),
                         legend={'orientation':'h','y':1.16}, margin={'l':20,'r':15,'t':35,'b':60},
                         font={'family':'system-ui, PingFang SC, sans-serif','size':11,'color':'#718098'})
    figure.update_xaxes(type='category', gridcolor='#eef1f7')
    rates = [(r[key] if levels else r['missing'][key]) for r in plotted for key in ('current_rate','reference_rate') if (r[key] if levels else r['missing'][key]) is not None]
    upper = min(100,max(5,max(rates,default=0)*115))
    figure.update_yaxes(range=[0,upper], gridcolor='#eef1f7')
    if not levels and rows and len(rates)==2*len(rows) and max(rates)==0:
        figure.add_annotation(text=tr('所选字段在两份表中均无缺失值'),x=.5,y=.5,xref='paper',yref='paper',showarrow=False)
    if not rows:
        figure.add_annotation(text=tr('两份表没有可比较的共有字段'), x=.5,y=.5,xref='paper',yref='paper',showarrow=False)
    return figure


def save_comparison_chart(value, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    path = directory / f'comparison-{digest}.html'
    if not path.exists():
        comparison_figure(value).write_html(path, include_plotlyjs=True, full_html=True, config={'displaylogo':False})
    return path


def _label(value):
    return escape(str(value)).replace('|', '\\|').replace('`', '&#96;')


def render_comparison_answer(trace, question):
    if {e.get('tool') for e in trace if e.get('status')=='ok'} - {'compare_datasets','inspect_schema'}:
        return None
    value = comparison_from_trace(trace)
    if value is None:
        return None
    chinese = bool(re.search(r'[\u3400-\u9fff]',question))
    a,b,s = value['current'],value['reference'],value['schema']
    percent = lambda x: '—' if x is None else f'{x*100:.1f}%'
    number = lambda x: '—' if x is None else f'{x:.4g}'
    if chinese:
        lines = ['**两表对照**', f'当前表 {a["rows"]} 行 / {a["columns"]} 列；参考表 {b["rows"]} 行 / {b["columns"]} 列。',
                 f'新增 {s["added_count"]} 列，减少 {s["removed_count"]} 列，类型变化 {s["dtype_change_count"]} 列。',
                 '| 字段 | 当前缺失率 | 参考缺失率 | 分布对照 |', '|---|---:|---:|---:|']
    else:
        lines = ['**Dataset comparison**',f'Current: {a["rows"]} rows / {a["columns"]} columns; reference: {b["rows"]} rows / {b["columns"]} columns.',
                 f'Added columns: {s["added_count"]}; removed: {s["removed_count"]}; dtype changes: {s["dtype_change_count"]}.',
                 '| Field | Current missing | Reference missing | Distribution |','|---|---:|---:|---:|']
    for row in value['columns']:
        n = row.get('numeric',{})
        means = (('均值 ' if chinese else 'Mean ')+f'{number(n.get("current_mean"))} / {number(n.get("reference_mean"))}' if n else
                 'TVD '+number(row['categorical'].get('tvd')) if row.get('categorical') else '—')
        lines.append(f'| {_label(row["column"])} | {percent(row["missing"]["current_rate"])} | {percent(row["missing"]["reference_rate"])} | {means} |')
    for key,zh,en in [('added','新增','Added'),('removed','减少','Removed')]:
        if s[key]:
            lines.append(f'{zh if chinese else en}: ' + ', '.join(_label(c) for c in s[key]) + (' …' if s[key+'_count'] > len(s[key]) else ''))
    levels = value['columns'][0].get('categorical',{}).get('levels',[]) if len(value['columns'])==1 else []
    if levels:
        category_lines = ['| 类别 | 当前占比 | 参考占比 |' if chinese else '| Category | Current share | Reference share |','|---|---:|---:|']
        category_lines += [f'| {_label(v["label"])} | {percent(v["current_rate"])} | {percent(v["reference_rate"])} |' for v in levels]
        lines.append('\n'.join(category_lines))
    chart_note = '图表对照非空类别占比（最多 3 项）。' if levels else '图表展示两份表的缺失率。'
    lines.append((f'本次查看 {len(value["columns"])} 个共有字段，还有 {value["unexamined_shared_columns"]} 个未展开。均值按当前 / 参考排列；类别 TVD 越接近 0，非空类别比例越相近。{chart_note}差异需结合采样方式和业务规则判断。'
                  if chinese else f'Examined {len(value["columns"])} shared fields; {value["unexamined_shared_columns"]} others not expanded. The chart compares {"category shares" if levels else "missing rates"}. Differences are descriptive; review sampling and business rules before interpreting them.'))
    table_end = 5 + len(value['columns'])
    return '\n\n'.join(lines[:3])+'\n\n'+'\n'.join(lines[3:table_end])+'\n\n'+'\n\n'.join(lines[table_end:])
