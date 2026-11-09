"""Check that the configured OpenAI-compatible model endpoint can serve this agent.

Run `python -m src.model_check` after editing `.env`. It checks, in order: the endpoint answers,
the API key is accepted, the model name exists (when the server lists models), and the model
returns a function call when one is required (the agent depends on tool calling).
Nothing from your tables is sent; the test prompt is a fixed sentence.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

from .i18n import tr, LANG

_CACHE = {'at': 0.0, 'value': None}


def settings():
    return {'base_url': os.getenv('OPENAI_BASE_URL', 'http://127.0.0.1:8080/v1').rstrip('/'),
            'model': os.getenv('MODEL_NAME', 'qwen2.5-7b-instruct'),
            'api_key': os.getenv('OPENAI_API_KEY', 'local')}


def _get(url, key, timeout):
    request = urllib.request.Request(url, headers={'Authorization': f'Bearer {key}'})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - URL comes from the operator's .env
        return json.loads(response.read().decode('utf-8') or '{}')


def endpoint_status(timeout=3.0, max_age=60.0):
    """Cheap reachability check for the page: {'ok', 'message', 'model'}; cached for max_age seconds."""
    now = time.monotonic()
    if _CACHE['value'] is not None and now - _CACHE['at'] < max_age:
        return _CACHE['value']
    cfg = settings()
    try:
        data = _get(cfg['base_url'] + '/models', cfg['api_key'], timeout)
        ids = [m.get('id') for m in data.get('data', []) if isinstance(m, dict)]
        if ids and cfg['model'] not in ids and not any(cfg['model'] in (i or '') for i in ids):
            value = {'ok': False, 'model': cfg['model'], 'message': tr('模型服务可以连接，但没有找到模型 {m}。', m=cfg['model'])}
        else:
            value = {'ok': True, 'model': cfg['model'], 'message': tr('模型已连接')}
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            value = {'ok': False, 'model': cfg['model'], 'message': tr('API Key 未被接受，请检查 OPENAI_API_KEY。')}
        else:  # some providers do not offer /models; the real call decides
            value = {'ok': True, 'model': cfg['model'], 'message': tr('模型服务可以连接')}
    except (urllib.error.URLError, OSError, ValueError):
        value = {'ok': False, 'model': cfg['model'], 'message': tr('无法连接模型服务（{url}）。', url=cfg['base_url'])}
    _CACHE.update(at=now, value=value)
    return value


def friendly_model_error(exc):
    """Plain-language message for model connection/auth/name errors, or None for other errors."""
    name = type(exc).__name__
    text = str(exc)
    if name in {'APIConnectionError', 'APITimeoutError', 'ConnectError', 'ConnectTimeout'} or 'Connection error' in text:
        return tr('连接不上模型服务。请确认 OPENAI_BASE_URL 指向一个正在运行的 OpenAI 兼容接口。')
    if name in {'AuthenticationError', 'PermissionDeniedError'}:
        return tr('API Key 未被接受。请检查 OPENAI_API_KEY。')
    if name == 'NotFoundError':
        return tr('模型服务找不到这个模型。请检查 MODEL_NAME。')
    if name == 'RateLimitError':
        return tr('模型服务暂时限流或额度不足，请稍后再试。')
    return None


def full_check():
    """Run every check and print a report; return a process exit code."""
    from langchain_core.messages import HumanMessage
    from langchain_core.tools import StructuredTool

    cfg = settings()
    print(tr('接口地址  {url}', url=cfg['base_url']) + '\n' + tr('模型名称  {m}', m=cfg['model']))
    status = endpoint_status(timeout=8, max_age=0)
    print(('✓ ' if status['ok'] else '× ') + status['message'])
    if not status['ok']:
        return 1

    def record_answer(answer: int) -> int:
        """Record the numeric answer."""
        return answer

    from .agent import _base_llm
    tool = StructuredTool.from_function(record_answer)
    started = time.perf_counter()
    try:
        reply = _base_llm(max_tokens=64).bind_tools([tool], tool_choice='record_answer').invoke(
            [HumanMessage(content='What is 2 + 3? Use the function to record the answer.')])
    except Exception as exc:  # report, do not crash
        print('× ' + tr('调用失败：') + (friendly_model_error(exc) or f'{type(exc).__name__}: {exc}'))
        return 1
    seconds = time.perf_counter() - started
    calls = reply.tool_calls or []
    if calls and calls[0]['name'] == 'record_answer':
        print('✓ ' + tr('支持函数调用（{s} 秒，参数 {args}）', s=f'{seconds:.1f}', args=calls[0].get('args')))
        print(tr('可以启动：python app.py'))
        return 0
    print('× ' + tr('模型回复了文字，但没有按要求调用函数。这个 Agent 依赖函数调用（tool calling），请换一个支持的模型或服务端参数。'))
    return 1


if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()
    if os.getenv('DATAAUDIT_LANG', '').lower().startswith('en'):
        LANG.set('en')
    sys.exit(full_check())
