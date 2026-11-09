import unittest

from src.model_config import request_options


class ModelOptions(unittest.TestCase):
    def test_existing_default_is_preserved(self):
        self.assertEqual(request_options({}), {'temperature': 0})

    def test_thinking_switch_is_opt_in_and_explicit(self):
        result = request_options({'LLM_TEMPERATURE':'.7','LLM_TOP_P':'.8','LLM_ENABLE_THINKING':'false'})
        self.assertEqual(result['extra_body'], {'chat_template_kwargs': {'enable_thinking': False}})
        self.assertEqual(result['top_p'], .8)

    def test_invalid_sampling_values_fail_early(self):
        for env in [{'LLM_TEMPERATURE':'nan'}, {'LLM_TEMPERATURE':'3'}, {'LLM_TOP_P':'0'},
                    {'LLM_TOP_P':'inf'}, {'LLM_ENABLE_THINKING':'maybe'}]:
            with self.subTest(env=env), self.assertRaises(ValueError):
                request_options(env)


if __name__ == '__main__':
    unittest.main()
