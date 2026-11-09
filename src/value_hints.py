"""Non-mutating, aggregate-only hints for common tabular representation pitfalls."""
from __future__ import annotations
import re
import pandas as pd

from .i18n import tr


def value_hints(frame):
    hints = []
    for column in frame:
        series = frame[column]
        if pd.api.types.is_numeric_dtype(series) or pd.api.types.is_datetime64_any_dtype(series):
            continue
        values = series.dropna().astype('string').str.strip()
        if values.empty:
            continue
        checks = {
            'percent_text': values.str.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)\s*[%％]'),
            'currency_or_grouping_text': values.str.contains(r'[$¥￥€£]|\d[,，]\d{3}(?:\D|$)',regex=True),
            'unit_suffix_text': values.str.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)\s*(?:万元|亿元|元|分|件|股|吨|公斤|千克|kg|cm|mm|ms|秒|分钟|小时|天)'),
            'non_iso_date_text': values.str.fullmatch(r'\d{4}[/.年]\d{1,2}[/.月]\d{1,2}日?|\d{1,2}/\d{1,2}/\d{4}'),
        }
        for kind,mask in checks.items():
            count = int(mask.fillna(False).sum())
            if count:
                hints.append({'column':str(column),'kind':kind,'matching_values':count,'non_null_values':len(values)})
    return hints


def hint_message(hint):
    explanation = {
        'percent_text':'含百分号的文字尚未转换；请先明确使用小数还是百分数。',
        'currency_or_grouping_text':'含货币符号或千位分隔符；请先确认币种和数值格式。',
        'unit_suffix_text':'数字后带单位文字；请先统一单位并另存为数值。',
        'non_iso_date_text':'使用非 ISO 日期文字；日期绘图前请确认格式并统一为 YYYY-MM-DD。',
    }[hint['kind']]
    return tr('{col}：{n} 个值', col=hint['column'], n=hint['matching_values']) + tr(explanation)
