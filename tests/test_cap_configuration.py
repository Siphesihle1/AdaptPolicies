import json
import os
from pathlib import Path
import random
import unittest
from unittest.mock import patch

from methods import config
from methods.cap.prompt import select_examples
from methods.cap.runtime import Limits


class ConfigurationTests(unittest.TestCase):
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
