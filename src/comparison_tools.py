"""Bounded, descriptive comparisons between two user-selected table snapshots."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from langchain_core.tools import StructuredTool

from .tools import is_sensitive_column


def _finite(value):
    return float(value) if value is not None and np.isfinite(value) else None


def compare_frames(current, reference, columns=None):
    if reference is None:
        return {'error': 'Select a reference table before comparing datasets.'}
    shared = [c for c in current.columns if c in reference.columns]
    if columns is not None and (not columns or len(columns) > 6 or len(set(columns)) != len(columns)):
        return {'error': 'Select 1..6 distinct shared columns, or omit columns.'}
    selected = shared[:6] if columns is None else columns
    if any(c not in shared for c in selected):
        return {'error': 'Selected columns must exist in BOTH datasets. Omit columns for schema comparison.'}
    added = [str(c) for c in current.columns if c not in reference.columns]
    removed = [str(c) for c in reference.columns if c not in current.columns]
    result = {
        'version': 1, 'kind': 'dataset_comparison',
        'current': {'rows': len(current), 'columns': len(current.columns), 'duplicate_rows': int(current.duplicated().sum())},
        'reference': {'rows': len(reference), 'columns': len(reference.columns), 'duplicate_rows': int(reference.duplicated().sum())},
        'schema': {'added': added[:10], 'removed': removed[:10], 'added_count': len(added),
                   'removed_count': len(removed), 'shared_count': len(shared),
                   'dtype_change_count': sum(str(current[c].dtype) != str(reference[c].dtype) for c in shared)},
        'columns': [], 'unexamined_shared_columns': len(shared) - len(selected),
    }
    for name in selected:
        a, b = current[name], reference[name]
        ra = float(a.isna().mean()) if len(a) else None
        rb = float(b.isna().mean()) if len(b) else None
        item = {'column': str(name), 'types': {'current': str(a.dtype), 'reference': str(b.dtype)},
                'missing': {'current': int(a.isna().sum()), 'reference': int(b.isna().sum()),
                            'current_rate': _finite(ra), 'reference_rate': _finite(rb),
                            'gap_pp': _finite((ra-rb)*100) if ra is not None and rb is not None else None}}
        if is_sensitive_column(name):
            item['distribution'] = 'omitted_sensitive_name'
        else:
            numeric_a = pd.api.types.is_numeric_dtype(a) and not pd.api.types.is_bool_dtype(a)
            numeric_b = pd.api.types.is_numeric_dtype(b) and not pd.api.types.is_bool_dtype(b)
            if numeric_a and numeric_b:
                a = pd.to_numeric(a, errors='coerce').replace([np.inf, -np.inf], np.nan).dropna()
                b = pd.to_numeric(b, errors='coerce').replace([np.inf, -np.inf], np.nan).dropna()
                ma = _finite(a.mean()) if len(a) else None
                mb = _finite(b.mean()) if len(b) else None
                std = _finite(b.std(ddof=0)) if len(b) else None
                change = _finite(ma-mb) if ma is not None and mb is not None else None
                item['numeric'] = {'current_mean': ma, 'reference_mean': mb, 'mean_change': change,
                                   'reference_std': std, 'standardized_change': _finite(change/std) if change is not None and std is not None and std > 0 else None,
                                   'valid_current': len(a), 'valid_reference': len(b)}
            elif not numeric_a and not numeric_b:
                na, nb = int(a.nunique(dropna=True)), int(b.nunique(dropna=True))
                tvd = None
                levels = []
                if a.notna().any() and b.notna().any() and max(na, nb) <= 1000:
                    ca, cb = a.value_counts(), b.value_counts()
                    pa, pb = ca/ca.sum(), cb/cb.sum()
                    keys = pa.index.union(pb.index, sort=False)
                    tvd = _finite(float((pa.reindex(keys, fill_value=0) - pb.reindex(keys, fill_value=0)).abs().sum()) / 2)
                    if len({str(k) for k in keys})==len(keys) and all(len(str(k))<=80 for k in keys):
                        largest = sorted(keys,key=lambda k:abs(float(pa.get(k,0))-float(pb.get(k,0))),reverse=True)[:3]
                        levels = [{'label':str(k),'current_count':int(ca.get(k,0)),'reference_count':int(cb.get(k,0)),
                                   'current_rate':float(pa.get(k,0)),'reference_rate':float(pb.get(k,0))} for k in largest]
                item['categorical'] = {'tvd': tvd, 'current_unique': na, 'reference_unique': nb,'levels':levels}
            else:
                item['distribution'] = 'incompatible_numeric_and_text_types'
        result['columns'].append(item)
    result['note'] = ('Descriptive differences, not a drift test or an error verdict. Numeric means use finite values; '
                      'standardization uses reference population std (ddof=0), undefined if zero/empty. '
                      'Categorical TVD compares non-null exact values, undefined for empty or >1000-category fields. '
                      'Up to three largest category-share differences are returned when labels are short and unambiguous. '
                      'Missing rates are undefined for zero-row tables. Duplicate rows are retained in metrics. '
                      'Sensitive-looking names omit distribution metrics. Schema name lists capped at 10; selected shared fields capped at 6.')
    return result


def build_comparison_tools(current, reference):
    def compare_datasets(columns: list[str] | None = None) -> str:
        return json.dumps(compare_frames(current, reference, columns), ensure_ascii=False, allow_nan=False)
    return [StructuredTool.from_function(compare_datasets, name='compare_datasets', description=(
        'Compare the CURRENT uploaded table with the attached REFERENCE table: schema, missing rates, '
        'numeric means and categorical TVD. Optional columns selects 1..6 exact shared fields; '
        'omit for up to 6 shared fields plus overall schema changes. Descriptive, no drift verdict. '
        'The app displays a paired missing-rate chart. No file paths or raw rows.'))]


def compact_comparison_observation(result):
    """Keep decision facts in the model context; retain the full result in the trace."""
    value = json.loads(result)
    if value.get('kind') != 'dataset_comparison':
        return result
    fields = []
    for row in value['columns']:
        item = {'column':row['column'], 'missing_counts':[row['missing']['current'],row['missing']['reference']]}
        if row['types']['current'] != row['types']['reference']:
            item['types'] = [row['types']['current'],row['types']['reference']]
        if row.get('numeric'):
            item['means'] = [row['numeric']['current_mean'],row['numeric']['reference_mean']]
        if row.get('categorical'):
            item['tvd'] = row['categorical']['tvd']
            if len(value['columns'])==1:
                item['category_shares'] = row['categorical']['levels']
        fields.append(item)
    return json.dumps({'rows':[value['current']['rows'],value['reference']['rows']],
                       'schema':value['schema'], 'columns':fields,
                       'unexamined_shared_columns':value['unexamined_shared_columns'],
                       'note':'Pairs are CURRENT, REFERENCE. Full computed details retained by app. Differences are descriptive.'},
                      ensure_ascii=False,allow_nan=False,separators=(',',':'))
