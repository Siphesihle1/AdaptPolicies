import json
import os
from pathlib import Path
import random
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from methods import config, telemetry
from methods.cap import run_eval
from methods.cap.prompt import select_examples
from methods.cap.runtime import Limits


class ConfigurationTests(unittest.TestCase):
    def test_cap_cli_uses_cap_only_experiment_metadata(self):
        args = SimpleNamespace(expt_name="cap-smoke", test_set="train", env_id=0,
                               examples_type="default", examples_num=3, num_tasks=1)
        with patch.dict(os.environ, {"ADAPT_CONFIG": str(config.ROOT / "config/cap.yml")}):
            config.get_config.cache_clear()
            try:
                with patch.object(run_eval, "parse_args", return_value=args), patch.object(
                    run_eval, "CaPAgent"
                ) as agent:
                    run_eval.main([])
                    agent.return_value.execute_tasks.assert_called_once_with()
                    metadata = telemetry.experiment_attributes()
                    self.assertEqual(metadata["cap_policy_max_tokens"], 4096)
                    self.assertEqual(metadata["cap_function_temperature"], 0)
                    self.assertNotIn("plan_max_tokens", metadata)
            finally:
                config.get_config.cache_clear()

    def test_cap_profiles_and_runtime_section_validate_without_progprompt(self):
        path = config.ROOT / "config" / "cap.yml"
        with patch.dict(os.environ, {"ADAPT_CONFIG": str(path)}):
            config.get_config.cache_clear()
            settings = config.get_llm_settings()
            self.assertTrue(config.CAP_PURPOSES <= settings.keys())
            config.require_method_profiles("cap")
            with self.assertRaisesRegex(ValueError, "progprompt requires"):
                config.require_method_profiles("progprompt")
        config.get_config.cache_clear()

    def test_invalid_limits_rejected(self):
        for settings in ({"task_seconds": float('inf')}, {"max_depth": 0}, {"max_queries": True}, {"max_actions": 1.5}):
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                Limits(**settings)

    def test_random_example_identities_match_existing_seed_policy(self):
        root = config.ROOT / "src" / "methods" / "progprompt" / "data"
        data = json.loads((root / "pythonic_plans" / "train_complete_plan_set.json").read_text())
        expected = random.Random(42).sample([name for entry in data for name in entry], 6)
        with patch.dict(os.environ, {"ADAPT_DATASET_DIR": str(root)}):
            examples = select_examples("random", 6)
        names = [line.split("task: ")[1] for line in examples.splitlines() if line.startswith("# example episode_id:")]
        self.assertEqual(names, expected)
