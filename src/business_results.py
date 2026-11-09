"""Render focused business checks from computed observations, without model-added numbers."""
from __future__ import annotations

import json
from html import escape
import re
from typing import Any

BUSINESS_TOOLS = {'check_numeric_range', 'compare_columns', 'summarize_time_series',
                  'validate_categories', 'check_key_uniqueness', 'filter_and_aggregate',
                  'check_text_quality', 'check_required_if', 'check_date_order'}


def render_business_answer(trace: list[dict[str, Any]], question: str) -> str | None:
    successful = [entry for entry in trace if entry['status'] == 'ok']
    names = {entry['tool'] for entry in successful}
    auxiliary = {'check_missing_values', 'check_duplicates'}
    if not names.intersection(BUSINESS_TOOLS) or not names.issubset(BUSINESS_TOOLS | auxiliary | {'inspect_schema'}):
        return None
    last_step = max(entry['step'] for entry in trace)
    if any(entry['status'] == 'error' for entry in trace if entry['step'] == last_step):
        return None
    chinese = bool(re.search(r'[\u3400-\u9fff]', question))
    latest = {entry['tool']: entry for entry in successful if entry['tool'] in BUSINESS_TOOLS | auxiliary}
    sections = []
    for name, entry in latest.items():
        try:
            x = entry.get('structured_result') or json.loads(entry['result'])
        except (ValueError, TypeError):
            return '结果过长，请查看检查过程。' if chinese else 'The result is too long; inspect the tool trace.'
        if name == 'check_numeric_range':
            title = f"`{x['column']}`"
            lower = '未设' if x['minimum'] is None else f"{x['minimum']:g}"
            upper = '未设' if x['maximum'] is None else f"{x['maximum']:g}"
            if chinese:
                sections.append(f"**{title} 范围检查（含边界）**\n\n下限 {lower}，上限 {upper}。\n\n"
                                f"检查 {x['checked_values']} 个有效数值：低于下限 {x['below_minimum']} 个，"
                                f"高于上限 {x['above_maximum']} 个，共 {x['violation_count']} 个超限。\n\n"
                                f"缺失 {x['missing_values']} 个，无效数值 {x['invalid_numeric_values']} 个。")
            else:
                sections.append(f"**{title}: inclusive range check**\n\n"
                                f"Limits: minimum={x['minimum']}, maximum={x['maximum']} (None means unset).\n\n"
                                f"Checked {x['checked_values']} finite values: {x['below_minimum']} below the minimum, "
                                f"{x['above_maximum']} above the maximum; {x['violation_count']} violations in total.\n\n"
                                f"Missing: {x['missing_values']}. Invalid numeric values: {x['invalid_numeric_values']}.")
        elif name == 'compare_columns':
            title = f"`{x['left_column']}` / `{x['right_column']}`"
            rule = f"{x['absolute_tolerance']:g}"
            if chinese:
                sections.append(f"**{title} 逐行核对**\n\n"
                                f"可比较 {x['compared_rows']} 行：一致 {x['matched_rows']} 行，不一致 {x['mismatched_rows']} 行。\n\n"
                                f"单边缺失 {x['one_side_missing_rows']} 行，双边缺失 {x['both_missing_rows']} 行，"
                                f"无效数值对 {x['invalid_numeric_pair_rows']} 行。\n\n"
                                + (f"按数值比较，允许绝对误差 {rule}。" if x['mode'] == 'numeric' else '按原值比较，区分大小写。'))
            else:
                sections.append(f"**{title}: row-by-row reconciliation**\n\n"
                                f"Comparable: {x['compared_rows']}; matched: {x['matched_rows']}; mismatched: {x['mismatched_rows']}.\n\n"
                                f"One side missing: {x['one_side_missing_rows']}; both missing: {x['both_missing_rows']}; "
                                f"invalid numeric pairs: {x['invalid_numeric_pair_rows']}.\n\n"
                                + (f"Absolute numeric tolerance: {rule}." if x['mode'] == 'numeric' else 'Exact, case-sensitive value comparison.'))
        elif name == 'summarize_time_series':
            excluded_metrics = sum(row['rows'] - row['metric_non_null'] for row in x['periods'])
            frequency = {'day': '按天', 'week': '按周', 'month': '按月'}[x['frequency']]
            method = {'sum': '总额', 'mean': '均值', 'count': '非空数量'}[x['method']]
            title = f"`{x['metric_column']}` {frequency}{method}（UTC）" if chinese else f"`{x['metric_column']}` · {x['frequency']} / {x['method']} · UTC"
            lines = [f"**{title}**", '',
                     '| 期间起点 | 记录数 | 有效指标数 | 结果 |' if chinese else '| Period start | Rows | Valid metrics | Value |',
                     '|---|---:|---:|---:|']
            for row in x['periods']:
                value = '—' if row['value'] is None else f"{row['value']:g}"
                lines.append(f"| {row['period_start']} | {row['rows']} | {row['metric_non_null']} | {value} |")
            lines.extend(['', (f"无效日期 {x['invalid_date_rows']} 行，缺失日期 {x['missing_date_rows']} 行；"
                              f"有效日期记录中，指标缺失或无效 {excluded_metrics} 行。" if chinese else
                              f"Invalid dates: {x['invalid_date_rows']}; missing dates: {x['missing_date_rows']}. "
                              f"Among valid-date rows, missing or invalid metrics: {excluded_metrics}.")])
            sections.append('\n'.join(lines))
        elif name == 'validate_categories':
            allowed = ', '.join(escape(str(value)).replace('`', "'") for value in x['allowed_values'])
            if chinese:
                text = (f"**`{x['column']}` 取值检查**\n\n允许值：{allowed}。\n\n"
                        f"检查 {x['non_null_values']} 个非空值，列表外 {x['unexpected_values']} 个，缺失 {x['missing_values']} 个。")
                if x['unexpected_categories']:
                    examples = '、'.join(f"`{escape(row['value']).replace('`', chr(39))}`（{row['count']}）" for row in x['unexpected_categories'])
                    text += '\n\n列表外的值（最多 10 类）：' + examples + '。'
                text += '\n\n' + ('区分大小写，不自动去除空格。' if x['case_sensitive'] else '忽略大小写，不自动去除空格。')
            else:
                text = (f"**`{x['column']}`: allowed values**\n\nAllowed: {allowed}.\n\n"
                        f"Checked: {x['non_null_values']}; unexpected: {x['unexpected_values']}; missing: {x['missing_values']}. "
                        f"Case-sensitive: {x['case_sensitive']}. Whitespace is not trimmed.")
            sections.append(text)
        elif name == 'check_key_uniqueness':
            label = ', '.join(x['columns'])
            if chinese:
                sections.append(f"**候选主键：`{label}`**\n\n"
                                f"完整键 {x['complete_key_rows']} 行，键有缺失 {x['missing_key_rows']} 行。\n\n"
                                f"重复键涉及 {x['duplicate_key_rows']} 行，其中多余 {x['redundant_rows']} 行（保留第一条后计数）。\n\n"
                                + ('未发现缺失或重复，满足这两项主键检查。' if x['usable_key'] else ('这份表为空，无法确认主键。' if x['rows'] == 0 else '暂不满足主键要求。')))
            else:
                sections.append(f"**Proposed key: `{label}`**\n\nComplete-key rows: {x['complete_key_rows']}; missing-key rows: {x['missing_key_rows']}. "
                                f"Repeated-key participants: {x['duplicate_key_rows']}; redundant rows beyond the first: {x['redundant_rows']}. "
                                f"Passes non-null/unique-key checks: {x['usable_key']}.")
        elif name == 'filter_and_aggregate':
            value = escape(str(x['filter_value'])).replace('`', "'")
            result = '—' if x['aggregate_value'] is None else f"{x['aggregate_value']:g}"
            if chinese:
                operator = {'eq':'等于','ne':'不等于','gt':'大于','ge':'大于等于','lt':'小于','le':'小于等于','contains':'包含'}[x['operator']]
                method = {'count':'数量','sum':'总额','mean':'均值','min':'最小值','max':'最大值'}[x['method']]
                metric = x['metric_column'] or '记录'
                text = (f"**筛选后统计**\n\n条件：`{x['filter_column']}` {operator} `{value}`。\n\n"
                        f"符合条件 {x['matched_rows']} 行，共 {x['rows']} 行。`{metric}`{method}：**{result}**。")
                if x['metric_column']:
                    text += (f"\n\n参与计算 {x['valid_metric_values']} 个值，指标缺失 {x['missing_metric_values']} 个，"
                             f"无效数值 {x['invalid_numeric_metric_values']} 个。")
                if x['missing_filter_values'] or x['invalid_numeric_filter_values']:
                    text += f"\n\n筛选列缺失 {x['missing_filter_values']} 个，无法按数字比较 {x['invalid_numeric_filter_values']} 个；这些记录未计入匹配。"
            else:
                text = (f"**Filtered summary**\n\nCondition: `{x['filter_column']}` {x['operator']} `{value}`. "
                        f"Matched {x['matched_rows']} of {x['rows']} rows. {x['method']}({x['metric_column'] or 'rows'}) = **{result}**. "
                        f"Missing metrics: {x['missing_metric_values']}; invalid numeric metrics: {x['invalid_numeric_metric_values']}.")
            sections.append(text)
        elif name == 'check_text_quality':
            lines = ['**文字格式检查**' if chinese else '**Text format checks**', '',
                     '| 字段 | 缺失 | 纯空白 | 首尾空格 | 写法合并组 |' if chinese else '| Field | Missing | Blank | Outer spaces | Variant groups |',
                     '|---|---:|---:|---:|---:|']
            for field in x['fields']:
                column = escape(str(field['column'])).replace('|', '&#124;')
                lines.append(f"| {column} | {field['missing_values']} | {field['blank_text_values']} | {field['outer_whitespace_values']} | {field['normalized_collision_groups']} |")
            lines += ['', '写法合并组指去除首尾空格、忽略大小写后相同的不同原值。只标出问题，不自动修改。' if chinese else
                      'Variant groups contain distinct original spellings that coincide after trimming and Unicode case folding. No data was changed.']
            sections.append('\n'.join(lines))
        elif name == 'check_required_if':
            value = escape(str(x['equals'])).replace('`', "'")
            if chinese:
                lines = [f"**条件必填检查**\n\n`{x['condition_column']}` 等于 `{value}` 时，以下字段必须填写。",
                         f"\n符合条件 {x['matched_rows']} 行，其中 {x['affected_rows']} 行存在必填项缺失。", '']
                lines += [f"- `{escape(str(column))}`：缺失 {count} 行。" for column, count in x['missing_by_column'].items()]
                lines += ['', '空值、空字符串和纯空白都算未填写；同一行缺少多个字段只计一次。']
            else:
                lines = [f"**Conditional required fields**\n\nWhen `{x['condition_column']}` equals `{value}`: {x['matched_rows']} matched rows, {x['affected_rows']} rows with a missing required field.", '']
                lines += [f"- `{escape(str(column))}`: {count} missing." for column, count in x['missing_by_column'].items()]
            sections.append('\n'.join(lines))
        elif name == 'check_date_order':
            if chinese:
                rule = '可以相同' if x['allow_equal'] else '必须早于结束日期'
                text = (f"**日期先后检查**\n\n`{x['start_column']}` → `{x['end_column']}`，{rule}。\n\n"
                        f"比较 {x['compared_rows']} 行，开始晚于结束 {x['start_after_end_rows']} 行，日期相同 {x['equal_date_rows']} 行，共 {x['violation_rows']} 行不符合规则。\n\n"
                        f"日期有缺失 {x['missing_date_pair_rows']} 行，格式无效 {x['invalid_date_pair_rows']} 行；这些记录未参与先后比较。")
            else:
                text = (f"**Date ordering**\n\n`{x['start_column']}` → `{x['end_column']}`; equality allowed: {x['allow_equal']}. "
                        f"Compared {x['compared_rows']} rows; reversed: {x['start_after_end_rows']}; equal: {x['equal_date_rows']}; violations: {x['violation_rows']}. "
                        f"Missing pairs: {x['missing_date_pair_rows']}; invalid pairs: {x['invalid_date_pair_rows']}.")
            sections.append(text)
        elif name == 'check_missing_values':
            missing = [row for row in x['by_column'] if row['missing_count']]
            if chinese:
                text = '**空值检查**\n\n'
                text += '\n'.join(f"- `{row['column']}`：{row['missing_count']} 个，占该列 {row['missing_ratio']:.1%}。" for row in missing) if missing else '没有发现空值。'
            else:
                text = '**Missing values**\n\n'
                text += '\n'.join(f"- `{row['column']}`: {row['missing_count']} ({row['missing_ratio']:.1%})." for row in missing) if missing else 'No missing values found.'
            sections.append(text)
        elif name == 'check_duplicates':
            scope = ', '.join(x['scope']) if isinstance(x['scope'], list) else ('整行' if chinese else 'all fields')
            sections.append(f"**重复记录**\n\n按 {scope} 查重，多余 {x['duplicate_rows']} 行（保留第一条后计数）。" if chinese else
                            f"**Duplicate records**\n\nScope: {scope}; redundant rows beyond the first: {x['duplicate_rows']}.")
    return '\n\n'.join(sections)
