"""Persistent sessions: save / reopen / restart / isolation / missing files. Synthetic data only."""
import json
import os
import sqlite3
import time
from pathlib import Path

import pandas as pd
import pytest

import app
from src import session_service as svc
from src.session_history import add_analysis, empty_history, new_question, selection_context
from src.session_store import SessionStore, sha256_of


@pytest.fixture()
def store(tmp_path, monkeypatch):
    monkeypatch.setenv('DATAAUDIT_DATA_DIR', str(tmp_path / 'data'))
    app._STORE = None
    yield app.get_store()
    app._STORE = None


def trace(tool='group_aggregate', **arguments):
    return [{'step': 1, 'tool': tool, 'arguments': arguments or {'group_by': 'g', 'value': 'v', 'agg': 'sum'},
             'status': 'ok', 'duration_ms': 3, 'structured_result': {'total': 6.5}, 'result': 'ok'}]


def workbook(tmp_path, name='book.xlsx'):
    path = tmp_path / name
    with pd.ExcelWriter(path) as xl:
        pd.DataFrame([['封面说明'], ['无数据']]).to_excel(xl, sheet_name='说明', header=False, index=False)
        pd.DataFrame([['备注', None, None], [None, None, None], ['组', '数量', '金额'], ['甲', 1, 2.5], ['乙', 3, 4.0]]
                     ).to_excel(xl, sheet_name='数据B', header=False, index=False)
        pd.DataFrame({'a': [1, 2, 3], 'b': [4, 5, 6]}).to_excel(xl, sheet_name='另一张', index=False)
    return str(path)


def open_page(browser, sid):
    return app._open_session(browser, sid)


def test_store_owner_isolation_and_rename_delete(store):
    a, b = store.create_session('owner-a'), store.create_session('owner-b')
    assert [r['id'] for r in store.list_sessions('owner-a')] == [a]
    with pytest.raises(KeyError):
        store.load_session('owner-b', a)
    with pytest.raises(KeyError):
        store.delete_session('owner-b', a)
    with pytest.raises(KeyError):
        store.rename_session('owner-b', a, 'x')
    assert store.rename_session('owner-a', a, '  季度  检查 ') == '季度 检查'
    with pytest.raises(ValueError):
        store.rename_session('owner-a', a, '   ')
    store.delete_session('owner-a', a)
    assert store.list_sessions('owner-a') == [] and len(store.list_sessions('owner-b')) == 1


def test_roundtrip_answer_arguments_and_results_identical(store, tmp_path):
    path = workbook(tmp_path)
    stored = app._persist_path(path)
    assert Path(stored).parent.parent == store.files_dir and Path(stored).name == 'book.xlsx'
    page = app.on_upload(stored, '数据B', 3)
    frame = page[0]
    assert list(frame.columns) == ['组', '数量', '金额']
    sid = store.create_session('o')
    history = add_analysis(empty_history(), '按组汇总金额', '甲 2.5，乙 4.0', trace(),
                           metadata={'dataset': app._dataset_metadata(frame)})
    svc.save_current(store, 'o', sid, svc.dataset_record(frame, app.EXAMPLES), None, history)

    store.close(); app._STORE = None  # simulate a service restart
    result = open_page({'owner': 'o'}, sid)
    frame2, history2 = result[0], result[10]
    assert list(frame2.columns) == ['组', '数量', '金额']
    assert frame2.attrs['import_info']['sheet'] == '数据B' and frame2.attrs['import_info']['header_row'] == 3
    assert history2['entries'] == history['entries'] and history2['active_id'] == history['active_id']
    assert result[6] == '甲 2.5，乙 4.0' and result[7] == history['entries'][0]['trace']
    assert result[7][0]['arguments'] == {'group_by': 'g', 'value': 'v', 'agg': 'sum'}


def test_followup_context_identical_after_reopen_and_new_question_detaches(store, tmp_path):
    frame = app.on_upload(app._persist_path(workbook(tmp_path)), '另一张', 1)[0]
    sid = store.create_session('o')
    h = add_analysis(empty_history(), '按 a 求和 b', '10', trace(group_by='a', value='b', agg='sum'),
                     metadata={'dataset': app._dataset_metadata(frame)})
    before = selection_context(h)
    assert 'sum' in before
    svc.save_current(store, 'o', sid, svc.dataset_record(frame, app.EXAMPLES), None, h)
    assert selection_context(open_page({'owner': 'o'}, sid)[10]) == before
    fresh = new_question(h)
    svc.save_current(store, 'o', sid, svc.dataset_record(frame, app.EXAMPLES), None, fresh)
    again = open_page({'owner': 'o'}, sid)[10]
    assert selection_context(again) == '' and len(again['entries']) == 1  # context cut, archive kept


def test_changing_sheet_or_file_forks_session_and_keeps_old_records(store, tmp_path):
    path = app._persist_path(workbook(tmp_path))
    f1 = app.on_upload(path, '数据B', 3)[0]
    sid = store.create_session('o')
    h = add_analysis(empty_history(), 'q', 'a', trace(), metadata={'dataset': app._dataset_metadata(f1)})
    svc.save_current(store, 'o', sid, svc.dataset_record(f1, app.EXAMPLES), None, h)
    f2 = app.on_upload(path, '另一张', 1)[0]
    new_sid, forked, _ = svc.save_current(store, 'o', sid, svc.dataset_record(f2, app.EXAMPLES), None, empty_history())
    assert forked and new_sid != sid
    assert len(store.load_session('o', sid)['history']['entries']) == 1
    assert store.load_session('o', new_sid)['dataset']['sheet'] == '另一张'
    # an unrelated record in the new session cannot see the old session's arguments
    assert selection_context(open_page({'owner': 'o'}, new_sid)[10]) == ''


def test_entries_for_a_different_file_are_not_reused(store, tmp_path):
    frame = app.on_upload(app._persist_path(workbook(tmp_path)), '另一张', 1)[0]
    sid = store.create_session('o')
    meta = app._dataset_metadata(frame)
    h = add_analysis(empty_history(), 'good', 'a', trace(), metadata={'dataset': meta})
    h = add_analysis(h, 'foreign', 'b', trace(), metadata={'dataset': {**meta, 'sha256': 'f' * 64}})
    svc.save_current(store, 'o', sid, svc.dataset_record(frame, app.EXAMPLES), None, h)
    result = open_page({'owner': 'o'}, sid)
    assert [e['question'] for e in result[10]['entries']] == ['good'] and '不是当前文件' in result[16]


def test_missing_file_is_explained_and_matching_reupload_resumes(store, tmp_path):
    path = workbook(tmp_path)
    stored = app._persist_path(path)
    frame = app.on_upload(stored, '数据B', 3)[0]
    sid = store.create_session('o')
    h = add_analysis(empty_history(), 'q', 'ans', trace(), metadata={'dataset': app._dataset_metadata(frame)})
    svc.save_current(store, 'o', sid, svc.dataset_record(frame, app.EXAMPLES), None, h)
    Path(stored).unlink()  # cleaned up behind our back
    result = open_page({'owner': 'o'}, sid)
    assert result[0] is None and '重新上传' in result[1] and result[6] == 'ans'
    assert len(result[10]['entries']) == 1  # history still viewable
    resumed = app.on_session_import_upload(path, sid, None)
    assert resumed[0] is not None and resumed[0].attrs['import_info']['sheet'] == '数据B'
    assert resumed[10]['entries'] == h['entries'] and resumed[0].attrs['source_sha256'] == sha256_of(path)


def test_different_file_after_loss_does_not_resume_old_records(store, tmp_path):
    path = workbook(tmp_path)
    stored = app._persist_path(path)
    frame = app.on_upload(stored, '数据B', 3)[0]
    sid = store.create_session('o')
    h = add_analysis(empty_history(), 'q', 'ans', trace(), metadata={'dataset': app._dataset_metadata(frame)})
    svc.save_current(store, 'o', sid, svc.dataset_record(frame, app.EXAMPLES), None, h)
    Path(stored).unlink()
    other = tmp_path / 'other.csv'
    other.write_text('x,y\n1,2\n', encoding='utf-8')
    result = app.on_session_import_upload(str(other), sid, None)
    assert result[0] is not None and result[10]['entries'] == []


def test_tampered_file_on_disk_is_rejected(store, tmp_path):
    stored = app._persist_path(workbook(tmp_path))
    frame = app.on_upload(stored, '另一张', 1)[0]
    sid = store.create_session('o')
    svc.save_current(store, 'o', sid, svc.dataset_record(frame, app.EXAMPLES), None,
                     add_analysis(empty_history(), 'q', 'a', trace(), metadata={'dataset': app._dataset_metadata(frame)}))
    Path(stored).write_bytes(Path(stored).read_bytes() + b'x')
    result = open_page({'owner': 'o'}, sid)
    assert result[0] is None and '重新上传' in result[1]


def test_damaged_entry_is_skipped_and_reported(store, tmp_path):
    frame = app.on_upload(app._persist_path(workbook(tmp_path)), '另一张', 1)[0]
    sid = store.create_session('o')
    h = add_analysis(empty_history(), 'one', 'a', trace(), metadata={'dataset': app._dataset_metadata(frame)})
    h = add_analysis(h, 'two', 'b', trace(), metadata={'dataset': app._dataset_metadata(frame)})
    svc.save_current(store, 'o', sid, svc.dataset_record(frame, app.EXAMPLES), None, h)
    store.db.execute("UPDATE entries SET payload='{not json' WHERE session_id=? AND seq=0", (sid,))
    result = open_page({'owner': 'o'}, sid)
    assert [e['question'] for e in result[10]['entries']] == ['two'] and '损坏' in result[16]


def test_corrupt_database_is_moved_aside(tmp_path):
    root = tmp_path / 'db'
    root.mkdir()
    (root / 'sessions.sqlite3').write_bytes(b'this is not a database' * 50)
    s = SessionStore(root)
    assert '损坏' in s.notice and list(root.glob('sessions.corrupt-*'))
    assert s.create_session('o')


def test_delete_removes_files_only_when_unreferenced(store, tmp_path):
    p1 = app._persist_path(workbook(tmp_path))
    f = app.on_upload(p1, '另一张', 1)[0]
    s1, s2 = store.create_session('o'), store.create_session('o')
    rec = svc.dataset_record(f, app.EXAMPLES)
    store.save_snapshot('o', s1, rec, None, empty_history())
    store.save_snapshot('o', s2, rec, None, empty_history())
    store.delete_session('o', s1)
    assert Path(p1).is_file()
    store.delete_session('o', s2)
    assert not Path(p1).exists() and store.usage()['files'] == 0


def test_delete_removes_saved_report_file(store, tmp_path):
    report = tmp_path / 'r.md'
    report.write_text('x', encoding='utf-8')
    sid = store.create_session('o')
    h = add_analysis(empty_history(), 'q', 'a', trace(), report_path=str(report))
    store.save_snapshot('o', sid, None, None, h)
    store.delete_session('o', sid)
    assert not report.exists()


def test_storage_limits_evict_least_recently_used_and_missing_is_reported(tmp_path):
    s = SessionStore(tmp_path / 'lim', max_files=2)
    paths = []
    for i in range(3):
        f = tmp_path / f'f{i}.csv'
        f.write_text(f'a\n{i}\n', encoding='utf-8')
        paths.append(s.store_file(f))
        time.sleep(0.01)
    assert s.usage()['files'] == 2
    assert s.find_file(paths[0]['sha256']) is None and s.find_file(paths[2]['sha256'])


def test_unreferenced_files_expire_but_referenced_ones_stay(tmp_path):
    s = SessionStore(tmp_path / 'ret', retention_days=0)
    a, b = tmp_path / 'a.csv', tmp_path / 'b.csv'
    a.write_text('a\n1\n', encoding='utf-8'); b.write_text('a\n2\n', encoding='utf-8')
    ra = s.store_file(a)
    sid = s.create_session('o')
    s.save_snapshot('o', sid, {'sha256': ra['sha256'], 'filename': 'a.csv'}, None, empty_history())
    s.store_file(b)
    time.sleep(0.02)
    s.enforce_limits()
    assert s.find_file(ra['sha256']) and s.usage()['files'] == 1


def test_oversized_or_invalid_uploads_are_not_stored(store, tmp_path):
    bad = tmp_path / 'notes.txt'
    bad.write_text('hello', encoding='utf-8')
    assert app._persist_path(str(bad)) == str(bad) and store.usage()['files'] == 0


def test_sample_dataset_restores_from_examples(store):
    frame = app.on_upload(str(app.EXAMPLES / 'office_orders.csv'))[0]
    rec = svc.dataset_record(frame, app.EXAMPLES)
    assert rec['sample'] is True and store.usage()['files'] == 0
    sid = store.create_session('o')
    store.save_snapshot('o', sid, rec, None, empty_history())
    result = open_page({'owner': 'o'}, sid)
    assert result[0] is not None and '示例' in result[1]


def test_boot_opens_last_session_creates_one_and_isolates_browsers(store):
    first = app.on_boot({'owner': '', 'last': ''})
    owner = first[17]['owner']
    assert owner and first[13]
    store.rename_session(owner, first[13], '我的会话')
    again = app.on_boot({'owner': owner, 'last': first[13]})
    assert again[13] == first[13] and again[15] == '我的会话'
    other = app.on_boot({'owner': '', 'last': first[13]})  # a different browser guessing an id
    assert other[17]['owner'] != owner and other[13] != first[13]
    assert app.on_pick_session({'owner': other[17]['owner']}, first[13])[0] == app.gr.skip()


def test_save_never_raises_into_the_page(store):
    out = app.on_session_save({'owner': 'o'}, 'x', None, None, 'not a history')
    assert 'error' in out[3] and out[0] == 'x'


def test_delete_flow_and_rename_via_handlers(store):
    browser = {'owner': 'o', 'last': ''}
    first = app.on_new_session(browser)
    sid = first[13]
    assert app.on_session_rename(browser, sid, '已改名')[1] == '已改名'
    assert 'error' in app.on_session_rename(browser, sid, ' ')[2]
    show, warn = app.on_delete_ask(browser, sid)
    assert show['visible'] and '已改名' in warn and '无法恢复' in warn
    after = app.on_delete_confirm(browser, sid)
    assert after[13] != sid and not store.owns('o', sid) and '已删除' in after[16]


def test_restore_analysis_rebuilds_a_cleaned_report(store, tmp_path, monkeypatch):
    monkeypatch.setattr(app, 'REPORT_DIR', tmp_path / 'reports')
    t = [{'tool': 'generate_quality_report', 'status': 'ok', 'arguments': {}, 'report_markdown': '# 报告'}]
    h = add_analysis(empty_history(), 'q', 'a', t, report_path=str(tmp_path / 'gone.md'))
    out = app.on_restore_analysis(h['entries'][0]['id'], h)
    assert out[3]['visible'] and Path(out[3]['value']).read_text(encoding='utf-8') == '# 报告'
