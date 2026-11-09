import json
import unittest

from src.session_history import (CONTEXT_BYTES, add_analysis, empty_history, history_choices,
                                 new_question, select_analysis, selection_context)


def log(**args):
    return [{'tool':'create_chart', 'status':'ok', 'arguments':args,
             'result':'PRIVATE_OBSERVATION', 'structured_result':{'private':'HIDDEN_RESULT'}}]


class SessionHistoryChecks(unittest.TestCase):
    def test_bounds_do_not_mutate_previous_state(self):
        initial = empty_history()
        state = initial
        for i in range(10):
            state = add_analysis(state, f'Question {i}', 'Answer', log(x='region'))
        self.assertEqual(initial, empty_history())
        self.assertEqual(len(state['entries']), 8)
        self.assertEqual(state['entries'][0]['question'], 'Question 2')
        self.assertEqual(history_choices(state)[0][1], state['active_id'])

    def test_context_excludes_prior_answers_results_and_paths(self):
        state = add_analysis(None, 'Draw region totals', 'PRIVATE_ANSWER', log(x='region', y='amount'), '/private/report')
        context = selection_context(state)
        self.assertIn('region', context)
        for secret in ['PRIVATE_ANSWER','PRIVATE_OBSERVATION','HIDDEN_RESULT','/private/report']:
            self.assertNotIn(secret, context)

    def test_selecting_old_result_branches_from_its_context(self):
        state = add_analysis(None, 'First chart', '', log(x='region'))
        first = state['active_id']
        state = add_analysis(state, 'Second chart', '', log(x='department'))
        _, selected = select_analysis(state, first)
        branch = add_analysis(selected, 'Change average', '', log(x='region', method='mean'))
        self.assertEqual(branch['entries'][-1]['parent_id'], first)
        self.assertIn('First chart', selection_context(branch))
        self.assertNotIn('Second chart', selection_context(branch))
        self.assertEqual(len(state['entries']), 2)

    def test_new_question_keeps_archive_but_removes_context(self):
        state = add_analysis(None, 'Old question', '', log(x='region'))
        fresh = new_question(state)
        self.assertEqual(selection_context(fresh), '')
        self.assertEqual(fresh['entries'], state['entries'])
        self.assertIsNotNone(state['active_id'])

    def test_utf8_budget_preserves_whole_arguments(self):
        state = empty_history()
        for _ in range(6):
            state = add_analysis(state, '中文问题' * 300, '', log(x='实际字段' * 40, method='sum'))
        context = selection_context(state)
        self.assertLessEqual(len(context.encode('utf-8')), CONTEXT_BYTES)
        records = json.loads(context)
        self.assertLessEqual(len(records), 2)
        for record in records:
            for call in record['tools']:
                self.assertEqual(call['arguments']['x'], '实际字段' * 40)

    def test_failed_request_does_not_overwrite_last_useful_context(self):
        state = add_analysis(None, 'Good', '', log(x='region'))
        failed = add_analysis(state, 'Bad', 'Error', [{'status':'error','tool':'create_chart'}])
        self.assertEqual(failed, state)
        self.assertEqual(selection_context(empty_history()), '')

    def test_unknown_selection_does_not_change_active_record(self):
        state = add_analysis(None, 'Good', '', log(x='region'))
        entry, selected = select_analysis(state, 'unknown')
        self.assertIsNone(entry)
        self.assertEqual(selected, state)


if __name__ == '__main__':
    unittest.main()
