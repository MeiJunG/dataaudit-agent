import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from evaluation.run_profile import main


class ProfileLauncher(unittest.TestCase):
    def test_profile_overrides_only_child_and_clears_stale_thinking(self):
        with tempfile.TemporaryDirectory() as temporary:
            profile=Path(temporary)/'candidate.env'; profile.write_text('MODEL_NAME=candidate\n')
            script=Path(temporary)/'check.py'; script.write_text('pass\n')
            fake=types.SimpleNamespace(dotenv_values=lambda _: {'MODEL_NAME':'candidate','LLM_TEMPERATURE':'.7'})
            with patch.dict(sys.modules, {'dotenv':fake}), patch.dict('os.environ', {'LLM_ENABLE_THINKING':'true','MODEL_NAME':'baseline'}), \
                 patch.object(sys,'argv',['run_profile.py','--profile',str(profile),str(script),'--limit','3']), \
                 patch('evaluation.run_profile.subprocess.run',return_value=types.SimpleNamespace(returncode=0)) as run:
                self.assertEqual(main(),0)
                self.assertNotIn('LLM_ENABLE_THINKING',run.call_args.kwargs['env'])
                self.assertEqual(run.call_args.kwargs['env']['MODEL_NAME'],'candidate')
                self.assertEqual(run.call_args.args[0][-2:],['--limit','3'])
                import os
                self.assertEqual(os.environ['MODEL_NAME'],'baseline')
                self.assertEqual(profile.read_text(),'MODEL_NAME=candidate\n')

    def test_child_failure_is_reported(self):
        with tempfile.TemporaryDirectory() as temporary:
            profile=Path(temporary)/'candidate.env'; profile.touch()
            script=Path(temporary)/'check.py'; script.touch()
            fake=types.SimpleNamespace(dotenv_values=lambda _: {})
            with patch.dict(sys.modules, {'dotenv':fake}), \
                 patch.object(sys,'argv',['run_profile.py','--profile',str(profile),str(script)]), \
                 patch('evaluation.run_profile.subprocess.run',return_value=types.SimpleNamespace(returncode=7)):
                self.assertEqual(main(),7)


if __name__ == '__main__':
    unittest.main()
