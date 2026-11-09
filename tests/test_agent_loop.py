import json

import pandas as pd
from langchain_core.messages import AIMessage, ToolMessage

from src import agent


def test_agent_consumes_tool_observation_before_final_answer(monkeypatch):
    seen = []

    class LocalModel:
        def __init__(self, **kwargs):
            pass

        def bind_tools(self, tools):
            return self

        def invoke(self, messages):
            seen.append(messages)
            if len(seen) == 1:
                return AIMessage(content='', tool_calls=[{
                    'name': 'check_missing_values', 'args': {}, 'id': 'call-1'}])
            assert isinstance(messages[-1], ToolMessage)
            observation = json.loads(messages[-1].content)
            assert observation['by_column'][0]['missing_count'] == 1
            return AIMessage(content='amount has 1 missing value.')

    monkeypatch.setattr(agent, 'ChatOpenAI', LocalModel)
    answer, trace = agent.run_agent('Check missing values.', pd.DataFrame({'amount': [1, None]}))
    assert answer == 'amount has 1 missing value.'
    assert len(seen) == 2
    assert trace[0]['status'] == 'ok'


def test_truncated_report_answer_keeps_complete_artifact(monkeypatch):
    class LimitedModel:
        def __init__(self, **kwargs):
            self.calls = 0

        def bind_tools(self, tools):
            return self

        def invoke(self, messages):
            self.calls += 1
            if self.calls == 1:
                return AIMessage(content='', tool_calls=[{
                    'name': 'generate_quality_report', 'args': {}, 'id': 'report-1'}])
            return AIMessage(content='incomplete sentence', response_metadata={'finish_reason': 'length'})

    monkeypatch.setattr(agent, 'ChatOpenAI', LimitedModel)
    answer, trace = agent.run_agent('Generate report', pd.DataFrame({'amount': [1, None]}))
    assert '下载完整报告' in answer
    assert trace[0]['report_markdown'].endswith('data errors or causation.')


def test_twelve_tool_round_budget_reaches_own_limit(monkeypatch):
    class PersistentModel:
        def __init__(self, **kwargs):
            self.calls = 0

        def bind_tools(self, tools):
            return self

        def invoke(self, messages):
            self.calls += 1
            return AIMessage(content='', tool_calls=[{
                'name': 'analyze_distribution',
                'args': {'column': 'x', 'top_k': self.calls}, 'id': f'call-{self.calls}'}])

    monkeypatch.setattr(agent, 'ChatOpenAI', PersistentModel)
    answer, trace = agent.run_agent('Analyze x', pd.DataFrame({'x': [1, 2]}), max_steps=12)
    assert len(trace) == 12
    assert 'tool-call limit' in answer


def test_failed_tool_cannot_be_followed_by_fabricated_data_conclusions(monkeypatch):
    class FailingModel:
        def __init__(self, **kwargs):
            self.calls = 0

        def bind_tools(self, tools):
            return self

        def invoke(self, messages):
            self.calls += 1
            if self.calls == 1:
                return AIMessage(content='', tool_calls=[{
                    'name': 'compare_columns', 'args': {'left_column': 'absent', 'right_column': 'x'},
                    'id': 'bad-1'}])
            return AIMessage(content='942 rows matched and 37 rows differed.')

    monkeypatch.setattr(agent, 'ChatOpenAI', FailingModel)
    answer, trace = agent.run_agent('Compare columns', pd.DataFrame({'x': [1]}))
    assert trace[0]['status'] == 'error'
    assert '942' not in answer and '37' not in answer
    assert '没有取得可用的工具结果' in answer


def test_final_answer_without_any_tool_evidence_does_not_claim_numbers(monkeypatch):
    class UnsupportedModel:
        def __init__(self, **kwargs):
            pass

        def bind_tools(self, tools):
            return self

        def invoke(self, messages):
            return AIMessage(content='The CSV has 999 missing cells.')

    monkeypatch.setattr(agent, 'ChatOpenAI', UnsupportedModel)
    answer, trace = agent.run_agent('How many cells are missing?', pd.DataFrame({'x': [None]}))
    assert trace == []
    assert '999' not in answer and '没有取得可用的工具结果' in answer


def test_successful_business_answer_uses_observations_instead_of_model_numbers(monkeypatch):
    class InaccurateModel:
        def __init__(self, **kwargs):
            self.calls = 0

        def bind_tools(self, tools):
            return self

        def invoke(self, messages):
            self.calls += 1
            if self.calls == 1:
                return AIMessage(content='', tool_calls=[{'name': 'check_numeric_range',
                    'args': {'column': 'amount', 'minimum': 0, 'maximum': 250}, 'id': 'range-1'}])
            return AIMessage(content='There are 942 out-of-range values.')

    monkeypatch.setattr(agent, 'ChatOpenAI', InaccurateModel)
    answer, trace = agent.run_agent('检查 amount 范围', pd.DataFrame({'amount': [0, 100, 300]}))
    assert '942' not in answer
    assert '共 1 个超限' in answer
    assert trace[0]['structured_result']['violation_count'] == 1
