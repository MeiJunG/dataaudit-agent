from src.agent import _tool_entry, _tool_failed
from src.reports import save_report_from_trace


def test_complete_report_survives_preview_truncation_and_is_saved(tmp_path):
    report = '# Report\n' + 'Verified aggregate results.\n' * 1000
    entry = _tool_entry('generate_quality_report', {}, report, 'ok', 1, 1.25)
    assert len(entry['result']) == 4000
    path = save_report_from_trace([entry], tmp_path)
    assert path.read_text(encoding='utf-8') == report
    assert save_report_from_trace([], tmp_path) is None


def test_json_error_observations_are_failures():
    assert _tool_failed('{"error": "Unknown field"}')
    assert not _tool_failed('{"rows": 10}')
    assert not _tool_failed('# Report')
