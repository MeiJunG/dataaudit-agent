import ast
import glob
import re
from pathlib import Path

import pandas as pd
import pytest

import app
from src import i18n
from src.i18n import EN, LANG, tr, using

ROOT = Path(__file__).resolve().parents[1]
CJK = re.compile('[一-鿿]')


def literal_keys():
    keys = set()
    for path in [ROOT / 'app.py', *sorted(p for p in (ROOT / 'src').glob('*.py') if not p.name.startswith('._'))]:
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'tr' and node.args:
                arg = node.args[0]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    keys.add(arg.value)
    return keys


def dynamic_keys():
    from src import presentation, suggestions, table_results, data_manager
    keys = set(presentation.TOOL_LABELS.values()) | set(suggestions.KIND_LABEL.values())
    keys |= set(table_results.METRIC_NAMES.values()) | set(table_results.ROW_OPERATIONS.values())
    keys |= set(app.USAGE_NOTES) | set(app.DOMAIN_QUESTIONS.values()) | {n + '表' for n in app.DOMAIN_EXAMPLES}
    keys |= {data_manager.EMPTY_HEADER_ERROR, data_manager.SHEET_COUNT_ERROR, '当前表', '参考表'}
    return keys


def test_every_key_used_in_code_has_english_text():
    missing = sorted(k for k in literal_keys() | dynamic_keys() if k not in EN and (CJK.search(k) or '（' in k))
    assert missing == []


def test_english_templates_keep_the_same_placeholders():
    field = re.compile(r'\{(\w+)\}')
    for zh, en in EN.items():
        assert set(field.findall(zh)) == set(field.findall(en)), zh
        assert not CJK.search(en) or any(name in en for name in ('数学', '地区', '销售额', '收盘价', '库存数量', '满意度')), en


def test_tr_defaults_to_chinese_and_switches_by_context():
    assert tr('开始分析') == '开始分析'
    token = LANG.set('en')
    try:
        assert tr('开始分析') == 'Analyse'
        assert tr('第 {n} 步', n=3) == 'Step 3'
        assert tr('不存在的文字') == '不存在的文字'  # untranslated text falls back to the source
    finally:
        LANG.reset(token)


def test_using_wraps_plain_and_generator_handlers():
    plain = using('en', lambda: tr('开始分析'))
    assert plain() == 'Analyse' and LANG.get() == 'zh'

    def steps():
        yield tr('开始分析')
        yield tr('新问题')
    assert list(using('en', steps)()) == ['Analyse', 'New question']
    assert LANG.get() == 'zh'


def test_english_page_builds_with_english_labels_and_handlers():
    demo = app.build_demo('en')
    labels = [b.label for b in demo.blocks.values() if getattr(b, 'label', None)]
    assert 'Analyse' not in labels  # buttons use value, not label
    values = [getattr(b, 'value', None) for b in demo.blocks.values()]
    assert 'Analyse' in values and 'Upload table' in [getattr(b, 'label', None) for b in demo.blocks.values()]
    html = ' '.join(str(v) for v in values if isinstance(v, str))
    assert 'Understand every table.' in html and 'href="../"' in html
    assert not any(CJK.search(str(l)) for l in labels if l not in ('当前会话',))
    assert all(getattr(f.fn, '_dataaudit_lang', None) == 'en' for f in demo.fns.values() if f.fn is not None)


def test_chinese_page_is_unchanged():
    demo = app.build_demo('zh')
    values = [getattr(b, 'value', None) for b in demo.blocks.values()]
    assert '开始分析' in values and '上传表格' in [getattr(b, 'label', None) for b in demo.blocks.values()]
    assert all(getattr(f.fn, '_dataaudit_lang', None) == 'zh' for f in demo.fns.values() if f.fn is not None)


def test_english_handlers_produce_english_output():
    frame = pd.DataFrame({'region': ['East', 'West', 'East', 'West'], 'amount': [1.0, 2.0, None, 4.0]})
    english = using('en', app.on_submit)
    answer, _, _ = english('', frame)
    assert answer == 'Type a question, or pick a common one.'
    suggestions = using('en', app.on_suggestions)(frame)['choices']
    assert any('Group by region' in s for s in suggestions)
    status = using('en', lambda: app.overview_html(frame))()
    assert 'Blank cells' in status and '空白' not in status


def test_web_app_serves_both_languages():
    from fastapi.testclient import TestClient
    client = TestClient(app.build_web_app())
    zh = client.get('/')
    en = client.get('/en/')
    assert zh.status_code == 200 and en.status_code == 200
