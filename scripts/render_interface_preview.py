"""Build a small, offline layout preview from shared CSS and a synthetic fixture."""
from __future__ import annotations

import ast
import csv
import json
import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.check_logic import check_conditional_values
from src.presentation import execution_html, preview_html


def constants():
    tree = ast.parse((ROOT / 'src' / 'interface.py').read_text())
    return {node.targets[0].id: ast.literal_eval(node.value) for node in tree.body
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id in {'APP_CSS', 'HEADER'}}


def main():
    shared = constants()
    with (ROOT / 'examples' / 'consistency_checks.csv').open() as source:
        reader = csv.DictReader(source)
        columns = reader.fieldnames
        rows = list(reader)
    metrics = [str(len(rows)), str(len(columns)), str(sum(value == '' for row in rows for value in row.values())), '0']
    labels = ['行数', '列数', '空白单元格', '重复行']
    strip = '<div class="stat-band">' + ''.join(f'<div class="stat"><div class="stat-label">{label}</div><div class="stat-value">{value}</div><div class="stat-unit">示例数据</div></div>' for label, value in zip(labels, metrics)) + '</div>'
    values = [float(row['amount']) for row in rows if row['amount']]
    top = max(values)
    bars = []
    for index, value in enumerate(values):
        height = value / top * 155
        x = 55 + index * 84
        bars.append(f'<rect x="{x}" y="{220-height}" width="43" height="{height}" rx="3" fill="#7b8bdf"/><text x="{x+21}" y="244" text-anchor="middle" fill="#97a3b5" font-size="11">{index+1}</text><text x="{x+21}" y="{210-height}" text-anchor="middle" fill="#718099" font-size="11">{value:g}</text>')
    chart = '<svg viewBox="0 0 440 275" role="img" aria-label="示例前四条有效金额">' + ''.join(f'<line x1="35" y1="{y}" x2="420" y2="{y}" stroke="#edf0f7"/>' for y in [65,115,165,220]) + ''.join(bars) + '<text x="230" y="268" text-anchor="middle" fill="#a1aabd" font-size="10">有效金额 · 按原表顺序</text></svg>'
    result = check_conditional_values([row['status'] for row in rows], {'amount': [row['amount'] or None for row in rows], 'recorded_amount': [row['recorded_amount'] or None for row in rows]}, 'completed')
    table = preview_html(columns, [[value or None for value in row.values()] for row in rows], hidden={'order_id'})
    trace = execution_html([{'tool':'check_required_if','status':'ok','duration_ms':2.4}])
    page = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>DataAudit · 界面草稿</title><style>
* {{ box-sizing:border-box; }} body {{margin:0;font-family:system-ui,sans-serif;}} .row{{display:flex;gap:18px;}} .column{{display:flex;flex-direction:column;gap:13px;min-width:0;}} button,textarea,select{{font:inherit;}} button{{cursor:default;}} .tab-nav{{display:flex;gap:24px;border-bottom:1px solid #e1e6ef;padding-bottom:12px;color:#8b95a7;font-size:13px;}} .tab-nav .selected{{color:#526be4;}} .data-actions{{margin:18px 0;}} .draft-note{{text-align:center;font-size:10px;color:#9ba6b8;margin-bottom:15px;}} .result-label{{margin-bottom:12px;}} #data-preview{{margin-top:8px;}} #data-preview summary{{font-size:11px;color:#8a98ad;padding:10px 0;cursor:pointer;}}
{shared['APP_CSS']}
</style></head><body><div class="gradio-container"><main>{shared['HEADER']}<div class="draft-note">本地界面草稿 · 示例统计来自实际 CSV · 按钮不连接模型</div><div id="main-tabs"><div class="tab-nav"><span class="selected">工作台</span><span>工具库 · 19</span></div></div>
<div class="row data-actions"><button id="choose-csv">上传 CSV</button><div class="file-status" style="flex:1"><strong>consistency_checks.csv <em>示例</em></strong><span>6 行</span></div><button class="sample-button">订单示例</button><button class="sample-button">格式示例</button></div>{strip}
<div class="row work-grid" style="margin-top:18px"><section class="column chart-card" style="flex:3"><div class="tab-nav"><span class="selected">数值分布</span><span>空值分布</span></div>{chart}<details id="data-preview" open><summary>数据预览 · 前 5 行</summary>{table}</details></section>
<section class="column ask-panel" style="flex:2"><div class="section-heading"><h2>问这份数据</h2></div><div id="question"><textarea aria-label="想查的问题" style="width:100%;resize:none" rows="3">completed 的订单，amount 和 recorded_amount 是否都填写了？</textarea></div><div class="row quick-row"><button class="quick-button">查空值</button><button class="quick-button">查重复</button><button class="quick-button">写报告</button></div><button id="run-check">开始检查</button><div class="result-label">检查结果</div><div id="analysis-answer"><strong>条件必填检查</strong><p>status 等于 completed 的记录中，{result['matched_rows']} 行符合条件，{result['affected_rows']} 行存在必填项缺失。</p><ul><li>amount：缺失 {result['missing_by_column']['amount']} 行。</li><li>recorded_amount：缺失 {result['missing_by_column']['recorded_amount']} 行。</li></ul></div>{trace}<div style="color:#9aa5b7;font-size:11px">参数与原始结果</div></section></div><div class="page-foot"><span>DataAudit / CSV 工作台</span><span>示例数据 · 原表不会被改写</span></div></main></div></body></html>'''
    output = ROOT / 'docs' / 'interface-preview.html'
    output.write_text(page, encoding='utf-8')
    print(output)


if __name__ == '__main__':
    main()
