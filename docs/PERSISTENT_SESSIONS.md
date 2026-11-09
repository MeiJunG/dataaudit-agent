# Persistent sessions and recovery

This round adds saved sessions that survive page refreshes, reopening the browser and web-service restarts. It deliberately stays small: one SQLite file plus a project-owned folder of uploaded files. No model weights, embeddings or external services are involved.

## Three kinds of state

| Kind | Where it lives | Lifetime |
|---|---|---|
| **Task execution state** (`messages`, `steps`, `tool_log` of one agent run) | In memory inside `src/agent.py` | Ends with the run. Never written to the database. |
| **Session history and analysis archive** | `data/sessions.sqlite3` (`sessions`, `entries`) | Until the user deletes the session. |
| **Explicit user preferences** (reply language, chart style, user-stated rules) | **Not implemented.** Nothing is inferred from file contents, and no statistic is stored as a standing fact. | – |

The model still receives only the small bounded record from `src/session_history.py` (at most two linked turns, tool names and arguments, 768 bytes). Saving eight analyses does not mean sending eight analyses to the model.

## What is saved, where, for how long

All paths are under `DATAAUDIT_DATA_DIR` (default `<project>/data`, git-ignored; on the server `/hy-tmp/dataaudit-agent/.../data`).

- `sessions.sqlite3` – per session: id, owner token, name, created/updated time, dataset record (file name, SHA-256, worksheet, header row, row count), reference-table record, active analysis id. Per analysis (the most recent 8 of each session): question, answer, parent link, full tool trace (arguments, results, errors, routing, report text), report path and the data fingerprint it was computed on. **Kept until the session is deleted.**
- `files/<sha256[:16]>/<original name>` – a copy of each uploaded table, deduplicated by SHA-256. Never copied to a laptop or to GitHub.
- `browser.secret` – signing key for the browser-side owner token.
- Sample files from `examples/` are not copied; they are referenced by name and fingerprint.
- Charts are rebuilt from the saved tool result; quality reports are rebuilt from the saved report text if the report file was cleaned up.

### Upload file lifecycle

| Rule | Value (env override) |
|---|---|
| Per file | 10 MB (`MAX_UPLOAD_MB`) |
| Total stored | 500 MB (`STORE_MAX_MB`) |
| Number of files | 60 (`STORE_MAX_FILES`) |
| Unreferenced files expire after | 30 days (`STORE_RETENTION_DAYS`) |
| Over a cap | least-recently-used files are evicted, **even if a session still refers to them** |
| Delete session | its file copies are removed unless another session uses the same fingerprint; its report files are removed too |

If the stored copy is missing, evicted, or no longer hashes to the saved fingerprint, the page says the original file must be uploaded again. The saved analyses stay readable. Uploading **the same bytes** re-attaches them and re-applies the saved worksheet and header row. Uploading a different file does not reuse the old records.

## Scope and isolation

- A session is bound to one data scope: file fingerprint + worksheet + header row (+ reference table). Changing any of them in a session that already holds analyses **opens a new session**; the old one remains intact and openable. Follow-up context never crosses scopes.
- Entries whose recorded fingerprint differs from the session's dataset are ignored on restore.
- **新问题** clears the follow-up parent but keeps the saved history.
- Every database query is filtered by an `owner` id, a random token kept in the browser's own storage (Gradio `BrowserState`). Different browsers cannot list, open, rename or delete each other's sessions. It is not authentication: anyone who obtains a token can use it, and two tabs of one browser profile share it.

## Recovery: what is and is not implemented

Implemented: reopening a saved analysis (no model call), restoring a session after refresh or service restart, restoring worksheet/header settings and the reference table, and explicit messages for missing files, fingerprint mismatch and damaged records (a damaged entry is skipped and counted; a damaged database file is moved aside as `sessions.corrupt-<time>.sqlite3` and a fresh one is created).

**Not implemented: resuming a run that was interrupted mid-way.** An analysis is saved only when it finishes. If the service stops during a run, that run is lost and the user asks again. No LangGraph checkpointer is used, so the UI offers no "continue from where it stopped" control. The existing six-step limit and repeated-call guard are unchanged.

## Other limits

- Last write wins if the same session is open in two tabs.
- Closing the tab loses nothing already saved, but an analysis still running is not saved until it ends.
- Excel formulas are read from cached values; irregular layouts are as before.

## Code map

- `src/session_store.py` – SQLite schema, owner-scoped CRUD, file storage and limits.
- `src/session_service.py` – dataset/reference records, scope rules, `save_current` (fork on scope change).
- `app.py` – `on_boot`, `on_pick_session`, `on_new_session`, `on_session_save`, rename/delete handlers, resume-on-reupload (`on_session_import_upload`).
- `tests/test_persistent_sessions.py` – 20 tests with synthetic workbooks.
