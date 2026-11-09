"""Adapters exposing focused consistency checks on the active table."""
from __future__ import annotations

import pandas as pd
from langchain_core.tools import StructuredTool

from .check_logic import check_conditional_values, check_date_pairs, check_text_values
from .tools import _dump, is_sensitive_column


def build_consistency_tools(frame: pd.DataFrame) -> list[StructuredTool]:
    def values(column):
        return [None if pd.isna(value) else value for value in frame[column].tolist()]

    def check_text_quality(columns: list[str] | None = None) -> str:
        """Check blanks, outer whitespace and category spelling variants without modifying data."""
        selected = list(dict.fromkeys(columns)) if columns is not None else [
            str(column) for column in frame.columns if pd.api.types.is_object_dtype(frame[column]) or
            isinstance(frame[column].dtype, pd.StringDtype)]
        if not selected or len(selected) > 20:
            return _dump({'error': 'Select between 1 and 20 text columns.'})
        invalid = [column for column in selected if column not in frame.columns]
        if invalid:
            return _dump({'error': 'Unknown column(s): ' + ', '.join(invalid)})
        return _dump({'columns_checked': len(selected), 'fields': [
            {'column': column, **check_text_values(values(column), sensitive=is_sensitive_column(column))}
            for column in selected]})

    def check_required_if(condition_column: str, equals: str, required_columns: list[str]) -> str:
        """Require fields only for rows matching an exact categorical condition."""
        selected = list(dict.fromkeys(required_columns))
        if not 1 <= len(selected) <= 20:
            return _dump({'error': 'Supply between 1 and 20 required columns.'})
        invalid = [column for column in [condition_column, *selected] if column not in frame.columns]
        if invalid:
            return _dump({'error': 'Unknown column(s): ' + ', '.join(invalid)})
        result = check_conditional_values(values(condition_column), {column: values(column) for column in selected}, equals)
        return _dump({'condition_column': condition_column, 'equals': equals,
                      'required_columns': selected, **result})

    def check_date_order(start_column: str, end_column: str, allow_equal: bool = True) -> str:
        """Validate start <= end (or start < end), with missing and invalid ISO dates separate."""
        invalid = [column for column in [start_column, end_column] if column not in frame.columns]
        if invalid:
            return _dump({'error': 'Unknown column(s): ' + ', '.join(invalid)})
        return _dump({'start_column': start_column, 'end_column': end_column,
                      **check_date_pairs(values(start_column), values(end_column), allow_equal=allow_equal)})

    return [
        StructuredTool.from_function(check_text_quality, name='check_text_quality', description='Inspect text fields for whitespace-only values, outer spaces, and distinct category spellings that collide after strip + casefold. Optional columns (maximum 20); no source edits. Different from numeric type validation.'),
        StructuredTool.from_function(check_required_if, name='check_required_if', description='Check conditional required fields. For example completed rows must have amount and recorded_amount. Requires condition_column, equals (exact case-sensitive string), required_columns. Missing includes null and blank text. Does not filter and sum.'),
        StructuredTool.from_function(check_date_order, name='check_date_order', description='Check order of two ISO date columns, such as order_date <= ship_date. Requires start_column and end_column; allow_equal defaults true. Missing/invalid pairs are separate; timestamps normalized to UTC. Does not merely inspect date ranges.'),
    ]
