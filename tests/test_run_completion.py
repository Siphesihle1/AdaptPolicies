import os
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from methods import config
from methods.progprompt import run_eval


class RunCompletionTests(unittest.TestCase):
    def run_agent(self, agent):
        args = SimpleNamespace(
            env_id=0,
            test_set="train",
            examples_type="random",
            examples_num=3,
            num_tasks=1,
        )
        with patch.dict(os.environ, {"ADAPT_CONFIG": "dev"}), patch.object(
            run_eval, "ProgPromptAgent", return_value=agent
        ):
            config.get_config.cache_clear()
            try:
                run_eval.execute_progprompt_agent(args)
            finally:
                config.get_config.cache_clear()

    def test_pipeline_failure_is_retained_if_cloud_finalization_also_fails(self):
        agent = MagicMock()
        agent.generate_task_plans.side_effect = ValueError("pipeline failure")
        agent.log_eval_results.side_effect = OSError("cloud offline")
        with self.assertRaisesRegex(ValueError, "pipeline failure"):
            self.run_agent(agent)
        saved = agent.export_results.call_args.kwargs
        self.assertEqual(saved["run_status"], "aborted")
        self.assertIn("pipeline failure", saved["error"])
        self.assertIn("cloud offline", saved["error"])

    def test_completed_local_results_distinguish_a_cloud_logging_failure(self):
        agent = MagicMock()
        agent.log_eval_results.side_effect = OSError("cloud offline")
        with self.assertRaisesRegex(OSError, "cloud offline"):
            self.run_agent(agent)
        self.assertEqual(
            agent.export_results.call_args.kwargs["run_status"], "telemetry_failed"
        )
