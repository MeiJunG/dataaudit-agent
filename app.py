from __future__ import annotations

import os
import time as _time
from uuid import uuid4
from html import escape
from pathlib import Path
from textwrap import dedent

import warnings

warnings.filterwarnings('ignore', category=DeprecationWarning, module=r'gradio(\.|$)')  # Gradio 6 notices, not actionable for users
warnings.filterwarnings('ignore', category=DeprecationWarning, message=r".*Gradio 6\.0.*")

import gradio as gr
from dotenv import load_dotenv

load_dotenv()

from src.agent import run_routed_agent as run_agent
from src.data_manager import MAX_UPLOAD_MB, load_table, inspect_source, EMPTY_HEADER_ERROR
from src.interface import APP_CSS, header_html, file_status, overview_html, tools_catalog
from src.reports import save_report_from_trace
from src.presentation import execution_html, preview_html
from src.tools import is_sensitive_column
from src.visualization import distribution_columns, distribution_figure, empty_figure, missingness_figure
from src.agent_charts import chart_spec_from_trace, chart_figure, save_chart
from src.session_history import empty_history, add_analysis, select_analysis, history_choices, new_question
from src.analysis_export import save_analysis_record
from src.comparison_view import comparison_from_trace, comparison_figure, save_comparison_chart
from src.value_hints import hint_message
from src.session_store import SessionStore, sha256_of
from src.suggestions import suggest_questions, profile_html
from src.result_tables import save_result_csv
from src.repro_script import save_script
from src.model_check import endpoint_status, friendly_model_error
from src import session_service as svc
from src.i18n import tr, LANG, bind_language, current as current_lang

ROOT = Path(__file__).resolve().parent
REPORT_DIR = Path(os.getenv("DATAAUDIT_REPORT_DIR", ROOT / "outputs" / "reports"))
CHART_DIR = REPORT_DIR.parent / 'charts'
RECORD_DIR = REPORT_DIR.parent / 'records'
EXPORT_DIR = REPORT_DIR.parent / 'exports'
EXAMPLES = ROOT / 'examples'
_STORE = None


def data_dir():
    return Path(os.getenv('DATAAUDIT_DATA_DIR', ROOT / 'data'))


def get_store():
    """Project-owned persistent store (sessions database + uploaded file copies), created on first use."""
    global _STORE
    if _STORE is None or _STORE.root != data_dir():
        _STORE = SessionStore(data_dir())
    return _STORE


def _persist_path(file_obj):
    """Copy a temporary upload into project storage so later reads do not depend on Gradio's cache."""
    if not file_obj:
        return file_obj
    try:
        resolved = Path(file_obj).resolve()
        store = get_store()
        if any(base.resolve() in resolved.parents for base in (store.files_dir, EXAMPLES)):
            return str(file_obj)
        inspect_source(file_obj)  # invalid / oversized files are not kept; the normal loader reports why
        return store.store_file(file_obj)['path']
    except (ValueError, OSError):
        return file_obj


def _load_upload(file_obj, sheet=None, header_row=1):
    if file_obj is None:
        return (None, file_status(), overview_html(),
                empty_figure(tr("选好文件后，这里会显示空值情况")), gr.update(choices=[], value=None),
                empty_figure(tr("选一列，看看数据怎么分布")))
    try:
        frame = load_table(file_obj,sheet=sheet,header_row=header_row)
        choices = distribution_columns(frame)
        selected = choices[0] if choices else None
        info = frame.attrs.get('import_info',{})
        display_name = Path(file_obj).name + (' · '+info['sheet'] if info.get('sheet') else '')
        return (frame, file_status(display_name, len(frame)), overview_html(frame), missingness_figure(frame),
                gr.update(choices=choices, value=selected), distribution_figure(frame, selected))
    except ValueError as exc:
        # A blank cover sheet should not prevent workbook discovery. Other errors stay errors.
        if sheet is None and str(exc) == tr(EMPTY_HEADER_ERROR):
            import pandas as pd
            import hashlib
            source=inspect_source(file_obj)
            if source['sheets']:
                frame=pd.DataFrame()
                with Path(file_obj).open('rb') as stream: sha=hashlib.file_digest(stream,'sha256').hexdigest()
                frame.attrs.update(_source_path=str(Path(file_obj).resolve()),source_sha256=sha,
                    import_info={'format':source['format'],'sheet':None,'sheet_names':source['sheets'],'header_row':1,'unselected':True})
                return (frame,file_status(Path(file_obj).name,0),overview_html(),empty_figure(tr('请选择工作表')),
                        gr.update(choices=[],value=None),empty_figure(tr('选择工作表和表头后可查看图表')))
        return (None, file_status(error=str(exc)), overview_html(),
                empty_figure(tr("检查读取设置，或换一份表格再试试")), gr.update(choices=[], value=None),
                empty_figure(tr("还没有可以显示的数据")))


def on_upload(file_obj, sheet=None, header_row=1):
    return (*_load_upload(file_obj,sheet,header_row), "", [], gr.update(value=None, visible=False))


def _example(filename):
    path = ROOT / "examples" / filename
    result = list(on_upload(str(path)))
    if result[0] is not None:
        result[1] = file_status(filename, len(result[0]), sample=True)
    return tuple(result)


def on_office_example():
    return _example("office_orders.csv")


def on_reconciliation_example():
    return _example("reconciliation.csv")


def on_rule_example():
    return _example("rule_checks.csv")


def on_consistency_example():
    return _example("consistency_checks.csv")


def on_preview(frame):
    if frame is None:
        return preview_html([], [])
    selected = frame.iloc[:5, :8]
    rows = [[None if value is None or str(value) in {"<NA>", "NaT"} else value for value in row]
            for row in selected.astype(object).where(selected.notna(), None).values.tolist()]
    hidden = {str(column) for column in selected.columns if is_sensitive_column(column)}
    return preview_html(list(selected.columns), rows, hidden=hidden)


def on_clear():
    return on_upload(None)


def on_chart_question(frame):
    if frame is not None:
        columns = distribution_columns(frame)
        if columns:
            column = columns[0]
            return tr('请用 {column} 画一张分布图，选择适合它的图表类型。', column=column)
    return tr('请先上传表格，再告诉我想画哪一列。')


def on_agent_chart(trace):
    spec = chart_spec_from_trace(trace)
    if spec is None:
        comparison = comparison_from_trace(trace)
        if comparison is not None:
            path = save_comparison_chart(comparison, CHART_DIR)
            return comparison_figure(comparison), gr.update(value=str(path), visible=True), gr.update(selected='agent-chart')
        return (empty_figure(tr('想画什么图？在右侧写下问题。')),
                gr.update(value=None, visible=False), gr.update(selected='distribution'))
    path = save_chart(spec, CHART_DIR)
    return chart_figure(spec), gr.update(value=str(path), visible=True), gr.update(selected='agent-chart')


def on_table_download(trace):
    path = save_result_csv(trace, EXPORT_DIR)
    return gr.update(value=str(path) if path else None, visible=bool(path))


def on_script_download(trace, frame=None):
    source = frame.attrs.get('_source_path') if frame is not None else None
    path = save_script(trace, EXPORT_DIR, Path(source).name if source else 'your_table.xlsx')
    return gr.update(value=str(path) if path else None, visible=bool(path))


def on_suggestions(frame):
    choices = suggest_questions(frame)
    return gr.update(choices=choices, value=None, visible=bool(choices))


def on_suggestion_pick(value):
    return value if value else gr.skip()


def on_distribution_change(column, frame):
    return distribution_figure(frame, column) if frame is not None else empty_figure(tr("先选一份表格"))


def on_submit(question, frame, history=None, reference=None):
    if frame is None:
        return tr("先在上面选择表格，或者加载一份示例。"), [], gr.update(value=None, visible=False)
    if not question or not question.strip():
        return tr("写下想查的问题，或者点一个常用问题。"), [], gr.update(value=None, visible=False)
    try:
        options = {'history':history} if history else {}
        if reference and reference.get('frame') is not None:
            options['reference_frame'] = reference['frame']
        answer, log = run_agent(question, frame, **options)
        report_path = save_report_from_trace(log, REPORT_DIR)
        return answer, log, gr.update(value=str(report_path) if report_path else None, visible=bool(report_path))
    except Exception as exc:
        detail = escape(f"{type(exc).__name__}: {exc}")
        friendly = friendly_model_error(exc)
        if friendly:
            return (friendly + "<details><summary>" + tr("查看原因") + "</summary><pre>" + detail + "</pre></details>",
                    [], gr.update(value=None, visible=False))
        return (tr("这次没有算完。可以把问题写得更具体一些，再试一次。")
                + f"<details><summary>{tr('查看原因')}</summary><pre>{detail}</pre></details>", [], gr.update(value=None, visible=False))


def _dataset_metadata(frame):
    return {'rows':len(frame), 'columns':[str(c) for c in frame.columns],
            'sha256':frame.attrs.get('source_sha256'),'import':frame.attrs.get('import_info')} if frame is not None else None


def on_session_submit(question, frame, history, reference=None):
    answer, log, download = on_submit(question, frame, history, reference)
    metadata = {'model':os.getenv('MODEL_NAME','qwen2.5-7b-instruct'), 'dataset':_dataset_metadata(frame),
                'reference':_dataset_metadata(reference['frame']) if reference and reference.get('frame') is not None else None}
    updated = add_analysis(history, question, answer, log, download.get('value'), metadata)
    return answer, log, download, updated


def progress_html(events, started):
    """Small live status shown while the agent works; built only from real tool events."""
    done = [e for e in events if e.get('phase') == 'tool_done']
    running = events[-1] if events and events[-1].get('phase') == 'tool_start' else None
    lines = []
    for e in done:
        mark = '✓' if e.get('status') == 'ok' else '×'
        lines.append(f'<li class="{"ok" if e.get("status") == "ok" else "bad"}"><span>{mark}</span>{tr("第 {n} 步", n=e["step"])} · {escape(str(e["tool"]))}</li>')
    if running:
        lines.append(f'<li class="run"><span>…</span>{tr("第 {n} 步", n=running["step"])} · {escape(str(running["tool"]))}</li>')
    head = tr('正在分析') if lines else tr('正在理解问题')
    return (f'<div class="run-progress"><strong>{head}</strong><small>{tr("已用 {s} 秒", s=int(_time.monotonic() - started))}</small>'
            + (f'<ul>{"".join(lines)}</ul>' if lines else '') + '</div>')


def on_session_submit_stream(question, frame, history, reference=None):
    """Same result as on_session_submit, but yields a live step list while the agent runs."""
    import threading
    from src.agent import PROGRESS
    events, outcome, done = [], {}, threading.Event()
    lang = current_lang()  # a new thread does not inherit context variables

    def work():
        LANG.set(lang)
        PROGRESS.set(lambda e: events.append(e))
        try:
            outcome['value'] = on_session_submit(question, frame, history, reference)
        except BaseException as exc:  # surfaced below
            outcome['error'] = exc
        finally:
            done.set()

    started = _time.monotonic()
    threading.Thread(target=work, daemon=True).start()
    while not done.wait(0.5):
        yield progress_html(list(events), started), gr.skip(), gr.skip(), gr.skip()
    if 'error' in outcome:
        raise outcome['error']
    yield outcome['value']


def on_analysis_export(history):
    path = save_analysis_record(history, RECORD_DIR)
    link = ('<a class="record-file-link" href="/analysis-records/' + path.name
            + '" download="' + escape(path.name, quote=True) + '">' + tr('下载分析记录 · JSON') + '</a>') if path else ''
    return gr.update(value=link, visible=bool(path))


def on_current_export(history, trace):
    state = history or empty_history()
    entry = next((e for e in state['entries'] if e['id']==state.get('active_id')),None)
    if not trace or entry is None or entry['trace'] != trace:
        return gr.update(value='',visible=False)
    return on_analysis_export(history)


def on_reference_status(reference):
    if not reference:
        return '<div class="context-hint">' + tr('尚未选择参考表。换一份当前表时，参考表会一起移除。') + '</div>'
    if reference.get('error'):
        return '<div class="reference-error">' + tr('参考表读取失败：') + escape(reference['error'])+'</div>'
    frame = reference['frame']
    label = tr('参考表 · 示例') if reference.get('sample') else tr('参考表')
    sheet = frame.attrs.get('import_info',{}).get('sheet')
    return '<div class="reference-ready"><span>'+label+'</span><strong>'+escape(reference['filename'])+'</strong><small>' + tr('{rows} 行 · {cols} 列', rows=len(frame), cols=len(frame.columns))+(' · '+escape(sheet) if sheet else '')+'</small></div>'


def on_reference_upload(file_obj, sheet=None, header_row=1):
    reference = None
    if file_obj:
        file_obj = _persist_path(file_obj)
        try:
            reference = {'frame':load_table(file_obj,sheet,header_row),'filename':Path(file_obj).name}
        except ValueError as exc:
            reference = {'frame':None,'error':str(exc)}
        reference['source'] = _import_source(file_obj,sheet,header_row,reference.get('frame'))
    return reference, '', [], gr.update(value=None,visible=False), empty_history()


def on_reference_clear():
    return on_reference_upload(None)


def on_reference_example():
    result = list(on_reference_upload(str(ROOT/'examples'/'office_reference.csv')))
    if result[0] and result[0].get('frame') is not None:
        result[0]['sample'] = True
    return tuple(result)


def on_compare_question():
    return tr('对照参考表，检查字段、缺失率和分布变化。'), gr.update(open=True)


def on_history_choices(history):
    return gr.update(choices=history_choices(history), value=None)


def on_restore_analysis(entry_id, history):
    if not entry_id:
        return (gr.skip(),) * 5
    entry, updated = select_analysis(history, entry_id)
    if entry is None:
        return (gr.skip(),) * 5
    path = _report_path(entry)
    available = bool(path)
    return (entry['question'], entry['answer'], entry['trace'],
            gr.update(value=path if available else None, visible=available), updated)


def _report_path(entry):
    """Existing report file, or one rebuilt from the saved tool result when the file was cleaned up."""
    path = entry.get('report_path')
    if path and Path(path).is_file():
        return path
    if any(t.get('tool') == 'generate_quality_report' and t.get('status') == 'ok' for t in entry.get('trace', [])):
        rebuilt = save_report_from_trace(entry['trace'], REPORT_DIR)
        if rebuilt:
            entry['report_path'] = str(rebuilt)
            return str(rebuilt)
    return None


def on_new_question(history):
    return '', '', [], gr.update(value=None, visible=False), new_question(history)


def on_session_upload(file_obj):
    return *on_upload(file_obj), empty_history(), None


def _import_source(file_obj,sheet=None,header_row=1,frame=None):
    if not file_obj:
        return None
    try:
        source = inspect_source(file_obj)
    except ValueError:
        return None
    source.update({'sheet':sheet or source['sheet'],'header_row':header_row,
                   'info':frame.attrs.get('import_info',{}) if frame is not None else {}})
    return source


def on_import_upload(file_obj):
    file_obj = _persist_path(file_obj)
    result = on_session_upload(file_obj)
    return *result[:9],_import_source(file_obj,frame=result[0]),*result[9:]


def on_read_table(source,sheet,header_row):
    result = (*on_upload(source['path'] if source else None,sheet,header_row),empty_history(),None)
    updated = _import_source(source['path'],sheet,header_row,result[0]) if source else None
    if source and source.get('sample') and result[0] is not None:
        result = list(result)
        result[1] = file_status(Path(source['path']).name+' · '+str(sheet),len(result[0]),sample=True)
        updated['sample'] = True
    return *result[:9],updated,*result[9:]


# ---------------------------------------------------------------- persistent sessions
def _owner(browser):
    return (browser or {}).get('owner') or ''


def _picker_update(owner, sid):
    rows = get_store().list_sessions(owner) if owner else []
    choices = [(r['name'] + ' · ' + _time.strftime('%m-%d %H:%M', _time.localtime(r['updated_at'])), r['id']) for r in rows]
    return gr.update(choices=choices, value=sid if any(r['id'] == sid for r in rows) else None)


def _session_name(owner, sid):
    return next((r['name'] for r in get_store().list_sessions(owner) if r['id'] == sid), '')


def _status(text, kind='ok'):
    return f'<div class="save-status {kind}">{escape(text)}</div>'


def _notice_html(message):
    return ('<div class="file-status failed">' + tr('需要重新上传原文件') + '<details open><summary>' + tr('查看说明') + '</summary>'
            + escape(message) + '</details></div>')


def _active_entry(history):
    return next((e for e in history['entries'] if e['id'] == history.get('active_id')), None)


def _open_from_data(data, forced_path=None):
    """Rebuild the 12 page outputs from a saved session. Returns (outputs, notes)."""
    store, notes = get_store(), []
    dataset = data['dataset']
    history, dropped = svc.usable_entries(data['history'], dataset)
    if dropped:
        notes.append(tr('{n} 条记录对应的不是当前文件，已不再使用。', n=dropped))
    if data['damaged']:
        notes.append(tr('{n} 条保存的记录已损坏，已跳过。', n=data["damaged"]))
    path = forced_path or (svc.locate_file(store, dataset, EXAMPLES) if dataset else None)
    frame, source = None, None
    page = list(on_upload(None))
    if dataset and path:
        page = list(on_upload(path, dataset.get('sheet'), dataset.get('header_row', 1)))
        frame = page[0]
        if frame is not None and frame.attrs.get('source_sha256') != dataset['sha256']:
            frame, page = None, list(on_upload(None))
            page[1] = _notice_html(tr('找到的文件与保存时的内容不一致，没有使用。请上传原来的那份文件。'))
            notes.append(tr('文件内容与保存时不一致。'))
        elif frame is not None:
            source = _import_source(path, dataset.get('sheet'), dataset.get('header_row', 1), frame)
            if dataset.get('sample'):
                source['sample'] = True
                page[1] = file_status(dataset['filename'] + (' · ' + str(dataset['sheet']) if dataset.get('sheet') else ''),
                                      len(frame), sample=True)
        else:
            notes.append(tr('保存的读取设置现在无法读取这份文件。'))
    elif dataset:
        page[1] = _notice_html(tr('「{name}」的副本已不在服务器上（可能已被清理）。之前的分析记录仍可查看；'
                                  '请重新上传同一份文件，内容一致时会接着使用这些记录和读取设置。', name=dataset["filename"]))
        notes.append(tr('原文件已不在服务器上，请重新上传。'))
    reference = None
    ref_record = data['reference']
    if ref_record:
        ref_path = svc.locate_file(store, ref_record, EXAMPLES)
        if ref_path and frame is not None:
            reference = on_reference_upload(ref_path, ref_record.get('sheet'), ref_record.get('header_row', 1))[0]
            if reference.get('frame') is None or reference['frame'].attrs.get('source_sha256') != ref_record['sha256']:
                reference = None
                notes.append(tr('参考表无法按原设置读取。'))
            elif ref_record.get('sample'):
                reference['sample'] = True
        elif frame is not None:
            notes.append(tr('参考表的文件已不在服务器上，需要重新选择。'))
    entry = _active_entry(history)
    answer_text, log, download = '', [], gr.update(value=None, visible=False)
    if entry is not None:
        answer_text, log = entry['answer'], entry['trace']
        report = _report_path(entry)
        download = gr.update(value=report, visible=bool(report))
    outputs = (frame, page[1], page[2], page[3], page[4], page[5], answer_text, log, download, source, history, reference)
    return outputs, notes


def _open_session(browser, sid):
    owner = _owner(browser)
    data = get_store().load_session(owner, sid)
    outputs, notes = _open_from_data(data)
    count = len(outputs[10]['entries'])
    text = tr('已恢复「{name}」· {n} 条分析记录', name=data["name"], n=count) if count else tr('已打开「{name}」', name=data["name"])
    if notes:
        text += tr('。') + ' '.join(notes)
    return (*outputs, '', sid, _picker_update(owner, sid), data['name'], _status(text, 'warn' if notes else 'ok'),
            {'owner': owner, 'last': sid}, gr.update(visible=False))


def on_model_status():
    """Warn on the page when the configured model endpoint cannot be used; stays hidden when it is fine."""
    status = endpoint_status()
    if status['ok']:
        return gr.update(value='', visible=False)
    return gr.update(visible=True, value=(
        '<div class="model-notice"><strong>' + escape(status['message']) + '</strong>'
        '<span>' + tr('表格预览、概览和图表仍可使用；提问需要模型。请在 .env 中设置 OPENAI_BASE_URL、OPENAI_API_KEY、MODEL_NAME，'
                      '然后运行 {cmd} 检查。', cmd='<code>python -m src.model_check</code>') + '</span></div>'))


def on_boot(browser):
    store = get_store()
    owner = _owner(browser) or uuid4().hex
    sessions = store.list_sessions(owner)
    last = (browser or {}).get('last')
    sid = last if any(r['id'] == last for r in sessions) else (sessions[0]['id'] if sessions else store.create_session(owner))
    result = list(_open_session({'owner': owner}, sid))
    if store.notice:
        result[16] = _status(store.notice, 'warn')
    return tuple(result)


def on_pick_session(browser, sid):
    owner = _owner(browser)
    if not sid or not get_store().owns(owner, sid):
        return (gr.skip(),) * 19
    return _open_session(browser, sid)


def on_new_session(browser):
    owner = _owner(browser) or uuid4().hex
    return _open_session({'owner': owner}, get_store().create_session(owner))


def on_session_save(browser, sid, frame, reference, history):
    """Persist the visible state; never raises into the page."""
    owner = _owner(browser) or uuid4().hex
    try:
        new_sid, forked, saved_at = svc.save_current(
            get_store(), owner, sid or '', svc.dataset_record(frame, EXAMPLES),
            svc.reference_record(reference, EXAMPLES), history)
        text = tr('已保存 · ') + _time.strftime('%H:%M:%S', _time.localtime(saved_at))
        if forked:
            text += tr('。数据或读取设置已更换，已另开新会话；原会话保留在列表里。')
        return (new_sid, _picker_update(owner, new_sid), _session_name(owner, new_sid),
                _status(text), {'owner': owner, 'last': new_sid})
    except Exception as exc:  # the page keeps working; the user is told the record was not saved
        return (sid, gr.skip(), gr.skip(), _status(tr('没有保存成功（{err}）。当前页面内容仍可使用，请稍后再试。', err=type(exc).__name__), 'error'),
                {'owner': owner, 'last': sid})


def on_session_rename(browser, sid, name):
    owner = _owner(browser)
    try:
        get_store().rename_session(owner, sid, name)
    except (ValueError, KeyError) as exc:
        return gr.skip(), gr.skip(), _status(str(exc), 'error')
    return _picker_update(owner, sid), _session_name(owner, sid), _status(tr('名称已更新'))


def on_delete_ask(browser, sid):
    name = _session_name(_owner(browser), sid)
    warn = ('<div class="delete-warn">' + tr('将永久删除「{name}」：它的分析记录、报告，以及没有其他会话使用的上传文件副本。'
                                              '删除后无法恢复。', name=escape(name)) + '</div>')
    return gr.update(visible=True), warn


def on_delete_cancel():
    return gr.update(visible=False)


def on_delete_confirm(browser, sid):
    owner, store = _owner(browser), get_store()
    try:
        store.delete_session(owner, sid)
    except KeyError:
        pass
    rest = store.list_sessions(owner)
    nxt = rest[0]['id'] if rest else store.create_session(owner)
    result = list(_open_session(browser, nxt))
    result[16] = _status(tr('会话已删除'))
    return tuple(result)


def on_session_import_upload(file_obj, sid=None, prior_frame=None):
    """Upload handler: if the file is exactly the one this session lost, resume the saved analyses."""
    path = _persist_path(file_obj)
    try:
        owner = get_store().owner_of(sid) if sid else None  # sid lives in server-side state, set only for owned sessions
        if prior_frame is None and path and owner:
            data = get_store().load_session(owner, sid)
            dataset = data['dataset']
            if (dataset and not dataset.get('sample') and data['history']['entries']
                    and sha256_of(path) == dataset['sha256']):
                return _open_from_data(data, forced_path=path)[0]
    except (OSError, KeyError):
        pass
    return on_import_upload(path)


DOMAIN_EXAMPLES = ['成绩','销售','股价','库存','问卷']
DOMAIN_QUESTIONS = {  # sheet names are the workbook's real (Chinese) sheet names; questions are translated
    '成绩':'数学的平均分是多少？',
    '销售':'按地区分组，用销售额（元）合计画柱状图。',
    '股价':'按日期每天的收盘价平均值画折线图，保留缺失值。示例是单一虚构股票。',
    '库存':'库存数量小于10的有多少条记录？',
    '问卷':'统计满意度每种取值的记录数。',
}


def on_domain_example(domain):
    if domain in (None,''):
        return (gr.skip(),)*12
    if domain not in DOMAIN_EXAMPLES:
        raise ValueError(tr('请选择列表中的示例。'))
    source = {'path':str(ROOT/'examples'/'domain_examples.xlsx'),'sample':True}
    return on_read_table(source,domain,1)


def on_domain_load(domain):
    return *on_domain_example(domain),(tr(DOMAIN_QUESTIONS[domain]) if domain in DOMAIN_QUESTIONS else gr.skip())


def _without_import_source(callback):
    def load_example():
        result = callback()
        return *result[:9],None,*result[9:]
    return load_example


def on_read_reference(reference,sheet,header_row):
    source = (reference or {}).get('source')
    return on_reference_upload(source['path'] if source else None,sheet,header_row)


def import_notes(source):
    if not source:
        return ''
    info = source.get('info',{})
    notes = []
    if info.get('sheet'):
        notes.append(tr('当前工作表：')+str(info['sheet']))
    notes.append(tr('列名在第 {n} 行；这一行以上的内容不参与分析。', n=source.get('header_row',1)))
    changes = info.get('column_changes',[])
    if changes:
        notes.append(tr('列名已整理：')+tr('；').join(tr('第 {p} 列 {old} → {new}', p=v["position"], old=v["original"] or tr('（空）'), new=v["column"]) for v in changes[:8])+(' …' if len(changes)>8 else ''))
    if source['format'] in {'xlsx','xls'}:
        notes.append(tr('公式只读取已保存的结果。修改过公式后，请在 Excel 中计算并保存再上传。'))
        notes.append(tr('百分比读取底层数值，例如 20% 读作 0.2；不会按显示格式自动换算单位。'))
    notes += [hint_message(h) for h in info.get('value_hints',[])[:6]]
    if info.get('encoding')=='gb18030':
        notes.append(tr('按 GB18030 编码读取。'))
    return '<div class="context-hint">'+'<br>'.join(escape(n) for n in notes)+'</div>'


def on_import_settings(source):
    sheets = (source or {}).get('sheets',[])
    return (gr.update(visible=bool(source),open=bool(sheets) or bool((source or {}).get('info',{}).get('column_changes')) or bool((source or {}).get('info',{}).get('value_hints'))),gr.update(choices=sheets,value=(source or {}).get('sheet') if sheets else None,visible=bool(sheets)),
            gr.update(value=(source or {}).get('header_row',1)),import_notes(source))


def on_reference_settings(reference):
    return on_import_settings((reference or {}).get('source'))


def on_session_office_example():
    return *on_office_example(), empty_history(), None


def on_session_reconciliation_example():
    return *on_reconciliation_example(), empty_history(), None


def on_session_rule_example():
    return *on_rule_example(), empty_history(), None


def on_session_consistency_example():
    return *on_consistency_example(), empty_history(), None


def on_session_clear():
    return *on_clear(), empty_history(), None


def _browser_secret():
    """Stable key for the browser-side owner token; created once next to the database."""
    path = data_dir() / 'browser.secret'
    try:
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(uuid4().hex + uuid4().hex, encoding='utf-8')
        return path.read_text(encoding='utf-8').strip()
    except OSError:
        return 'dataaudit-local'


USAGE_NOTES = [
    '涉及某一列时，请尽量使用表格里的列名。',
    '范围和类别检查需要你给出规则，不会自动设定业务标准。',
    '偏离较大的值不一定是错误；相关性不能说明因果。',
    '部分敏感字段按列名隐藏，这套规则不能识别所有敏感信息。',
    '每次最多进行 6 轮工具调用，重复调用时会停止。',
    '当前使用 Qwen、LangGraph 和 Pandas；计算记录可展开查看。',
]


def build_demo(lang='zh'):
    """One page per language ('zh' at /, 'en' at /en); every handler is tagged with that language."""
    token = LANG.set(lang)
    try:
        return bind_language(_build_demo(lang), lang)
    finally:
        LANG.reset(token)


def _build_demo(lang):
    initial = on_clear()
    initial_frame = initial[0]
    choices = distribution_columns(initial_frame) if initial_frame is not None else []
    with gr.Blocks(
        title=tr("DataAudit · 数据工作台"), analytics_enabled=False,
        theme=gr.themes.Base(primary_hue="indigo", secondary_hue="slate", neutral_hue="slate",
                             font=["system-ui", "sans-serif"], font_mono=["ui-monospace", "monospace"]),
        css=APP_CSS, delete_cache=(3600, 3600),
        js="() => { document.body.classList.remove('dark'); document.documentElement.style.colorScheme = 'light'; }",
    ) as demo:
        gr.HTML(header_html(lang), padding=False)
        frame_state = gr.State(value=initial_frame, time_to_live=3600)
        history_state = gr.State(value=empty_history(), time_to_live=3600)
        reference_state = gr.State(value=None, time_to_live=3600)
        source_state = gr.State(value=None,time_to_live=3600)
        session_state = gr.State(value='')
        browser_state = gr.BrowserState({'owner': '', 'last': ''}, storage_key='dataaudit-sessions-v1', secret=_browser_secret())
        with gr.Tabs(elem_id="main-tabs"):
            with gr.Tab(tr("工作台")):
                with gr.Row(elem_classes='session-bar'):
                    session_picker = gr.Dropdown(label=tr('当前会话'), show_label=False, choices=[], value=None, interactive=True,
                                                 scale=3, min_width=200, elem_id='session-picker', container=False)
                    new_session = gr.Button(tr('新建会话'), size='sm', scale=0, min_width=84, elem_id='new-session')
                    save_status = gr.HTML('', padding=False, elem_id='save-status')
                model_notice = gr.HTML('', padding=False, visible=False, elem_id='model-notice')
                with gr.Accordion(tr('管理会话 · 重命名与删除'), open=False, elem_id='session-manage'):
                    with gr.Row():
                        session_name = gr.Textbox(label=tr('会话名称'), max_lines=1, scale=3, elem_id='session-name')
                        rename_button = gr.Button(tr('保存名称'), size='sm', scale=0, min_width=84, elem_id='rename-session')
                        delete_button = gr.Button(tr('删除会话…'), size='sm', scale=0, min_width=84, elem_id='delete-session')
                    with gr.Group(visible=False, elem_id='delete-confirm') as delete_confirm:
                        delete_warning = gr.HTML('', padding=False)
                        with gr.Row():
                            delete_yes = gr.Button(tr('确认删除'), size='sm', variant='stop', elem_id='delete-yes')
                            delete_no = gr.Button(tr('取消'), size='sm', elem_id='delete-no')
                with gr.Row(elem_classes="data-actions"):
                    upload = gr.UploadButton(tr("上传表格"), type="filepath", file_types=[".csv",".tsv",".xlsx",".xls"], scale=0, min_width=112, elem_id="choose-csv")
                    with gr.Column(scale=2, min_width=180, elem_classes="file-info"):
                        dataset_status = gr.HTML(initial[1], padding=False)
                    clear = gr.Button(tr("移除"), size="sm", scale=0, min_width=34, elem_id="clear-file")
                with gr.Accordion(tr('示例文件 · 可选'),open=False,elem_id='sample-files'):
                    with gr.Row():
                        office = gr.Button(tr("订单示例"), size="sm", scale=0, min_width=66, elem_classes="sample-button")
                        reconciliation = gr.Button(tr("对账示例"), size="sm", scale=0, min_width=66, elem_classes="sample-button")
                        rules = gr.Button(tr("规则示例"), size="sm", scale=0, min_width=66, elem_classes="sample-button")
                        consistency = gr.Button(tr("格式示例"), size="sm", scale=0, min_width=66, elem_classes="sample-button")
                        domain_selector = gr.Dropdown(label=tr('其他示例'),show_label=False,choices=[(tr('更多示例…'),'')]+[(tr(name+'表'),name) for name in DOMAIN_EXAMPLES],value='',interactive=True,scale=0,min_width=130,elem_id='domain-examples')
                with gr.Accordion(tr('读取设置 · 工作表与表头'),visible=False,open=False,elem_id='import-settings') as import_panel:
                    with gr.Row():
                        import_sheet = gr.Dropdown(label=tr('工作表'),choices=[],visible=False,interactive=True)
                        import_header = gr.Number(label=tr('列名在第几行'),value=1,precision=0,minimum=1,maximum=100)
                        read_table = gr.Button(tr('按设置重新读取'),size='sm')
                    import_status = gr.HTML('',padding=False)
                gr.HTML('<div class="context-hint">' + tr('支持 Excel、CSV、TSV。列名可以是中文；默认第一行是列名，可在读取设置里调整。') + '</div>',padding=False)
                summary = gr.HTML(initial[2], padding=False)
                with gr.Row(elem_classes="work-grid"):
                    with gr.Column(scale=3, min_width=440, elem_classes="chart-card"):
                        with gr.Tabs(elem_id="chart-tabs", selected="distribution") as chart_tabs:
                            with gr.Tab(tr("空值分布"), id="missing"):
                                gr.HTML('<div class="chart-caption">' + tr('只展示存在空值的列，最多 8 列。') + '</div>', padding=False)
                                missing_plot = gr.Plot(initial[3], show_label=False)
                            with gr.Tab(tr("数值分布"), id="distribution"):
                                distribution_column = gr.Dropdown(label=tr("查看哪一列"), show_label=False, choices=choices,
                                                                  value=choices[0] if choices else None, elem_id="distribution-picker")
                                distribution_plot = gr.Plot(initial[5], show_label=False)
                            with gr.Tab(tr("生成的图表"), id="agent-chart"):
                                agent_plot = gr.Plot(empty_figure(tr('想画什么图？在右侧写下问题。')), show_label=False)
                                chart_download = gr.DownloadButton(tr('下载图表 · HTML'), visible=False, size='sm')
                        with gr.Accordion(tr("数据预览 · 前 5 行"), open=False, elem_id="data-preview"):
                            preview = gr.HTML(on_preview(initial_frame), padding=False)
                        with gr.Accordion(tr('数据概览 · 每列的情况'), open=False, elem_id='data-profile'):
                            profile = gr.HTML(profile_html(None), padding=False)
                        with gr.Accordion(tr('对照另一份表 · 可选'), open=False, elem_id='reference-panel') as reference_panel:
                            with gr.Row(elem_classes='reference-actions'):
                                reference_upload = gr.UploadButton(tr('选择参考表格'),type='filepath',file_types=['.csv','.tsv','.xlsx','.xls'],scale=0,min_width=120,elem_classes='reference-upload')
                                reference_example = gr.Button(tr('参考示例'),scale=0,min_width=80,size='sm',elem_classes='reference-clear')
                                reference_clear = gr.Button(tr('移除参考'),scale=0,min_width=80,size='sm',elem_classes='reference-clear')
                            reference_status = gr.HTML(on_reference_status(None),padding=False)
                            with gr.Accordion(tr('参考表读取设置'),visible=False,open=False) as reference_import_panel:
                                reference_sheet = gr.Dropdown(label=tr('参考工作表'),choices=[],visible=False,interactive=True)
                                reference_header = gr.Number(label=tr('参考表列名在第几行'),value=1,precision=0,minimum=1,maximum=100)
                                reference_read = gr.Button(tr('重新读取参考表'),size='sm')
                                reference_import_status = gr.HTML('',padding=False)
                            gr.HTML('<div class="context-hint">' + tr('选好参考表后，点「对照」，再开始分析。') + '</div>',padding=False)
                        with gr.Accordion(tr('本次分析记录 · 最近 8 次'), open=False, elem_id='session-history'):
                            history_picker = gr.Dropdown(label=tr('重新打开之前的结果'), choices=[], value=None, interactive=True)
                            gr.HTML('<div class="context-hint">' + tr('换数据或读取设置会另开新会话，原会话的记录保留。重新打开结果不会调用模型。') + '</div>', padding=False)
                    with gr.Column(scale=2, min_width=300, elem_classes="ask-panel"):
                        with gr.Row(elem_classes='question-heading'):
                            gr.HTML('<div class="section-heading"><h2>' + tr('问这份数据') + '</h2></div>', padding=False)
                            start_fresh = gr.Button(tr('新问题'), scale=0, min_width=62, size='sm', elem_id='new-question')
                        question = gr.Textbox(label=tr("想查的问题"), show_label=False,
                                              placeholder=tr("比如：按我指定的条件查行、汇总，或计算两列的比值。"), lines=3, elem_id="question")
                        gr.HTML('<div class="context-hint">' + tr('可以接着问，例如“改成平均值”。点「新问题」可从头开始。') + '</div>', padding=False)
                        suggestions = gr.Dropdown(choices=[], value=None, label=tr('试试这样问'), info=tr('根据列的类型生成，选一条填入问题框'), interactive=True,
                                                  visible=False, elem_id='suggestions')
                        with gr.Row(elem_classes="quick-row"):
                            quick_missing = gr.Button(tr("查空值"), size="sm", min_width=0, elem_classes="quick-button")
                            quick_duplicates = gr.Button(tr("查重复"), size="sm", min_width=0, elem_classes="quick-button")
                            quick_report = gr.Button(tr("写报告"), size="sm", min_width=0, elem_classes="quick-button")
                            quick_chart = gr.Button(tr("画图"), size="sm", min_width=0, elem_classes="quick-button")
                            quick_compare = gr.Button(tr('对照'),size='sm',min_width=0,elem_classes='quick-button')
                        submit = gr.Button(tr("开始分析"), variant="primary", elem_id="run-check")
                        gr.HTML('<div class="result-label">' + tr('分析结果') + '</div>', padding=False)
                        answer = gr.Markdown(elem_id="analysis-answer")
                        with gr.Row(elem_classes='artifact-actions'):
                            report_download = gr.DownloadButton(tr("下载报告 · Markdown"), visible=False, size="sm", elem_id="download-report")
                            record_download = gr.HTML('',visible=False,padding=False,elem_id='download-record')
                            table_download = gr.DownloadButton(tr('下载结果表 · CSV'), visible=False, size='sm', elem_id='download-table')
                            script_download = gr.DownloadButton(tr('下载复现脚本 · Python'), visible=False, size='sm', elem_id='download-script')
                        execution = gr.HTML(execution_html([]), padding=False, elem_id="execution-summary")
                        with gr.Accordion(tr("参数与原始结果"), open=False, elem_id="calculation-log"):
                            tool_log = gr.JSON(label=tr("调用记录"))
            with gr.Tab(tr("工具库 · 26")):
                gr.HTML(tools_catalog(), padding=False)
                with gr.Accordion(tr("使用说明与开发信息"), open=False):
                    gr.Markdown('\n'.join('- ' + tr(line) for line in USAGE_NOTES))
        gr.HTML('<div class="page-foot"><span>' + tr('DataAudit / 表格工作台') + '</span><span>' + tr('示例均为虚构数据 · 原表不会被改写') + '</span></div>', padding=False)
        outputs = [frame_state, dataset_status, summary, missing_plot, distribution_column,
                   distribution_plot, answer, tool_log, report_download, source_state, history_state, reference_state]
        upload_event = upload.upload(on_session_import_upload, inputs=[upload, session_state, frame_state], outputs=outputs, api_name='on_upload', concurrency_id="dataset_work", concurrency_limit=1)
        office_event = office.click(_without_import_source(on_session_office_example), outputs=outputs, api_name='on_office_example', concurrency_id="dataset_work", concurrency_limit=1)
        reconciliation_event = reconciliation.click(_without_import_source(on_session_reconciliation_example), outputs=outputs, api_name='on_reconciliation_example', concurrency_id="dataset_work", concurrency_limit=1)
        rules_event = rules.click(_without_import_source(on_session_rule_example), outputs=outputs, api_name='on_rule_example', concurrency_id="dataset_work", concurrency_limit=1)
        consistency_event = consistency.click(_without_import_source(on_session_consistency_example), outputs=outputs, api_name='on_consistency_example', concurrency_id="dataset_work", concurrency_limit=1)
        domain_event = domain_selector.input(on_domain_load,inputs=domain_selector,outputs=outputs+[question],api_name='on_domain_example',concurrency_id='dataset_work',concurrency_limit=1)
        domain_event.then(lambda:gr.update(value=''),outputs=domain_selector,queue=False,api_name=False)
        source_state.change(on_import_settings,inputs=source_state,outputs=[import_panel,import_sheet,import_header,import_status],queue=False)
        read_table_event = read_table.click(on_read_table,inputs=[source_state,import_sheet,import_header],outputs=outputs,concurrency_id='dataset_work',concurrency_limit=1)
        frame_state.change(on_preview, inputs=frame_state, outputs=preview, queue=False)
        frame_state.change(on_suggestions, inputs=frame_state, outputs=suggestions, queue=False)
        frame_state.change(lambda f: profile_html(f), inputs=frame_state, outputs=profile, queue=False)
        suggestions.input(on_suggestion_pick, inputs=suggestions, outputs=question, queue=False)
        tool_log.change(on_table_download, inputs=tool_log, outputs=table_download, queue=False)
        tool_log.change(on_script_download, inputs=[tool_log, frame_state], outputs=script_download, queue=False)
        tool_log.change(execution_html, inputs=tool_log, outputs=execution, queue=False)
        tool_log.change(on_agent_chart, inputs=tool_log, outputs=[agent_plot, chart_download, chart_tabs], queue=False)
        clear_event = clear.click(_without_import_source(on_session_clear), outputs=outputs, api_name='on_clear', concurrency_id="dataset_work", concurrency_limit=1)
        distribution_column.change(on_distribution_change, inputs=[distribution_column, frame_state], outputs=distribution_plot)
        submit_event = submit.click(on_session_submit_stream, inputs=[question, frame_state, history_state, reference_state],
                     outputs=[answer, tool_log, report_download, history_state], api_name='on_submit',
                     concurrency_id="dataset_work", concurrency_limit=1, show_progress='minimal')
        history_state.change(on_history_choices, inputs=history_state, outputs=history_picker, queue=False)
        reference_state.change(on_reference_status,inputs=reference_state,outputs=reference_status,queue=False)
        reference_state.change(on_reference_settings,inputs=reference_state,outputs=[reference_import_panel,reference_sheet,reference_header,reference_import_status],queue=False)
        reference_outputs = [reference_state, answer, tool_log, report_download, history_state]
        reference_upload_event = reference_upload.upload(on_reference_upload,inputs=reference_upload,outputs=reference_outputs,concurrency_id='dataset_work',concurrency_limit=1)
        reference_clear_event = reference_clear.click(on_reference_clear,outputs=reference_outputs,concurrency_id='dataset_work',concurrency_limit=1)
        reference_example_event = reference_example.click(on_reference_example,outputs=reference_outputs,concurrency_id='dataset_work',concurrency_limit=1)
        reference_read_event = reference_read.click(on_read_reference,inputs=[reference_state,reference_sheet,reference_header],outputs=reference_outputs,concurrency_id='dataset_work',concurrency_limit=1)
        history_picker_event = history_picker.input(on_restore_analysis, inputs=[history_picker, history_state],
                             outputs=[question, answer, tool_log, report_download, history_state],
                             concurrency_id='dataset_work', concurrency_limit=1)
        start_fresh_event = start_fresh.click(on_new_question, inputs=history_state,
                          outputs=[question, answer, tool_log, report_download, history_state],
                          concurrency_id='dataset_work', concurrency_limit=1)
        quick_missing.click(lambda: tr("哪些列有空值？请统计数量和比例。"), outputs=question, queue=False, api_name=False)
        quick_duplicates.click(lambda: tr("有多少完全重复的记录？"), outputs=question, queue=False, api_name=False)
        quick_report.click(lambda: tr("帮我生成一份检查报告。"), outputs=question, queue=False, api_name=False)
        quick_chart.click(on_chart_question, inputs=frame_state, outputs=question, queue=False)
        quick_compare.click(on_compare_question,outputs=[question,reference_panel],queue=False)
        submit_event.then(on_current_export, inputs=[history_state,tool_log], outputs=record_download,
                          queue=False, api_name='on_current_export')
        save_inputs = [browser_state, session_state, frame_state, reference_state, history_state]
        save_outputs = [session_state, session_picker, session_name, save_status, browser_state]
        open_outputs = outputs + [question, session_state, session_picker, session_name, save_status, browser_state, delete_confirm]
        boot_event = demo.load(on_boot, inputs=browser_state, outputs=open_outputs, api_name=False,
                               concurrency_id='dataset_work', concurrency_limit=1, show_progress='hidden')
        demo.load(on_model_status, outputs=model_notice, queue=False, api_name=False, show_progress='hidden')
        pick_event = session_picker.input(on_pick_session, inputs=[browser_state, session_picker], outputs=open_outputs,
                                          api_name=False, concurrency_id='dataset_work', concurrency_limit=1, show_progress='hidden')
        new_event = new_session.click(on_new_session, inputs=browser_state, outputs=open_outputs,
                                      api_name=False, concurrency_id='dataset_work', concurrency_limit=1, show_progress='hidden')
        rename_button.click(on_session_rename, inputs=[browser_state, session_state, session_name],
                            outputs=[session_picker, session_name, save_status], api_name=False)
        delete_button.click(on_delete_ask, inputs=[browser_state, session_state], outputs=[delete_confirm, delete_warning], api_name=False)
        delete_no.click(on_delete_cancel, outputs=delete_confirm, api_name=False)
        delete_event = delete_yes.click(on_delete_confirm, inputs=[browser_state, session_state], outputs=open_outputs,
                                        api_name=False, concurrency_id='dataset_work', concurrency_limit=1)
        for opened_event in [boot_event, pick_event, new_event, delete_event]:
            opened_event.then(on_current_export, inputs=[history_state, tool_log], outputs=record_download,
                              queue=False, api_name=False)
        submit_event.then(on_session_save, inputs=save_inputs, outputs=save_outputs, queue=False, api_name=False)
        for completed_event in [upload_event,office_event,reconciliation_event,rules_event,consistency_event,
                                clear_event,reference_upload_event,reference_clear_event,reference_example_event,
                                history_picker_event,start_fresh_event,read_table_event,reference_read_event,domain_event]:
            completed_event.then(on_current_export,inputs=[history_state,tool_log],outputs=record_download,
                                 queue=False,api_name=False)
            completed_event.then(on_session_save, inputs=save_inputs, outputs=save_outputs, queue=False, api_name=False)
    return demo


def build_web_app():
    """Chinese page at /, English page at /en (each with its own API); downloads are shared."""
    from src.artifact_download import record_download_app
    from fastapi.responses import RedirectResponse
    app = record_download_app(RECORD_DIR)

    @app.get('/en', include_in_schema=False)
    def english_without_slash():
        return RedirectResponse('en/')  # relative, so it also works behind a path prefix

    options = dict(max_file_size=f"{MAX_UPLOAD_MB}mb", show_error=False,
                   allowed_paths=[str(REPORT_DIR), str(CHART_DIR), str(RECORD_DIR), str(EXPORT_DIR)])
    app = gr.mount_gradio_app(app, build_demo('en').queue(default_concurrency_limit=1), path='/en', **options)
    return gr.mount_gradio_app(app, build_demo('zh').queue(default_concurrency_limit=1), path='/', **options)


if __name__ == "__main__":
    import uvicorn
    host = os.getenv('DATAAUDIT_HOST', '127.0.0.1')  # set 0.0.0.0 only behind your own access control
    port = int(os.getenv('DATAAUDIT_PORT', '7860'))
    status = endpoint_status()
    shown = '127.0.0.1' if host == '0.0.0.0' else host
    print(f"DataAudit → http://{shown}:{port}  (English: http://{shown}:{port}/en)   model: {status['model']} · {status['message']}")
    uvicorn.run(build_web_app(), host=host, port=port)
