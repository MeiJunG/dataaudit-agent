from src.agent import _is_repeated_tool_round


def test_repeated_tool_round_is_detected_after_same_call_completed():
    log = [{"tool": "check_missing_values", "arguments": {}}]
    repeated = [{"name": "check_missing_values", "args": {}}]
    new_call = [{"name": "check_duplicates", "args": {}}]

    assert _is_repeated_tool_round(repeated, log)
    assert not _is_repeated_tool_round(new_call, log)
    assert not _is_repeated_tool_round([], log)


def test_repeated_tool_round_compares_arguments_not_only_tool_name():
    log = [{"tool": "detect_outliers", "arguments": {"column": "age"}}]

    assert not _is_repeated_tool_round(
        [{"name": "detect_outliers", "args": {"column": "spend"}}], log)


def test_schema_context_is_bounded_and_never_contains_sample_values():
    import pandas as pd
    from src.agent import _dataset_context

    frame = pd.DataFrame({'region': ['private-record-value'], 'status': ['another-private-value']})
    context = _dataset_context(frame)
    assert 'region' in context and 'status' in context
    assert 'private-record-value' not in context
    assert 'another-private-value' not in context
    long = pd.DataFrame({f'{i}_' + 'x' * 100: [1] for i in range(100)})
    assert len(_dataset_context(long, budget=500)) < 1000
