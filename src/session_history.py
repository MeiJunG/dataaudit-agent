"""Bounded, per-dataset session history and small tool-selection context."""
from __future__ import annotations

import copy
import json
from uuid import uuid4

MAX_ENTRIES = 8
CONTEXT_BYTES = 768


def empty_history():
    return {'entries': [], 'active_id': None}


def add_analysis(history, question, answer, trace, report_path=None, metadata=None):
    """Store successful computed work; a failed request does not replace useful context."""
    state = copy.deepcopy(history or empty_history())
    if not any(e.get('status') == 'ok' for e in trace or []):
        return state
    entry = {'id': uuid4().hex, 'parent_id': state.get('active_id'),
             'question': str(question)[:2000], 'answer': str(answer),
             'trace': copy.deepcopy(trace), 'report_path': report_path,
             'metadata': copy.deepcopy(metadata or {})}
    state['entries'] = (state.get('entries', []) + [entry])[-MAX_ENTRIES:]
    state['active_id'] = entry['id']
    return state


def select_analysis(history, entry_id):
    state = copy.deepcopy(history or empty_history())
    entry = next((e for e in state['entries'] if e['id'] == entry_id), None)
    if entry is not None:
        state['active_id'] = entry['id']
    return entry, state


def new_question(history):
    state = copy.deepcopy(history or empty_history())
    state['active_id'] = None
    return state


def history_choices(history):
    entries = (history or {}).get('entries', [])
    return [(f'{index + 1:02d} · ' + ' '.join(e['question'].split())[:64], e['id'])
            for index, e in reversed(list(enumerate(entries)))]


def _short_text(text, limit):
    return str(text).encode('utf-8')[:limit].decode('utf-8', errors='ignore')


def selection_context(history, budget=CONTEXT_BYTES):
    """At most two linked turns, arguments only: never prior answers, rows or results.

    JSON records are kept whole. An oversized argument is omitted rather than rewritten.
    The newest turn wins when the UTF-8 budget would be exceeded.
    """
    state = history or empty_history()
    entries = {e['id']: e for e in state.get('entries', [])}
    current = state.get('active_id')
    selected = []
    for _ in range(2):
        entry = entries.get(current)
        if not entry:
            break
        record = {'question': _short_text(entry['question'], 160), 'tools': []}
        for tool in reversed(entry.get('trace', [])):
            if tool.get('status') != 'ok':
                continue
            call = {'name': tool['tool'], 'arguments': tool.get('arguments', {})}
            if len(json.dumps(call, ensure_ascii=False).encode('utf-8')) <= 400:
                record['tools'].insert(0, call)
            if len(record['tools']) == 3:
                break
        while record['tools'] and len(json.dumps([record] + selected, ensure_ascii=False).encode('utf-8')) > budget:
            record['tools'].pop(0)
        if len(json.dumps([record] + selected, ensure_ascii=False).encode('utf-8')) > budget:
            break
        selected.insert(0, record)
        current = entry.get('parent_id')
    return json.dumps(selected, ensure_ascii=False) if selected else ''
