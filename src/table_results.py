"""Display generic tool evidence, including the worksheet actually read."""
from html import escape

from .i18n import tr


def _s(value):
    if value is None: return '—'
    if isinstance(value,float): return f'{value:.8g}'
    return escape(str(value)).replace('|','&#124;').replace('`','&#96;').replace('\n',' ')


def _table(headers,rows):
    return '| '+' | '.join(map(_s,headers))+' |\n| '+' | '.join('---' for _ in headers)+' |\n'+''.join('| '+' | '.join(map(_s,row))+' |\n' for row in rows)


METRIC_NAMES={'count':'记录数','sum':'合计','mean':'均值','median':'中位数','min':'最小值','max':'最大值'}
ROW_OPERATIONS={'sum':'逐行相加','mean':'逐行均值','product':'逐行相乘','difference':'第一列减第二列','ratio':'第一列除以第二列','weighted_sum':'加权求和','weighted_mean':'加权均值'}


def render_table_answer(trace):
    successful=[e for e in trace if e.get('status')=='ok' and e.get('structured_result',{}).get('kind') in {'workbook_sheets','sheet_layout','row_query','table_aggregate','row_metric'}]
    if not successful: return None
    last=max(e.get('step',0) for e in trace)
    if any(e.get('status')=='error' for e in trace if e.get('step')==last): return None
    calculations=[e for e in successful if e['structured_result']['kind'] in {'row_query','table_aggregate','row_metric'}]
    selected=(calculations or successful)[-6:];sections=[]
    for entry in selected:
        x=entry['structured_result'];kind=x['kind'];o=x.get('origin',{})
        sheet=_s(o.get('sheet') or tr('当前文本表'))
        origin=tr('来源：{sheet} · 表头第 {row} 行。',sheet=sheet,row=_s(o.get('header_row')))
        if kind=='workbook_sheets':
            origin=tr('来源：上传的工作簿。') if x['total_sheets'] else tr('来源：上传的文本表。')
            body='**'+tr('工作表 · 共 {n} 个',n=x['total_sheets'])+'**\n\n'+tr('、').join(_s(n) for n in x['sheets'])
            if x.get('next_offset') is not None: body+='\n\n'+tr('还有工作表未列出，下一页 offset={n}。',n=x['next_offset'])
            if not x['total_sheets']: body+=tr('当前文件是单个文本表，没有 Excel 工作表。')
        elif kind=='sheet_layout':
            body='**'+tr('表头位置')+'**\n\n'+_table([tr('行号'),tr('非空单元格'),tr('文字单元格')],[[r['row'],r['nonempty_cells'],r['text_cells']] for r in x['row_profiles']])
            candidates=tr('；').join(tr('第 {row} 行（{labels}）',row=c['header_row'],labels=', '.join(_s(v) for v in c['labels'])) for c in x['header_candidates'])
            body+='\n'+tr('可能的表头：')+(candidates or tr('未找到明确候选'))+tr('。候选仅供判断，读取时仍需指定行号。')
            origin=tr('来源：{sheet} · 查看文件开头，未改变当前读取设置。',sheet=sheet)
        elif kind=='row_query':
            body=('**'+tr('筛选结果')+'**\n\n'+tr('共 {total} 行，符合条件 {matched} 行，展示 {shown} 行。',total=x['total_rows'],matched=x['matched_rows'],shown=x['shown_rows'])+'\n\n'
                  +_table([tr('数据行')]+x['columns'],[[r['table_row']]+[r['values'][c] for c in x['columns']] for r in x['rows']]))
        elif kind=='table_aggregate':
            body=('**'+tr(METRIC_NAMES[x['metric']])+(f" · {_s(x['value_column'])}" if x.get('value_column') else '')+'**\n\n'
                  +tr('共 {total} 行，纳入 {matched} 行。',total=x['total_rows'],matched=x['matched_rows'])+'\n\n')
            if not x['group_by']:
                s=x['summary'];body+=tr('结果：**{value}**。有效值 {valid}，缺失 {missing}，无效数值 {invalid}。',value=_s(s['value']),valid=s['valid_values'],missing=s['missing_values'],invalid=s['invalid_values'])
            else:
                body+=_table(x['group_by']+[tr('结果'),tr('记录数'),tr('缺失'),tr('无效数值')],[[r['keys'][c] for c in x['group_by']]+[r['value'],r['rows'],r['missing_values'],r['invalid_values']] for r in x['groups']])
        else:
            s=x['summary']
            body='**'+tr(ROW_OPERATIONS[x['operation']])+'**\n\n'+tr('列顺序：')+' → '.join(_s(c) for c in x['columns'])+tr('。')
            if x['weights'] is not None: body+=tr('权重：')+', '.join(_s(w) for w in x['weights'])+tr('。')
            body+='\n\n'+tr('纳入 {matched} 行，得到 {valid} 个有效结果。缺失输入 {missing} 行，无效输入 {invalid} 行，除零 {zero} 行，数值溢出 {overflow} 行。',
                            matched=x['matched_rows'],valid=s['valid_results'],missing=s['missing_input_rows'],invalid=s['invalid_input_rows'],
                            zero=s['zero_denominator_rows'],overflow=s['nonfinite_result_rows'])+'\n\n'
            if x.get('group_by'):
                body+=tr('分组后按 `{agg}` 汇总：',agg=x['aggregation'])+'\n\n'+_table(x['group_by']+[tr('结果'),tr('记录数')],[[r['keys'][c] for c in x['group_by']]+[r['value'],r['rows']] for r in x['groups']])
            else:
                body+=(tr('合计 {sum}，均值 {mean}，最小 {min}，最大 {max}。',sum=_s(s['sum']),mean=_s(s['mean']),min=_s(s['min']),max=_s(s['max']))+'\n\n'
                       +_table([tr('数据行'),tr('计算结果')],[[r['table_row'],r['value']] for r in x['rows']]))
            body+='\n'+tr('原表未改动；缺失输入不会自动补零。')
        if x.get('conditions'):
            join=tr(' 且 ') if x.get('match')=='all' else tr(' 或 ')
            body+='\n\n'+tr('筛选条件：')+join.join(f"{_s(c['column'])} {_s(c['operator'])} {_s(c['value'])}" for c in x['conditions'])+tr('。')
        sections.append(body+'\n\n'+origin)
    return '\n\n---\n\n'.join(sections)
