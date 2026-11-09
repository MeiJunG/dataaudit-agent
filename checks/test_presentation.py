import unittest

from src.business_results import render_business_answer
from src.check_logic import check_conditional_values, check_date_pairs, check_text_values
from src.presentation import execution_html, preview_html


class PresentationChecks(unittest.TestCase):
    def test_preview_masks_sensitive_data_and_escapes_html(self):
        markup = preview_html(['email', '<column>'], [['private@example.com', '<script>bad</script>']], hidden={'email'})
        self.assertNotIn('private@example.com', markup)
        self.assertNotIn('<script>', markup)
        self.assertIn('&lt;script&gt;', markup)
        self.assertIn('已隐藏', markup)

    def test_preview_limits_are_real(self):
        markup = preview_html([str(i) for i in range(10)], [[str(i)] * 10 for i in range(8)])
        self.assertEqual(markup.count('<th>'), 8)
        self.assertEqual(markup.count('<td '), 40)

    def test_trace_has_human_labels_without_raw_results(self):
        markup = execution_html([{'tool':'check_date_order','status':'ok','duration_ms':2.8,'result':'secret'}])
        self.assertIn('核对日期先后', markup)
        self.assertIn('3 ms', markup)
        self.assertNotIn('secret', markup)

    def test_trace_escapes_unknown_tool_and_marks_errors(self):
        markup = execution_html([{'tool':'<b>bad</b>','status':'error'}])
        self.assertIn('&lt;b&gt;', markup)
        self.assertIn('未完成', markup)
        self.assertIn('计算完成后', execution_html([]))

    def test_new_renderers_use_actual_observations(self):
        cases = [
            ('check_text_quality', {'fields':[{'column':'status', **check_text_values(['done',' Done '])}]}, '写法合并组'),
            ('check_required_if', {'condition_column':'status','equals':'done',**check_conditional_values(['done'],{'amount':[None]},'done')}, '1 行存在必填项缺失'),
            ('check_date_order', {'start_column':'order','end_column':'ship',**check_date_pairs(['2026-10-02'],['2026-10-01'])}, '共 1 行不符合规则'),
        ]
        for tool, result, expected in cases:
            trace = [{'tool':tool,'step':1,'status':'ok','structured_result':result}]
            self.assertIn(expected, render_business_answer(trace,'检查'))


if __name__ == '__main__':
    unittest.main()
