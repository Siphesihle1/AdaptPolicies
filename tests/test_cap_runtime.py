import json
import multiprocessing
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from methods import config, telemetry
from methods.cap.runtime import PolicyRuntime, Limits, validate
from methods.cap.environment import CaPEnvironment
from virtual_home.task import VHTask
from cap_fakes import FakeEnvironment, FakeProvider


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        path = Path(self.directory.name) / "offline.yml"
        path.write_text('''llm:
  provider: lm_studio
  model: fake
  providers:
    lm_studio:
      base_url: http://127.0.0.1:1/v1
      timeout: 1
      models:
        fake:
          plan: {}
          assertion: {}
weave:
  enabled: false
''')
        self.environment = patch.dict(os.environ, {"ADAPT_CONFIG": str(path)})
        self.environment.start()
        config.get_config.cache_clear()
        self.addCleanup(self.directory.cleanup)
        self.addCleanup(self.environment.stop)
        self.addCleanup(config.get_config.cache_clear)
        self.task = VHTask("test", "offline", ["test"], 100)
        self.env = FakeEnvironment(task=self.task)
        self.api = CaPEnvironment(self.env, self.task)

    def run_policy(self, source, **limits):
        self.runtime = PolicyRuntime(self.api, Limits(task_seconds=5, **limits), FakeProvider({"cap_policy": source}))
        return self.runtime.run("test")

    def test_reservations_and_external_access(self):
        for source in ["import os", "ret_val = (1).__class__", "walk = 1",
                       "def walk():\n    pass", "def f(walk):\n    pass"]:
            with self.subTest(source=source), self.assertRaises(ValueError):
                validate(source, {"walk"})

    def test_spawned_policy_observations_and_actions(self):
        result = self.run_policy('''def policy():
    mugs = [obj for obj in get_visible_objects() if obj.name == 'mug']
    for mug in mugs:
        if mug.id == 21:
            return grab(mug).status''')
        self.assertEqual(result["status"], "executed", result)
        self.assertEqual(result["result"], "succeeded")
        self.assertIn("<mug> (21)", self.env.calls[-1])
        self.assertEqual(result["counts"]["actions"], 1)
        self.assertTrue(result["final_state_available"])

    def test_real_process_cpu_and_generation_deadlines(self):
        for source in ["def policy():\n    while True:\n        pass", "BLOCK"]:
            with self.subTest(source=source):
                start = time.monotonic()
                result = self.run_policy(source)
                self.assertIn("deadline", result["error"])
                self.assertLess(time.monotonic() - start, 8)
                self.assertTrue(result["final_state_available"])
        self.assertFalse(multiprocessing.active_children())

    def test_query_and_action_budgets(self):
        for source, limits, category in [
            ("def policy():\n    while True:\n        get_visible_objects()", {"max_queries": 3}, "queries_limit"),
            ("def policy():\n    for i in range(5):\n        touch('mug')", {"max_actions": 2}, "actions_limit")]:
            result = self.run_policy(source, **limits)
            self.assertIn(category, result["error"], result)

    def test_native_call_deadline_invalidates_episode(self):
        from threading import Event
        release = Event()
        self.api.registry["walk"] = lambda *args: release.wait(10)
        try:
            result = self.run_policy("def policy():\n    walk('mug')")
            self.assertIn("native_action_deadline", result["error"])
            self.assertFalse(result["final_state_available"])
            self.assertTrue(self.env.execution_failed)
        finally:
            release.set()
