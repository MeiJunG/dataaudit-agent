"""Pure regression tests runnable without a local Pandas/LLM installation."""
import unittest

from src.check_logic import check_conditional_values, check_date_pairs, check_text_values


class TextChecks(unittest.TestCase):
    def test_blank_space_and_case_variants_are_distinct_checks(self):
        result = check_text_values(['completed', ' Completed ', 'COMPLETED', '', '  ', None])
        self.assertEqual(result['missing_values'], 1)
        self.assertEqual(result['blank_text_values'], 2)
        self.assertEqual(result['outer_whitespace_values'], 2)
        self.assertEqual(result['normalized_collision_groups'], 1)
        self.assertEqual(result['collision_rows'], 3)

    def test_sensitive_examples_hidden(self):
        result = check_text_values(['private', 'PRIVATE'], sensitive=True)
        self.assertEqual(result['example_groups'], [])
        self.assertEqual(result['collision_rows'], 2)

    def test_unicode_casefold_and_no_false_collision_for_identical_strings(self):
        self.assertEqual(check_text_values(['Straße', 'STRASSE'])['normalized_collision_groups'], 1)
        self.assertEqual(check_text_values(['same', 'same'])['normalized_collision_groups'], 0)


class ConditionalChecks(unittest.TestCase):
    def test_multiple_missing_fields_count_row_once(self):
        result = check_conditional_values(['completed', 'completed', 'pending', None],
                                         {'a': [None, '  ', None, None], 'b': ['', 20, None, None]}, 'completed')
        self.assertEqual(result['matched_rows'], 2)
        self.assertEqual(result['affected_rows'], 2)
        self.assertEqual(result['missing_by_column'], {'a': 2, 'b': 1})
        self.assertEqual(result['missing_condition_rows'], 1)

    def test_condition_is_exact_and_zero_is_not_missing(self):
        result = check_conditional_values(['Completed', ' completed ', 'completed'], {'a': [None, None, 0]}, 'completed')
        self.assertEqual(result['matched_rows'], 1)
        self.assertEqual(result['affected_rows'], 0)

    def test_misaligned_columns_rejected(self):
        with self.assertRaises(ValueError):
            check_conditional_values(['a'], {'x': []}, 'a')


class DateOrderChecks(unittest.TestCase):
    def test_order_missing_and_invalid_are_separate(self):
        result = check_date_pairs(['2026-10-01', '2026-10-03', '2026-10-01', None, 'bad'],
                                  ['2026-10-02', '2026-10-02', '2026-10-01', 'bad', '2026-10-01'])
        self.assertEqual(result['compared_rows'], 3)
        self.assertEqual(result['violation_rows'], 1)
        self.assertEqual(result['equal_date_rows'], 1)
        self.assertEqual(result['missing_date_pair_rows'], 1)
        self.assertEqual(result['invalid_date_pair_rows'], 1)

    def test_strict_order_counts_equal_dates_as_violations(self):
        result = check_date_pairs(['2026-10-01'], ['2026-10-01'], allow_equal=False)
        self.assertEqual(result['violation_rows'], 1)

    def test_offsets_are_normalized_and_numeric_epochs_are_not_guessed(self):
        result = check_date_pairs(['2026-10-01T01:00:00+02:00', 123], ['2026-09-30T23:00:00Z', '2026-10-01'])
        self.assertEqual(result['equal_date_rows'], 1)
        self.assertEqual(result['invalid_date_pair_rows'], 1)

    def test_empty_and_misaligned_pairs(self):
        self.assertEqual(check_date_pairs([], [])['compared_rows'], 0)
        with self.assertRaises(ValueError):
            check_date_pairs([], ['2026-10-01'])


if __name__ == '__main__':
    unittest.main()
