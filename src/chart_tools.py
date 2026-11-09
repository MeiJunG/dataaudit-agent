"""Declarative, computed charts: no generated Python, SQL, paths or expressions."""
from __future__ import annotations

import json
from typing import Literal

import numpy as np
import pandas as pd
from langchain_core.tools import StructuredTool

from .tools import is_sensitive_column
from .chart_limits import MAX_CATEGORY_GROUPS, MAX_LINE_PERIODS


def build_chart_tools(frame: pd.DataFrame) -> list[StructuredTool]:
    def create_chart(chart_type: Literal['bar', 'histogram', 'line'], x: str,
                     y: str | None = None, method: Literal['count', 'sum', 'mean'] = 'count',
                     frequency: Literal['day', 'week', 'month'] = 'month') -> str:
        """Compute a bounded chart specification from the active dataset."""
        def dump(value):
            return json.dumps(value, ensure_ascii=False, allow_nan=False)

        if any(c not in frame.columns for c in [x] + ([y] if y else [])):
            return dump({'error': 'Unknown chart column. Use exact dataset field names.'})
        if any(is_sensitive_column(c) for c in [x] + ([y] if y else [])):
            return dump({'error': 'Charts exclude fields with sensitive-looking names.'})
        if chart_type == 'histogram' and (y is not None or method != 'count'):
            return dump({'error': 'Histogram requires only x and method=count; omit y.'})
        if chart_type != 'histogram' and ((method == 'count' and y is not None) or (method != 'count' and y is None)):
            return dump({'error': 'count counts rows and requires y omitted; sum/mean require numeric y.'})

        result = {'version': 1, 'chart_type': chart_type, 'x': x, 'y': y, 'method': method,
                  'frequency': frequency if chart_type == 'line' else None, 'rows': len(frame)}
        if chart_type == 'histogram':
            numeric = pd.to_numeric(frame[x], errors='coerce').replace([np.inf, -np.inf], np.nan)
            values = numeric.dropna().to_numpy(dtype=float)
            if not len(values):
                return dump({'error': 'No finite numeric values for the histogram.'})
            try:
                counts, edges = np.histogram(values, bins=10)
            except (ValueError, OverflowError):
                return dump({'error': 'Numeric range cannot be safely binned.'})
            if not np.isfinite(edges).all():
                return dump({'error': 'Numeric range cannot be safely binned.'})
            result.update(data=[{'low': float(edges[i]), 'high': float(edges[i+1]), 'y': int(n)}
                                for i, n in enumerate(counts)],
                          plotted_rows=len(values), excluded_x_rows=int(numeric.isna().sum()))
        else:
            if chart_type == 'line':
                raw = frame[x]
                # Reject epoch integers and locale date guessing, including numeric strings.
                dates = pd.to_datetime(raw.astype('string'), format='ISO8601', errors='coerce', utc=True)
                freq = {'day': 'D', 'week': 'W-SUN', 'month': 'M'}[frequency]
                groups = dates.dt.tz_localize(None).dt.to_period(freq).dt.start_time.dt.strftime('%Y-%m-%d')
            else:
                groups = frame[x].astype('string')
                if groups.dropna().str.len().gt(256).any():
                    return dump({'error': 'Category labels exceed 256 characters; choose a shorter field.'})
            limit = MAX_LINE_PERIODS if chart_type == 'line' else MAX_CATEGORY_GROUPS
            if groups.nunique() > limit:
                return dump({'error': f'Chart exceeds {limit} groups/periods. Choose a lower-cardinality field or coarser frequency.'})
            if not groups.notna().any():
                return dump({'error': 'No valid categories or ISO dates to plot.'})
            numeric = (pd.to_numeric(frame[y], errors='coerce').replace([np.inf, -np.inf], np.nan)
                       if y is not None else pd.Series(1, index=frame.index))
            work = pd.DataFrame({'group': groups, 'metric': numeric})
            grouped = work.groupby('group', sort=True)['metric']
            values = grouped.size() if method == 'count' else grouped.sum(min_count=1) if method == 'sum' else grouped.mean()
            if not np.isfinite(values.dropna().to_numpy(dtype=float)).all():
                return dump({'error': 'Aggregation exceeded the finite numeric range.'})
            if not values.notna().any():
                return dump({'error': 'No finite numeric values for the selected metric.'})
            data = [{'x': str(k), 'y': None if pd.isna(v) else int(v) if method == 'count' else float(v)}
                    for k, v in values.items()]
            result.update(data=data, plotted_rows=int(groups.notna().sum()), excluded_x_rows=int(groups.isna().sum()),
                          excluded_metric_rows=int((groups.notna() & numeric.isna()).sum()))
        result['note'] = ('Duplicate rows are retained. Missing/invalid x values are excluded. '
                          + ('Histogram uses 10 equal-width bins; the last bin includes its right edge.'
                             if chart_type == 'histogram' else
                             'Numeric aggregates exclude missing/invalid/infinite y; all-invalid groups have null values. '
                             'count means all rows per group, not non-null y. '
                             + ('Dates use UTC; weeks start Monday. Only observed periods are returned; '
                                'a line joins observed points and does not imply measurements between them.' if chart_type == 'line' else '')))
        return dump(result)

    return [StructuredTool.from_function(create_chart, name='create_chart', description=(
        'Create an actual chart when asked to draw/plot/visualize. chart_type=bar for categories, '
        'histogram for numeric x distribution, line for ISO date x. Exact x required; '
        'method=count counts rows (omit y), sum/mean require numeric y. '
        'Line frequency=day/week/month. Max 366 line periods or 30 category groups. No sensitive fields.'))]


def compact_chart_observation(result):
    """Keep full chart values in the trace while bounding the next model observation."""
    value = json.loads(result)
    data = value.get('data',[])
    if value.get('chart_type') != 'line' or len(data)<=30:
        return result
    compact = {key:item for key,item in value.items() if key not in {'data','note'}}
    compact.update(point_count=len(data),null_points=sum(p['y'] is None for p in data),
                   first_points=data[:2],last_points=data[-2:],
                   observation='Chart computed; full ordered points are retained in the UI/export trace. Only endpoints are included here; do not infer intermediate values.')
    return json.dumps(compact,ensure_ascii=False,allow_nan=False)
