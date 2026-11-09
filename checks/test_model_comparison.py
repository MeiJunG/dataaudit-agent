import copy
import unittest

from evaluation.compare_models import compare


def report():
    return {'complete':True,'model':'baseline','max_steps':3,'tasks_sha256':'same',
            'tasks':[{'id':'a','question':'Count rows','checks':['schema'],'seconds':1,'success':True,'error_observations':0},
                     {'id':'b','question':'Find duplicates','checks':['duplicates'],'seconds':3,'success':False,'error_observations':1}]}


class ModelComparison(unittest.TestCase):
    def test_same_tasks_can_compare_different_models_and_preserve_failure(self):
        baseline=report(); candidate=copy.deepcopy(baseline); candidate['model']='candidate'
        candidate['tasks'][1]['success']=True
        result=compare([baseline,candidate])
        self.assertEqual([row['passed'] for row in result],[1,2])
        self.assertEqual(result[0]['median_seconds'],2)
        self.assertEqual(result[0]['failures'],['b'])

    def test_changed_prompts_incomplete_runs_and_duplicate_ids_rejected(self):
        for change in ['prompt','incomplete','duplicate','budget','digest']:
            candidate=report()
            if change=='prompt': candidate['tasks'][0]['question']='A different task'
            if change=='incomplete': candidate['complete']=False
            if change=='duplicate': candidate['tasks'][1]['id']='a'
            if change=='budget': candidate['max_steps']=6
            if change=='digest': candidate['tasks_sha256']='different'
            with self.subTest(change=change), self.assertRaises(ValueError):
                compare([report(),candidate])


    def test_known_context_or_output_budget_changes_cannot_be_ranked_as_same_budget(self):
        baseline=report(); candidate=report()
        baseline['runtime_limits']={'context_tokens':4096,'max_output_tokens':256}
        candidate['runtime_limits']={'context_tokens':8192,'max_output_tokens':512}
        with self.assertRaises(ValueError):
            compare([baseline,candidate])


if __name__ == '__main__':
    unittest.main()
