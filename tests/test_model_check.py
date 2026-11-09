import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

import app
from src import model_check




def named(name, text=''):
    return type(name, (Exception,), {})(text)


def test_friendly_errors_cover_connection_auth_and_name():
    assert '连接不上' in model_check.friendly_model_error(named('APIConnectionError', 'Connection error.'))
    assert 'API Key' in model_check.friendly_model_error(named('AuthenticationError'))
    assert 'MODEL_NAME' in model_check.friendly_model_error(named('NotFoundError'))
    assert model_check.friendly_model_error(ValueError('bad column')) is None


def serve(handler):
    server = HTTPServer(('127.0.0.1', 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


@pytest.fixture(autouse=True)
def no_cache():
    model_check._CACHE.update(at=0.0, value=None)
    yield
    model_check._CACHE.update(at=0.0, value=None)


def models_handler(ids, code=200):
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(code)
            self.end_headers()
            self.wfile.write(json.dumps({'data': [{'id': i} for i in ids]}).encode())

        def log_message(self, *a):
            pass
    return H


def test_endpoint_status_states(monkeypatch):
    ok = serve(models_handler(['qwen2.5-7b-instruct']))
    monkeypatch.setenv('OPENAI_BASE_URL', f'http://127.0.0.1:{ok.server_port}/v1')
    monkeypatch.setenv('MODEL_NAME', 'qwen2.5-7b-instruct')
    assert model_check.endpoint_status(max_age=0)['ok']
    monkeypatch.setenv('MODEL_NAME', 'other-model')
    status = model_check.endpoint_status(max_age=0)
    assert not status['ok'] and 'other-model' in status['message']
    denied = serve(models_handler([], code=401))
    monkeypatch.setenv('OPENAI_BASE_URL', f'http://127.0.0.1:{denied.server_port}/v1')
    assert 'API Key' in model_check.endpoint_status(max_age=0)['message']
    monkeypatch.setenv('OPENAI_BASE_URL', 'http://127.0.0.1:9/v1')
    assert not model_check.endpoint_status(timeout=1, max_age=0)['ok']
    ok.shutdown(); denied.shutdown()


def test_page_notice_only_when_model_unusable(monkeypatch):
    monkeypatch.setattr(app, 'endpoint_status', lambda: {'ok': True, 'model': 'm', 'message': '模型已连接'})
    assert app.on_model_status()['visible'] is False
    monkeypatch.setattr(app, 'endpoint_status', lambda: {'ok': False, 'model': 'm', 'message': '无法连接<b>'})
    update = app.on_model_status()
    assert update['visible'] and '&lt;b&gt;' in update['value'] and 'model_check' in update['value']


def test_submit_shows_friendly_message_for_model_errors(monkeypatch):
    import pandas as pd

    def broken(*a, **k):
        raise named('APIConnectionError', 'Connection error.')
    monkeypatch.setattr(app, 'run_agent', broken)
    answer, log, _ = app.on_submit('q', pd.DataFrame({'a': [1]}))
    assert answer.startswith('连接不上模型服务') and log == []
