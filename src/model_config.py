"""Environment-based model request options for reproducible, opt-in model comparisons."""
from __future__ import annotations

import math
import os
from collections.abc import Mapping


def request_options(environment: Mapping[str, str] | None = None) -> dict:
    env = os.environ if environment is None else environment
    temperature = float(env.get('LLM_TEMPERATURE', '0'))
    if not math.isfinite(temperature) or not 0 <= temperature <= 2:
        raise ValueError('LLM_TEMPERATURE must be a finite number in 0..2.')
    result = {'temperature': temperature}
    if env.get('LLM_TOP_P'):
        top_p = float(env['LLM_TOP_P'])
        if not math.isfinite(top_p) or not 0 < top_p <= 1:
            raise ValueError('LLM_TOP_P must be in (0, 1].')
        result['top_p'] = top_p
    thinking = env.get('LLM_ENABLE_THINKING', '').strip().lower()
    if thinking:
        if thinking not in {'true', 'false'}:
            raise ValueError('LLM_ENABLE_THINKING must be true, false, or unset.')
        result['extra_body'] = {'chat_template_kwargs': {'enable_thinking': thinking == 'true'}}
    return result
