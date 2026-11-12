"""Adaptive Policies settings, configuration validation and model profiles."""

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from methods import config
from methods.adaptive.settings import AdaptiveLimits

PROFILES = "\n".join(f"          {purpose}: {{}}" for purpose in sorted(config.ADAPTIVE_PURPOSES))


def write_config(directory, adaptive="", profiles=PROFILES):
    path = Path(directory) / "config.yml"
    path.write_text(f'''llm:
  provider: lm_studio
  model: fake
  providers:
    lm_studio:
      base_url: http://127.0.0.1:1/v1
      timeout: 1
      models:
        fake:
{profiles}
weave:
  enabled: false
{adaptive}''')
    return path


class AdaptiveConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.addCleanup(config.get_config.cache_clear)

    def load(self, **kwargs):
        config.get_config.cache_clear()
        with patch.dict(os.environ, {"ADAPT_CONFIG": str(write_config(self.directory.name, **kwargs))}):
            return config.get_config()

    def test_limits_defaults_and_validation(self):
        limits = AdaptiveLimits()
        self.assertEqual((limits.placement, limits.max_model_requests, limits.max_recoveries_per_checkpoint),
                         ("both", 64, 2))
        self.assertTrue(limits.explicit and limits.implicit)
        self.assertFalse(AdaptiveLimits(placement="implicit").explicit)
        self.assertFalse(AdaptiveLimits(placement="explicit").implicit)
        for bad in ({"placement": "never"}, {"max_recoveries_per_checkpoint": 0}, {"max_actions": 1.5},
                    {"task_seconds": float("inf")}):
            with self.subTest(settings=bad), self.assertRaises(ValueError):
                AdaptiveLimits(**bad)

    def test_adaptive_section_and_profiles_are_validated(self):
        loaded = self.load(adaptive="adaptive:\n  placement: explicit\n  max_model_requests: 80\n")
        self.assertEqual(loaded["adaptive"]["placement"], "explicit")
        with self.assertRaises(ValueError):
            self.load(adaptive="adaptive:\n  placement: sometimes\n")
        with self.assertRaises(ValueError):
            self.load(adaptive="adaptive:\n  unknown: 1\n")
        with self.assertRaises(ValueError):
            self.load(profiles="          ap_policy: {}")

    def test_method_profiles_are_required_per_method(self):
        self.load()
        with patch.dict(os.environ, {"ADAPT_CONFIG": str(write_config(self.directory.name))}):
            config.get_config.cache_clear()
            config.require_method_profiles("adaptive")
            with self.assertRaises(ValueError):
                config.require_method_profiles("cap")

    def test_generation_accepts_adaptive_purposes(self):
        self.assertLessEqual(config.ADAPTIVE_PURPOSES, config.ALL_PURPOSES)
        from methods.chat_transcript import record_response
        for purpose in config.ADAPTIVE_PURPOSES:
            record_response("def policy():\n    pass", purpose)


if __name__ == "__main__":
    unittest.main()
