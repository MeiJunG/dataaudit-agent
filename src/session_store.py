"""SQLite-backed session persistence and project-owned upload storage.

Three kinds of state are kept apart:
  * task state (messages / steps / tool_log) lives only inside one agent run and is never stored here;
  * session history (sessions + entries tables) is the saved analysis archive;
  * explicit user preferences are NOT implemented in this module.

Every query is scoped by `owner`, an opaque random id that the browser keeps in its own storage.
It separates browsers on one deployment; it is not authentication.
"""
from __future__ import annotations

from .i18n import tr

import hashlib
import json
import os
import re
import shutil
import sqlite3
import threading
import time
from pathlib import Path
from uuid import uuid4

SCHEMA_VERSION = 1
MAX_STORE_MB = int(os.getenv('STORE_MAX_MB', '500'))
MAX_STORE_FILES = int(os.getenv('STORE_MAX_FILES', '60'))
FILE_RETENTION_DAYS = int(os.getenv('STORE_RETENTION_DAYS', '30'))

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS sessions(
  id TEXT PRIMARY KEY, owner TEXT NOT NULL, name TEXT NOT NULL,
  created_at REAL NOT NULL, updated_at REAL NOT NULL,
  dataset TEXT, reference TEXT, active_id TEXT);
CREATE INDEX IF NOT EXISTS sessions_owner ON sessions(owner, updated_at DESC);
CREATE TABLE IF NOT EXISTS entries(
  id TEXT NOT NULL, session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  seq INTEGER NOT NULL, parent_id TEXT, created_at REAL NOT NULL,
  dataset_sha TEXT, sheet TEXT, header_row INTEGER,
  payload TEXT NOT NULL, PRIMARY KEY(session_id, id));
CREATE TABLE IF NOT EXISTS files(
  sha256 TEXT PRIMARY KEY, filename TEXT NOT NULL, size INTEGER NOT NULL,
  rel_path TEXT NOT NULL, created_at REAL NOT NULL, last_used REAL NOT NULL);
"""


def _safe_name(name):
    base = re.sub(r'[\\/:*?"<>|\x00-\x1f]', '_', Path(str(name)).name).strip(' .')
    return (base or 'table')[:120]


def sha256_of(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


class SessionStore:
    def __init__(self, root, max_mb=None, max_files=None, retention_days=None):
        self.root = Path(root)
        self.files_dir = self.root / 'files'
        self.db_path = self.root / 'sessions.sqlite3'
        self.max_bytes = (max_mb if max_mb is not None else MAX_STORE_MB) * 1024 * 1024
        self.max_files = max_files if max_files is not None else MAX_STORE_FILES
        self.retention = (retention_days if retention_days is not None else FILE_RETENTION_DAYS) * 86400
        self.lock = threading.RLock()
        self.notice = ''
        self.root.mkdir(parents=True, exist_ok=True)
        self.files_dir.mkdir(parents=True, exist_ok=True)
        self._open()

    # ---- connection -------------------------------------------------
    def _open(self):
        try:
            self._connect()
        except sqlite3.DatabaseError:
            # An unreadable database file is moved aside, never silently overwritten.
            try:
                self.db.close()  # Windows cannot move a file that is still open
            except Exception:
                pass
            if self.db_path.exists():
                aside = self.db_path.with_name(f'sessions.corrupt-{int(time.time())}.sqlite3')
                self.db_path.replace(aside)
                self.notice = tr('保存记录的文件已损坏，已另存备份并新建了空白记录。')
            self._connect()

    def _connect(self):
        self.db = sqlite3.connect(self.db_path, check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA integrity_check').fetchone()
        self.db.executescript(_SCHEMA)
        self.db.execute("INSERT OR IGNORE INTO meta VALUES('schema_version',?)", (str(SCHEMA_VERSION),))

    def close(self):
        with self.lock:
            self.db.close()

    # ---- sessions ---------------------------------------------------
    def create_session(self, owner, name=None):
        sid, now = uuid4().hex, time.time()
        with self.lock:
            count = self.db.execute('SELECT COUNT(*) FROM sessions WHERE owner=?', (owner,)).fetchone()[0]
            self.db.execute('INSERT INTO sessions(id,owner,name,created_at,updated_at) VALUES(?,?,?,?,?)',
                            (sid, owner, (name or tr('新会话 {n}', n=count + 1)).strip()[:60], now, now))
        return sid

    def list_sessions(self, owner):
        with self.lock:
            rows = self.db.execute('SELECT id,name,updated_at FROM sessions WHERE owner=? ORDER BY updated_at DESC',
                                   (owner,)).fetchall()
        return [dict(r) for r in rows]

    def owns(self, owner, sid):
        with self.lock:
            return self.db.execute('SELECT 1 FROM sessions WHERE id=? AND owner=?', (sid, owner)).fetchone() is not None

    def owner_of(self, sid):
        with self.lock:
            row = self.db.execute('SELECT owner FROM sessions WHERE id=?', (sid,)).fetchone()
        return row['owner'] if row else None

    def rename_session(self, owner, sid, name):
        name = ' '.join(str(name or '').split())[:60]
        if not name:
            raise ValueError(tr('会话名称不能为空。'))
        with self.lock:
            cur = self.db.execute('UPDATE sessions SET name=?,updated_at=? WHERE id=? AND owner=?',
                                  (name, time.time(), sid, owner))
        if cur.rowcount == 0:
            raise KeyError(tr('找不到这个会话。'))
        return name

    def delete_session(self, owner, sid):
        """Remove the session, its entries, and uploaded files no other session still uses."""
        with self.lock:
            if not self.owns(owner, sid):
                raise KeyError(tr('找不到这个会话。'))
            reports = []
            for row in self.db.execute('SELECT payload FROM entries WHERE session_id=?', (sid,)):
                try:
                    path = json.loads(row['payload']).get('report_path')
                except ValueError:
                    path = None
                if path:
                    reports.append(path)
            self.db.execute('DELETE FROM sessions WHERE id=? AND owner=?', (sid, owner))
            removed = self._drop_unreferenced_files()
        for path in reports:
            Path(path).unlink(missing_ok=True)
        return removed

    # ---- snapshots --------------------------------------------------
    def save_snapshot(self, owner, sid, dataset, reference, history):
        """Replace the stored dataset settings and analysis archive with the current in-memory view."""
        history = history or {'entries': [], 'active_id': None}
        scope = dataset or {}
        with self.lock:
            if not self.owns(owner, sid):
                raise KeyError(tr('找不到这个会话。'))
            now = time.time()
            self.db.execute('BEGIN')
            try:
                keep = []
                for seq, entry in enumerate(history.get('entries', [])):
                    keep.append(entry['id'])
                    meta = (entry.get('metadata') or {}).get('dataset') or {}
                    imp = meta.get('import') or {}
                    payload = json.dumps(entry, ensure_ascii=False, default=str, allow_nan=False)
                    self.db.execute(
                        'INSERT INTO entries(id,session_id,seq,parent_id,created_at,dataset_sha,sheet,header_row,payload)'
                        ' VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(session_id,id) DO UPDATE SET seq=excluded.seq,'
                        'parent_id=excluded.parent_id,payload=excluded.payload',
                        (entry['id'], sid, seq, entry.get('parent_id'), now, meta.get('sha256'),
                         imp.get('sheet'), imp.get('header_row'), payload))
                marks = ','.join('?' * len(keep))
                self.db.execute(f'DELETE FROM entries WHERE session_id=?' + (f' AND id NOT IN ({marks})' if keep else ''),
                                [sid] + keep)
                self.db.execute('UPDATE sessions SET dataset=?,reference=?,active_id=?,updated_at=? WHERE id=?',
                                (json.dumps(scope or None, ensure_ascii=False), json.dumps(reference or None, ensure_ascii=False),
                                 history.get('active_id'), now, sid))
                self.db.execute('COMMIT')
            except Exception:
                self.db.execute('ROLLBACK')
                raise
        return now

    def load_session(self, owner, sid):
        """Return the saved view. Damaged entries are skipped and counted, never raised."""
        with self.lock:
            row = self.db.execute('SELECT * FROM sessions WHERE id=? AND owner=?', (sid, owner)).fetchone()
            if row is None:
                raise KeyError(tr('找不到这个会话。'))
            entry_rows = self.db.execute('SELECT id,payload FROM entries WHERE session_id=? ORDER BY seq', (sid,)).fetchall()
        entries, damaged = [], 0
        for r in entry_rows:
            try:
                entry = json.loads(r['payload'])
                if not isinstance(entry, dict) or entry.get('id') != r['id'] or 'question' not in entry or 'trace' not in entry:
                    raise ValueError
                entries.append(entry)
            except (ValueError, TypeError):
                damaged += 1
        def _json(text):
            try:
                value = json.loads(text) if text else None
                return value if isinstance(value, dict) else None
            except ValueError:
                return None
        active = row['active_id'] if any(e['id'] == row['active_id'] for e in entries) else None
        return {'id': sid, 'name': row['name'], 'updated_at': row['updated_at'],
                'dataset': _json(row['dataset']), 'reference': _json(row['reference']),
                'history': {'entries': entries, 'active_id': active}, 'damaged': damaged}

    # ---- uploaded files --------------------------------------------
    def store_file(self, path, filename=None):
        """Copy an upload into project storage (keyed by SHA-256) and return its record."""
        src = Path(path)
        digest = sha256_of(src)
        name = _safe_name(filename or src.name)
        with self.lock:
            row = self.db.execute('SELECT * FROM files WHERE sha256=?', (digest,)).fetchone()
            now = time.time()
            if row is not None and (self.root / row['rel_path']).is_file():
                self.db.execute('UPDATE files SET last_used=? WHERE sha256=?', (now, digest))
                return self._file_record(row['sha256'], row['filename'], row['rel_path'])
            target_dir = self.files_dir / digest[:16]
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / name
            shutil.copyfile(src, target)
            rel = target.relative_to(self.root).as_posix()
            self.db.execute('INSERT OR REPLACE INTO files VALUES(?,?,?,?,?,?)',
                            (digest, name, target.stat().st_size, rel, now, now))
            self.enforce_limits(protect=digest)
        return self._file_record(digest, name, rel)

    def _file_record(self, digest, name, rel):
        return {'sha256': digest, 'filename': name, 'path': str(self.root / rel)}

    def find_file(self, digest):
        """Path of a stored file whose bytes still hash to `digest`, else None."""
        with self.lock:
            row = self.db.execute('SELECT * FROM files WHERE sha256=?', (digest,)).fetchone()
            if row is None:
                return None
            path = self.root / row['rel_path']
            if not path.is_file():
                return None
            self.db.execute('UPDATE files SET last_used=? WHERE sha256=?', (time.time(), digest))
        return {'sha256': digest, 'filename': row['filename'], 'path': str(path)}

    def _referenced_hashes(self):
        shas = set()
        for row in self.db.execute('SELECT dataset,reference FROM sessions'):
            for text in (row['dataset'], row['reference']):
                try:
                    value = json.loads(text) if text else None
                except ValueError:
                    value = None
                if isinstance(value, dict) and value.get('sha256') and not value.get('sample'):
                    shas.add(value['sha256'])
        return shas

    def _delete_file(self, row):
        path = self.root / row['rel_path']
        path.unlink(missing_ok=True)
        try:
            path.parent.rmdir()
        except OSError:
            pass
        self.db.execute('DELETE FROM files WHERE sha256=?', (row['sha256'],))

    def _drop_unreferenced_files(self):
        used, removed = self._referenced_hashes(), 0
        for row in self.db.execute('SELECT * FROM files').fetchall():
            if row['sha256'] not in used:
                self._delete_file(row)
                removed += 1
        return removed

    def enforce_limits(self, protect=None):
        """Drop expired unreferenced files, then evict least-recently-used files over the caps."""
        with self.lock:
            used, removed = self._referenced_hashes(), []
            now = time.time()
            for row in self.db.execute('SELECT * FROM files').fetchall():
                if row['sha256'] not in used and row['sha256'] != protect and now - row['last_used'] > self.retention:
                    self._delete_file(row)
                    removed.append(row['sha256'])
            rows = self.db.execute('SELECT * FROM files ORDER BY last_used ASC').fetchall()
            total, count = sum(r['size'] for r in rows), len(rows)
            for row in rows:
                if total <= self.max_bytes and count <= self.max_files:
                    break
                if row['sha256'] == protect:
                    continue
                total -= row['size']
                count -= 1
                self._delete_file(row)
                removed.append(row['sha256'])
        return removed

    def usage(self):
        with self.lock:
            n, size = self.db.execute('SELECT COUNT(*),COALESCE(SUM(size),0) FROM files').fetchone()
        return {'files': n, 'bytes': size}
