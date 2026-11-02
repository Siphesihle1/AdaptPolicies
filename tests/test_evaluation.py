"""Evaluation regression checks without starting a simulator or loading its SDK."""

import importlib
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from methods import config


class EvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # These collaborators are irrelevant to evaluating already executed tasks.
        with patch.dict(
            "sys.modules",
            {
                "uuid_utils": SimpleNamespace(uuid7=lambda: "test-id"),
                "methods.progprompt.prompt": SimpleNamespace(
                    Env0TestSet=str, ExamplesType=str, PromptBuilder=None
                ),
                "methods.progprompt.task_scripts": SimpleNamespace(
                    exec_task=None, generate_task_scripts=None
                ),
            },
        ):
            cls.agent_class = importlib.import_module(
                "methods.progprompt.agent"
            ).ProgPromptAgent

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.environment = patch.dict(
            os.environ, {"JOB_OUTPUT_DIR": self.directory.name, "ADAPT_CONFIG": "dev"}
        )
        self.environment.start()
        config.get_config.cache_clear()
        self.agent = self.agent_class.__new__(self.agent_class)
        self.agent.results = {}
        self.agent.evaluation_logger = None
        self.agent.num_tasks_parsed = 0
        self.agent.num_tasks_executed = 0

    def tearDown(self):
        self.environment.stop()
        self.directory.cleanup()
        config.get_config.cache_clear()

    def test_all_failed_run_with_logging_disabled(self):
        self.agent.plans = {"failed": []}
        self.agent.final_states = []
        self.agent.initial_states = []
        self.agent.final_states_gt = [{"nodes": [], "edges": []}]
        self.agent.exec_per_task = {}
        self.agent.eval()
        self.agent.log_eval_results()
        self.assertEqual(self.agent.results["overall"]["SR"], 0)
        self.assertFalse((Path(self.directory.name) / "evaluation.json").exists())

    def test_ground_truth_loader_preserves_array_order(self):
        root = Path(self.directory.name)
        (root / "final_states").mkdir()
        graphs = [
            {"nodes": [{"id": identifier}], "edges": []} for identifier in (20, 10)
        ]
        (root / "final_states/final_states_example.json").write_text(
            json.dumps(graphs, indent=2)
        )
        module = importlib.import_module("methods.progprompt.agent")
        with patch.dict(os.environ, {"PROGPROMPT_DATASET_DIR": str(root)}):
            self.assertEqual(module.get_ground_truth_final_states("example"), graphs)

    def test_failed_task_does_not_shift_ground_truth(self):
        def graph(state):
            return {
                "nodes": [{"id": 1, "class_name": "fridge", "states": [state]}],
                "edges": [],
            }

        self.agent.plans = {"failed": [], "successful": ["def successful():", "test"]}
        self.agent.final_states_gt = [graph("OFF"), graph("OPEN")]
        self.agent.final_states = [graph("OPEN")]
        self.agent.initial_states = [graph("CLOSED")]
        self.agent.exec_per_task = {"successful": 1.0}
        (Path(self.directory.name) / "task_logs" / "successful").mkdir(parents=True)
        self.agent.eval()
        self.agent.log_eval_results()
        self.assertEqual(self.agent.results["successful"]["SR"], 1)
        self.assertNotIn("failed", self.agent.results)
