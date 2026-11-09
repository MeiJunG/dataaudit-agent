import pandas as pd

import app
from src import agent
from src.session_history import empty_history


def test_progress_html_lists_real_events_and_escapes():
    events = [{'phase': 'tool_start', 'tool': '<x>', 'step': 1}, {'phase': 'tool_done', 'tool': '<x>', 'step': 1, 'status': 'ok'},
              {'phase': 'tool_start', 'tool': 'b', 'step': 2}]
    html = app.progress_html(events, app._time.monotonic())
    assert '&lt;x&gt;' in html and '<x>' not in html and '第 2 步' in html and 'class="run"' in html
    assert '正在理解问题' in app.progress_html([], app._time.monotonic())


def test_stream_yields_progress_then_final(monkeypatch):
    def slow(question, frame, **kwargs):
        cb = agent.PROGRESS.get()
        cb({'phase': 'tool_start', 'tool': 't', 'step': 1})
        import time
        time.sleep(0.7)
        cb({'phase': 'tool_done', 'tool': 't', 'step': 1, 'status': 'ok'})
        return 'done', [{'step': 1, 'tool': 't', 'status': 'ok', 'arguments': {}, 'result': 'r'}]

    monkeypatch.setattr(app, 'run_agent', slow)
    monkeypatch.setattr(app, 'save_report_from_trace', lambda *a, **k: None)
    outputs = list(app.on_session_submit_stream('q', pd.DataFrame({'a': [1]}), empty_history()))
    assert len(outputs) >= 2
    assert 'run-progress' in outputs[0][0] and outputs[0][1] is not None
    final = outputs[-1]
    assert final[0] == 'done' and len(final) == 4


def test_stream_propagates_errors_as_message(monkeypatch):
    # run errors are already converted into a message by on_submit; no-frame path is immediate
    outputs = list(app.on_session_submit_stream('q', None, empty_history()))
    assert 'done' not in outputs[-1][0] and outputs[-1][1] == []


def test_run_agent_reports_tool_events(monkeypatch):
    seen = []
    graph_events = []
    monkeypatch.setattr(agent, '_make_graph', lambda *a, **k: type('G', (), {'invoke': lambda self, *x, **y: (graph_events.append(k.get('on_progress')) or
                                                                                                           {'messages': [agent.AIMessage(content='ok')], 'tool_log': []})})())
    token = agent.PROGRESS.set(seen.append)
    try:
        agent.run_agent('q', pd.DataFrame({'a': [1]}))
    finally:
        agent.PROGRESS.reset(token)
    assert graph_events[0] is not None
