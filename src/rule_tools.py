"""Bounded category, key, and conditional-summary tools for the active CSV."""
from __future__ import annotations

import numpy as np
import pandas as pd
from langchain_core.tools import StructuredTool

from .tools import _dump, is_sensitive_column


def build_rule_tools(frame: pd.DataFrame) -> list[StructuredTool]:
    def validate_categories(column: str, allowed_values: list[str], case_sensitive: bool = True) -> str:
        """Check non-null values against a user-supplied list, without trimming whitespace."""
        if column not in frame.columns:
            return _dump({'error': f'Unknown column: {column}'})
        if not 1 <= len(allowed_values) <= 50:
            return _dump({'error': 'Supply between 1 and 50 allowed values.'})
        values = frame[column].astype('string')
        allowed = list(dict.fromkeys(allowed_values))
        compared = values if case_sensitive else values.str.casefold()
        accepted = allowed if case_sensitive else [value.casefold() for value in allowed]
        present = values.notna()
        invalid = present & ~compared.isin(accepted)
        counts = values[invalid].value_counts().head(10)
        examples = [] if is_sensitive_column(column) else [
            {'value': str(value), 'count': int(count)} for value, count in counts.items()]
        return _dump({'column': column, 'allowed_values': allowed, 'case_sensitive': case_sensitive,
                      'non_null_values': int(present.sum()), 'valid_values': int((present & ~invalid).sum()),
                      'unexpected_values': int(invalid.sum()), 'missing_values': int((~present).sum()),
                      'unexpected_categories': examples,
                      'note': 'Missing values are separate. No whitespace is trimmed. Unexpected examples are limited to 10 categories and hidden for sensitive-looking fields.'})

    def check_key_uniqueness(columns: list[str]) -> str:
        """Check a proposed single or composite key for missing and repeated values."""
        columns = list(dict.fromkeys(columns))
        if not 1 <= len(columns) <= 10:
            return _dump({'error': 'Supply between 1 and 10 key columns.'})
        invalid = [name for name in columns if name not in frame.columns]
        if invalid:
            return _dump({'error': 'Unknown column(s): ' + ', '.join(invalid)})
        missing = frame[columns].isna().any(axis=1)
        complete = frame.loc[~missing, columns]
        repeated = complete.duplicated(keep=False)
        redundant = complete.duplicated(keep='first')
        return _dump({'columns': columns, 'rows': len(frame), 'complete_key_rows': len(complete),
                      'missing_key_rows': int(missing.sum()), 'distinct_complete_keys': len(complete.drop_duplicates()),
                      'duplicate_key_rows': int(repeated.sum()), 'redundant_rows': int(redundant.sum()),
                      'unique_among_complete': not bool(repeated.any()),
                      'usable_key': bool(len(frame) and not missing.any() and not repeated.any()),
                      'note': 'Duplicate-key rows include every participant. Redundant rows exclude the first. Rows missing any key component are excluded from duplicate counts. Empty data cannot establish a usable key. No key values are exposed.'})

    def filter_and_aggregate(filter_column: str, operator: str, value: str | float | int | bool,
                             metric_column: str | None = None, method: str = 'count') -> str:
        """Apply one literal condition and return counts or an aggregate; never evaluate code."""
        invalid = [name for name in [filter_column, metric_column] if name is not None and name not in frame.columns]
        if invalid:
            return _dump({'error': 'Unknown column(s): ' + ', '.join(invalid)})
        if operator not in {'eq', 'ne', 'gt', 'ge', 'lt', 'le', 'contains'}:
            return _dump({'error': 'operator must be eq/ne/gt/ge/lt/le/contains.'})
        if method not in {'count', 'sum', 'mean', 'min', 'max'} or (method != 'count' and metric_column is None):
            return _dump({'error': 'method must be count/sum/mean/min/max; numeric aggregates require metric_column.'})
        source = frame[filter_column]
        invalid_filter_values = 0
        numeric_filter = operator in {'gt', 'ge', 'lt', 'le'} or (
            operator in {'eq', 'ne'} and pd.api.types.is_numeric_dtype(source) and not pd.api.types.is_bool_dtype(source))
        if numeric_filter:
            try:
                target = float(value)
                if not np.isfinite(target):
                    raise ValueError()
            except (TypeError, ValueError):
                return _dump({'error': 'This comparison requires a finite numeric filter value.'})
            numeric = pd.to_numeric(source, errors='coerce')
            valid = numeric.notna() & np.isfinite(numeric)
            invalid_filter_values = int((source.notna() & ~valid).sum())
            compare = {'eq': numeric.eq, 'ne': numeric.ne, 'gt': numeric.gt, 'ge': numeric.ge,
                       'lt': numeric.lt, 'le': numeric.le}[operator]
            mask = valid & compare(target)
        elif pd.api.types.is_bool_dtype(source) and operator in {'eq', 'ne'}:
            if isinstance(value, str):
                if value.casefold() not in {'true', 'false'}:
                    return _dump({'error': 'Use true or false for a boolean field.'})
                target = value.casefold() == 'true'
            elif isinstance(value, bool):
                target = value
            else:
                return _dump({'error': 'Use true or false for a boolean field.'})
            mask = source.notna() & (source.eq(target) if operator == 'eq' else source.ne(target))
        else:
            text = source.astype('string')
            if operator == 'contains':
                mask = text.str.contains(str(value), regex=False, na=False)
            else:
                mask = text.notna() & (text.eq(str(value)) if operator == 'eq' else text.ne(str(value)))
        mask = mask.fillna(False)
        matched = int(mask.sum())
        missing_metric = invalid_metric = 0
        valid_metric_count = matched
        if metric_column is None:
            result = matched
        else:
            selected = frame.loc[mask, metric_column]
            missing_metric = int(selected.isna().sum())
            if method == 'count':
                result = int(selected.notna().sum())
                valid_metric_count = result
            else:
                numeric = pd.to_numeric(selected, errors='coerce')
                valid = numeric.notna() & np.isfinite(numeric)
                values = numeric[valid]
                invalid_metric = int((selected.notna() & ~valid).sum())
                valid_metric_count = len(values)
                result = None if values.empty else float(getattr(values, method)())
                if result is not None and not np.isfinite(result):
                    return _dump({'error': 'Aggregation exceeded the finite numeric range.'})
        return _dump({'filter_column': filter_column, 'operator': operator, 'filter_value': value,
                      'metric_column': metric_column, 'method': method, 'rows': len(frame),
                      'matched_rows': matched, 'missing_filter_values': int(source.isna().sum()),
                      'invalid_numeric_filter_values': invalid_filter_values, 'valid_metric_values': valid_metric_count,
                      'missing_metric_values': missing_metric, 'invalid_numeric_metric_values': invalid_metric,
                      'aggregate_value': result,
                      'note': 'One literal condition only. Missing filter values never match, including ne. Text matching is case-sensitive; contains is literal, not regex. Numeric aggregates exclude missing, invalid, and infinite metrics. An empty numeric aggregate is null. No matching rows are exposed.'})

    return [
        StructuredTool.from_function(validate_categories, name='validate_categories',
            description='Check a field against an explicit allowed_values list of strings. Requires column. case_sensitive defaults true. Missing values are separate; no whitespace is trimmed. Do not invent allowed categories.'),
        StructuredTool.from_function(check_key_uniqueness, name='check_key_uniqueness',
            description='Validate a proposed primary key, including missing components and repeated keys. columns is a list of one or more exact field names. Supports composite keys. Distinguishes all repeated-key rows from redundant rows.'),
        StructuredTool.from_function(filter_and_aggregate, name='filter_and_aggregate',
            description='Filter rows by one condition, then aggregate. Requires filter_column, operator (eq/ne/gt/ge/lt/le/contains), and value. Optional metric_column and method (count/sum/mean/min/max). count without a metric counts matched rows. No code, SQL, regex, or arbitrary expressions.'),
    ]
