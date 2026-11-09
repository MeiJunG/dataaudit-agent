import pytest

from app import on_upload


@pytest.mark.parametrize('kind', ['new', 'cleared', 'invalid'])
def test_upload_invalidates_previous_answer_trace_and_report(tmp_path, kind):
    path = tmp_path / 'data.csv'
    path.write_text('amount,region\n10,East\n20,West\n', encoding='utf-8')
    source = str(path) if kind == 'new' else None if kind == 'cleared' else str(tmp_path / 'absent.csv')
    result = on_upload(source)
    assert len(result) == 9
    assert result[6] == ''
    assert result[7] == []
    assert result[8]['value'] is None and result[8]['visible'] is False
    if kind == 'new':
        assert result[0].shape == (2, 2)
    else:
        assert result[0] is None
