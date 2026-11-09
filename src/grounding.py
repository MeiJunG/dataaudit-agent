"""Check that numbers in a model-written answer can be found in the tool results.

Most answers in this project are rendered directly from tool results. When the model's own free text
is shown instead, this check lists numbers that appear nowhere in the executed tools' arguments or
results (allowing rounding and percent forms). It is a consistency check, not a proof of correctness:
a number that matches may still be used for the wrong claim.
"""
from __future__ import annotations

import json
import re

_NUMBER = re.compile(r'(?<![\w.])[-+]?\d[\d,]*(?:\.\d+)?%?')
_EVIDENCE = re.compile(r'[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?')


def _answer_numbers(text):
    found = []
    for token in _NUMBER.findall(text or ''):
        percent = token.endswith('%')
        raw = token.rstrip('%').replace(',', '')
        try:
            value = float(raw)
        except ValueError:
            continue
        decimals = len(raw.split('.')[1]) if '.' in raw else 0
        if decimals == 0 and abs(value) < 10 and not percent:
            continue  # list numbers and tiny counts are too ambiguous to judge
        found.append((token, value, decimals, percent))
    return found


def _evidence_values(trace):
    values = set()
    for entry in trace or []:
        if entry.get('status') != 'ok':
            continue
        blob = json.dumps(entry.get('structured_result'), ensure_ascii=False, default=str) if entry.get('structured_result') is not None else ''
        blob += ' ' + str(entry.get('result', '')) + ' ' + json.dumps(entry.get('arguments', {}), ensure_ascii=False, default=str)
        for token in _EVIDENCE.findall(blob):
            try:
                values.add(float(token))
            except ValueError:
                pass
    return values


def _matches(value, decimals, percent, evidence):
    tolerance = 0.5 * 10 ** (-decimals) + 1e-9
    if any(abs(e - value) <= tolerance for e in evidence):
        return True
    # "12.5%" may be the stored fraction 0.125
    return percent and any(abs(e * 100 - value) <= tolerance for e in evidence)


def check_grounding(answer, trace):
    """Return {'checked': n, 'unverified': [...]}; None when there is nothing to judge."""
    if not any(e.get('status') == 'ok' for e in trace or []):
        return None
    numbers = _answer_numbers(str(answer))
    if not numbers:
        return None
    evidence = _evidence_values(trace)
    unverified = [tok for tok, val, dec, pct in numbers if not _matches(val, dec, pct, evidence)]
    return {'checked': len(numbers), 'unverified': unverified[:10], 'method': 'numbers_in_tool_results'}
