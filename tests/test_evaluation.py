"""Evaluation regression checks without starting a simulator or loading its SDK."""

import importlib
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
                    Env0TestSet=str,
                    ExamplesType=str,
                    PromptBuilder=None,
                    load_tasks_from_dir=None,
                    load_tasks_from_file=None,
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
        self.agent.ground_truth_graphs = {"failed": {"nodes": [], "edges": []}}
        self.agent.exec_per_task = {}
        self.agent.eval()
        self.agent.log_eval_results()
        self.assertEqual(self.agent.results["overall"]["SR"], 0)
        self.assertFalse((Path(self.directory.name) / "evaluation.json").exists())

    def test_failed_task_does_not_shift_ground_truth(self):
        def graph(state):
            return {
                "nodes": [{"id": 1, "class_name": "fridge", "states": [state]}],
                "edges": [],
            }

        self.agent.plans = {"failed": [], "successful": ["def successful():", "test"]}
        self.agent.ground_truth_graphs = {
            "successful": graph("OPEN"),
            "failed": graph("OFF"),
        }
        self.agent.final_states = [graph("OPEN")]
        self.agent.initial_states = [graph("CLOSED")]
        self.agent.exec_per_task = {"successful": 1.0}
        (Path(self.directory.name) / "task_logs" / "successful").mkdir(parents=True)
        self.agent.eval()
        self.agent.log_eval_results()
        self.assertEqual(self.agent.results["successful"]["SR"], 1)
        self.assertNotIn("failed", self.agent.results)

    def test_single_task_uses_its_named_graph(self):
        def graph(state):
            return {
                "nodes": [{"id": 1, "class_name": "radio", "states": [state]}],
                "edges": [],
            }

        self.agent.plans = {"listen_to_radio": ["def listen_to_radio():", "test"]}
        self.agent.ground_truth_graphs = {
            "other_task": graph("OFF"),
            "listen_to_radio": graph("ON"),
        }
        self.agent.final_states = [graph("ON")]
        self.agent.initial_states = [graph("OFF")]
        self.agent.exec_per_task = {"listen_to_radio": 1.0}
        (Path(self.directory.name) / "task_logs/listen_to_radio").mkdir(parents=True)
        self.agent.eval()
        self.assertEqual(self.agent.results["listen_to_radio"]["SR"], 1)

    def test_plan_and_mapping_order_do_not_determine_graph_selection(self):
        def graph(state):
            return {
                "nodes": [{"id": 1, "class_name": "fridge", "states": [state]}],
                "edges": [],
            }

        self.agent.plans = {
            "turn_on": ["def turn_on():", "test"],
            "open_fridge": ["def open_fridge():", "test"],
        }
        self.agent.ground_truth_graphs = {
            "open_fridge": graph("OPEN"),
            "turn_on": graph("ON"),
        }
        self.agent.exec_per_task = {"open_fridge": 1.0, "turn_on": 1.0}
        self.agent.final_states = [graph("OPEN"), graph("ON")]
        self.agent.initial_states = [graph("CLOSED"), graph("OFF")]
        for task in self.agent.plans:
            (Path(self.directory.name) / "task_logs" / task).mkdir(parents=True)
        self.agent.eval()
        self.assertEqual(self.agent.results["open_fridge"]["SR"], 1)
        self.assertEqual(self.agent.results["turn_on"]["SR"], 1)

    def test_missing_mapping_fails_before_simulator_construction(self):
        with patch.dict(
            os.environ, {"PROGPROMPT_DATASET_DIR": self.directory.name}
        ), patch(
            "methods.progprompt.agent.load_tasks_from_dir", return_value=["test task"]
        ), patch(
            "methods.progprompt.agent.PromptBuilder"
        ) as builder:
            with self.assertRaisesRegex(
                ValueError, "Missing ground_truth_graph mapping"
            ):
                self.agent_class(env_id=0, test_set="test_seen")
            builder.assert_not_called()
