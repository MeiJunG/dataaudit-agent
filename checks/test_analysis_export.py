import json
import tempfile
import unittest
from pathlib import Path

from src.analysis_export import save_analysis_record
from src.session_history import add_analysis, empty_history, new_question, select_analysis


def state(question='Original question'):
    trace = [{'tool':'check_missing_values','arguments':{},'status':'ok','duration_ms':2,
              'structured_result':{'missing':2},'unexpected_secret':'DO_NOT_EXPORT'}]
    return add_analysis(None,question,'Computed answer',trace,metadata={
        'model':'local-model','dataset':{'sha256':'a'*64},'api_key':'DO_NOT_EXPORT'})


class AnalysisExportChecks(unittest.TestCase):
    def test_record_contains_exact_inputs_observations_and_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            history = state()
            path = save_analysis_record(history,directory)
            record = json.loads(path.read_text())
            self.assertEqual(record['question'],'Original question')
            self.assertEqual(record['tools'][0]['structured_result'],{'missing':2})
            self.assertEqual(record['metadata']['dataset']['sha256'],'a'*64)
            self.assertNotIn('DO_NOT_EXPORT',path.read_text())

    def test_restoring_older_analysis_reuses_its_exact_file(self):
        with tempfile.TemporaryDirectory() as directory:
            history = state()
            first_id = history['active_id']
            first_path = save_analysis_record(history,directory)
            history = add_analysis(history,'Second question','Second answer',[{'tool':'inspect_schema','status':'ok'}])
            second_path = save_analysis_record(history,directory)
            _,history = select_analysis(history,first_id)
            self.assertEqual(save_analysis_record(history,directory),first_path)
            self.assertNotEqual(first_path,second_path)
            self.assertEqual(len(list(Path(directory).glob('*.json'))),2)

    def test_fresh_or_empty_context_has_no_download(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertIsNone(save_analysis_record(empty_history(),directory))
            self.assertIsNone(save_analysis_record(new_question(state()),directory))

    def test_size_limit_prevents_partial_or_large_file(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertIsNone(save_analysis_record(state(),directory,max_bytes=1))
            self.assertEqual(list(Path(directory).iterdir()),[])


if __name__=='__main__':
    unittest.main()
