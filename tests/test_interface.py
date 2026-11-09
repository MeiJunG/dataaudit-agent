import pytest

from app import on_clear, on_office_example, on_reconciliation_example, on_rule_example
from src.interface import file_status


@pytest.mark.parametrize('callback,shape', [(on_office_example, (9, 6)), (on_reconciliation_example, (8, 4)), (on_rule_example, (8, 4))])
def test_example_actions_load_real_data_and_reset_previous_analysis(callback, shape):
    result = callback()
    assert result[0].shape == shape
    assert result[6:8] == ('', [])
    assert result[8]['value'] is None and result[8]['visible'] is False
    cleared = on_clear()
    assert cleared[0] is None and cleared[6:8] == ('', [])


def test_filename_is_displayed_as_text_not_html():
    result = file_status('<script>alert(1)</script>.csv', rows=2)
    assert '<script>' not in result
    assert '&lt;script&gt;' in result
