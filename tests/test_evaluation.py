"""Evaluation regression checks without starting a simulator or loading its SDK."""

import importlib
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

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
        self.agent.task_records = {}
        self.agent.dataset = "train"
        self.agent.env_id = 0

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
        self.agent.export_results(run_status="completed")
        self.agent.log_eval_results()
        self.assertEqual(self.agent.results["overall"]["SR"], 0)
        saved = json.loads((Path(self.directory.name) / "results.json").read_text())
        self.assertEqual(saved["summary"]["num_tasks"], 1)
        self.assertEqual(saved["tasks"]["failed"]["metrics"]["SR"], 0)
        self.assertIsNone(saved["tasks"]["failed"]["metrics"]["Precision"])

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
        self.assertEqual(self.agent.evaluation_summary()["SR"], 0.5)
        self.assertEqual(
            self.agent.evaluation_summary()["conditional_metrics"]["SR"], 1
        )

    def test_weave_includes_failure_rows_and_uses_all_intended_tasks(self):
        self.agent.plans = {"failed": [], "success": ["def success():", "thread"]}
        self.agent.results = {
            "success": {"SR": 1, "PSR": 1, "Exec": 1, "Precision": 1},
            "overall": {"SR": 1, "PSR": 1, "Exec": 1, "Precision": 1},
        }
        self.agent.task_record("failed").update(
            status="execution_failed",
            plan="raw rejected plan",
            error="unsupported action",
        )
        logger = self.agent.evaluation_logger = MagicMock()
        self.agent.log_eval_results()
        self.assertEqual(logger.log_prediction.call_count, 2)
        failure = logger.log_prediction.call_args_list[0].kwargs
        self.assertEqual(failure["output"]["status"], "execution_failed")
        self.assertEqual(failure["output"]["plan"], "raw rejected plan")
        summary = logger.log_summary.call_args.args[0]
        self.assertEqual(summary["SR"], 0.5)
        self.assertEqual(summary["num_tasks_without_results"], 1)
        self.assertEqual(summary["conditional_metrics"]["SR"], 1)

    def test_generation_exception_does_not_lose_later_tasks_or_raw_rejections(self):
        prompts = [
            SimpleNamespace(task_instruction=name, text=f"prompt {name}")
            for name in ["api_failure", "bad_format", "valid"]
        ]
        self.agent.prompt_builder = prompts
        self.agent.plans = {prompt.task_instruction: [] for prompt in prompts}
        self.agent.exec_per_task = {}
        with patch(
            "methods.progprompt.agent.generate",
            side_effect=[
                RuntimeError("connection failed"),
                "```python\ndef bad_format():\n pass\n```",
                "def valid():\n pass",
            ],
        ):
            self.agent.generate_task_plans()
        saved = json.loads((Path(self.directory.name) / "results.json").read_text())
        self.assertEqual(saved["summary"]["num_tasks"], 3)
        self.assertEqual(saved["tasks"]["api_failure"]["status"], "generation_failed")
        self.assertEqual(saved["tasks"]["bad_format"]["status"], "parse_failed")
        self.assertTrue(saved["tasks"]["bad_format"]["plan"].startswith("```"))
        self.assertEqual(saved["tasks"]["valid"]["status"], "generated")
        self.assertEqual(saved["tasks"]["valid"]["prompt"], "prompt valid")

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
