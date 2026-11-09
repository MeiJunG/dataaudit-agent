"""Minimal two-language support (Chinese source text, English translations).

`tr('中文模板 {x}', x=1)` returns the Chinese template, or its English entry when the current
language is English. The Chinese text is the key, so untranslated strings fall back to Chinese
(tests check that every key used in the code has an English entry).

The current language lives in a ContextVar. The web app builds one page per language and tags
each event handler with its page's language (see `bind_language`), so concurrent visitors of the
two pages never share it.
"""
from __future__ import annotations

import contextvars
import functools
import inspect

LANG = contextvars.ContextVar('dataaudit_lang', default='zh')


def current():
    return LANG.get()


def tr(text, **values):
    template = EN.get(text, text) if LANG.get() == 'en' else text
    return template.format(**values) if values else template


def using(lang, fn):
    """Wrap fn so it (and generator steps) run with the given language."""
    if inspect.isgeneratorfunction(fn):
        @functools.wraps(fn)
        def gen(*args, **kwargs):
            token = LANG.set(lang)
            try:
                iterator = fn(*args, **kwargs)
            finally:
                LANG.reset(token)
            while True:
                token = LANG.set(lang)
                try:
                    value = next(iterator)
                except StopIteration:
                    return
                finally:
                    LANG.reset(token)
                yield value
        return gen

    @functools.wraps(fn)
    def plain(*args, **kwargs):
        token = LANG.set(lang)
        try:
            return fn(*args, **kwargs)
        finally:
            LANG.reset(token)
    return plain


def bind_language(demo, lang):
    """Tag every registered event handler of a Gradio Blocks app with one language."""
    for block_fn in demo.fns.values():
        if block_fn.fn is not None and not getattr(block_fn.fn, '_dataaudit_lang', None):
            block_fn.fn = using(lang, block_fn.fn)
            block_fn.fn._dataaudit_lang = lang
    return demo


EN = {}  # filled from src/i18n_en.py
from .i18n_en import EN as _EN  # noqa: E402
EN.update(_EN)
