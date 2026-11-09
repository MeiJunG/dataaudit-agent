import unittest
from pathlib import Path
from scripts.run_candidate_model import launch_arguments


class CandidateLaunch(unittest.TestCase):
    def test_local_single_slot_and_gpu_layers_are_explicit(self):
        args=launch_arguments(Path('/runtime/llama-server'),Path('/runtime/candidate.gguf'),'candidate',8081,4096)
        self.assertEqual(args[args.index('--host')+1],'127.0.0.1')
        self.assertEqual(args[args.index('--parallel')+1],'1')
        self.assertEqual(args[args.index('--flash-attn')+1],'off')
        self.assertEqual(args[args.index('--port')+1],'8081')

    def test_active_service_ports_and_oversized_context_are_rejected(self):
        for port,context in [(8080,4096),(7860,4096),(80,4096),(8081,100000)]:
            with self.subTest(port=port,context=context),self.assertRaises(ValueError):
                launch_arguments(Path('/server'),Path('/model'),'candidate',port,context)


if __name__=='__main__':
    unittest.main()
