"""Glue between the in-page state (frame / history / reference) and the SessionStore.

Rules (documented in docs/PERSISTENT_SESSIONS.md):
  * A session is bound to one data scope: file fingerprint + worksheet + header row (+ reference table).
    Changing the scope while the session already holds analyses opens a NEW session; the old one stays intact.
  * Stored uploads are located by SHA-256, never by a temporary Gradio path.
"""
from __future__ import annotations

import re
from pathlib import Path

from .session_store import SessionStore, sha256_of

AUTO_NAME = re.compile(r'^(新会话|New session) \d+$')


def dataset_record(frame, examples_dir):
    """Describe how a loaded table was read; None when nothing usable is loaded."""
    if frame is None:
        return None
    attrs = frame.attrs
    path, sha = attrs.get('_source_path'), attrs.get('source_sha256')
    if not path or not sha:
        return None
    info = attrs.get('import_info', {})
    sample = Path(path).resolve().parent == Path(examples_dir).resolve()
    return {'filename': Path(path).name, 'sha256': sha, 'sheet': info.get('sheet'),
            'header_row': info.get('header_row', 1), 'sample': sample, 'format': info.get('format'),
            'rows': int(len(frame))}


def reference_record(reference, examples_dir):
    if not reference or reference.get('frame') is None:
        return None
    return dataset_record(reference['frame'], examples_dir)


def scope_key(dataset, reference=None):
    def part(r):
        return None if not r else (r.get('sha256'), r.get('sheet'), r.get('header_row'))
    return (part(dataset), part(reference))


def locate_file(store: SessionStore, record, examples_dir):
    """Path of the exact file the record was made from, or None (missing / cleaned up / changed)."""
    if not record or not record.get('sha256'):
        return None
    if record.get('sample'):
        path = Path(examples_dir) / Path(record.get('filename', '')).name
        if path.is_file() and sha256_of(path) == record['sha256']:
            return str(path)
        return None
    found = store.find_file(record['sha256'])
    if found and sha256_of(found['path']) == record['sha256']:
        return found['path']
    return None


def usable_entries(history, dataset):
    """Drop entries whose recorded data fingerprint differs from the session's dataset."""
    if not dataset:
        return history, 0
    kept, dropped = [], 0
    for entry in history['entries']:
        sha = ((entry.get('metadata') or {}).get('dataset') or {}).get('sha256')
        if sha and sha != dataset.get('sha256'):
            dropped += 1
        else:
            kept.append(entry)
    active = history.get('active_id') if any(e['id'] == history.get('active_id') for e in kept) else None
    return {'entries': kept, 'active_id': active}, dropped


def save_current(store: SessionStore, owner, sid, dataset, reference, history):
    """Persist the page state. Returns (session_id, forked, saved_at)."""
    history = history or {'entries': [], 'active_id': None}
    forked = False
    try:
        saved = store.load_session(owner, sid)
    except KeyError:
        sid, saved = store.create_session(owner), None
        saved = store.load_session(owner, sid)
        forked = True
    if (saved['history']['entries'] and not history['entries']
            and scope_key(saved['dataset'], saved['reference']) != scope_key(dataset, reference)):
        sid, forked = store.create_session(owner), True
        saved = store.load_session(owner, sid)
    if dataset and AUTO_NAME.match(saved['name']):
        label = dataset['filename'] + (' · ' + str(dataset['sheet']) if dataset.get('sheet') else '')
        store.rename_session(owner, sid, label)
    saved_at = store.save_snapshot(owner, sid, dataset, reference, history)
    return sid, forked, saved_at
