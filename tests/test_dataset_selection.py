"""Dataset selection through the runner and agent without a simulator."""

from contextlib import redirect_stderr
import importlib
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from methods import config
from methods.progprompt.datasets import validate_dataset
from methods.progprompt.ground_truth import normalize_task_name
from methods.progprompt.prompt import load_tasks_from_dir, load_tasks_from_file

DATASET_ROOT = Path(__file__).resolve().parents[1] / "src/methods/progprompt/data"


class DatasetSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch.dict(
            "sys.modules",
            {
                "uuid_utils": SimpleNamespace(uuid7=lambda: "test-id"),
                "methods.progprompt.task_scripts": SimpleNamespace(
                    exec_task=None, generate_task_scripts=None
                ),
            },
        ):
            cls.runner = importlib.import_module("methods.progprompt.run_eval")

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.environment = patch.dict(
            os.environ,
            {
                "ADAPT_CONFIG": "dev",
                "PROGPROMPT_DATASET_DIR": str(DATASET_ROOT),
                "JOB_OUTPUT_DIR": self.directory.name,
            },
        )
        self.environment.start()
        config.get_config.cache_clear()

    def tearDown(self):
        self.environment.stop()
        self.directory.cleanup()
        config.get_config.cache_clear()

    def arguments(self, env_id=0, dataset="test_seen", num_tasks="2"):
        return [
            "--expt-name",
            "selection-test",
            "--env-id",
            str(env_id),
            "--test-set",
            dataset,
            "--num-tasks",
            num_tasks,
            "--examples-type",
            "random",
            "--examples-num",
            "3",
        ]

    def test_each_cli_option_is_required(self):
        arguments = self.arguments()
        for index in range(0, len(arguments), 2):
            with self.subTest(option=arguments[index]), redirect_stderr(
                io.StringIO()
            ) as errors:
                with self.assertRaises(SystemExit) as raised:
                    self.runner.parse_args(arguments[:index] + arguments[index + 2 :])
                self.assertEqual(raised.exception.code, 2)
                self.assertIn(arguments[index], errors.getvalue())
                self.assertIn("required", errors.getvalue())

    def test_cli_preserves_each_explicit_dataset_and_task_count(self):
        for env_id, split in (
            (0, "train"),
            (0, "test_seen"),
            (0, "test_unseen"),
            (0, "test_unseen_ambiguous_goals"),
            (1, "env1"),
            (2, "env2"),
        ):
            with self.subTest(split=split):
                args = self.runner.parse_args(self.arguments(env_id, split))
                self.assertEqual(
                    (args.env_id, args.test_set, args.num_tasks), (env_id, split, 2)
                )
        self.assertIsNone(
            self.runner.parse_args(self.arguments(num_tasks="all")).num_tasks
        )

    def test_cli_can_derive_env_dataset_from_required_scene(self):
        for env_id in (1, 2):
            with self.subTest(env_id=env_id):
                arguments = self.arguments(env_id, f"env{env_id}")
                index = arguments.index("--test-set")
                del arguments[index : index + 2]
                args = self.runner.parse_args(arguments)
                self.assertEqual((args.env_id, args.test_set), (env_id, f"env{env_id}"))

    def test_cli_rejects_incompatible_or_unknown_selections(self):
        cases = [
            (self.arguments(env_id, split), "requires --env-id 0")
            for env_id in (1, 2)
            for split in (
                "train",
                "test_seen",
                "test_unseen",
                "test_unseen_ambiguous_goals",
            )
        ] + [
            (self.arguments(0, "env1"), "requires --env-id 1"),
            (self.arguments(1, "env2"), "requires --env-id 2"),
            (self.arguments(3), "invalid choice"),
            (self.arguments(dataset="test_unseen_ambiguous"), "invalid choice"),
        ]
        for arguments, message in cases:
            with self.subTest(arguments=arguments), redirect_stderr(
                io.StringIO()
            ) as errors:
                with self.assertRaises(SystemExit) as raised:
                    self.runner.parse_args(arguments)
                self.assertEqual(raised.exception.code, 2)
                self.assertIn(message, errors.getvalue())

    def test_cli_rejects_invalid_task_counts(self):
        for count in ("0", "-1", "none", "1.5"):
            with self.subTest(count=count), redirect_stderr(io.StringIO()) as errors:
                with self.assertRaises(SystemExit):
                    self.runner.parse_args(self.arguments(num_tasks=count))
                self.assertIn("positive integer or 'all'", errors.getvalue())

    def test_agent_selects_matching_tasks_and_references_before_subsetting(self):
        cases = (
            (0, "test_unseen", "test_unseen"),
            (0, "train", "train"),
            (0, "test_seen", "test_seen"),
            (0, "test_unseen_ambiguous_goals", "test_unseen_ambiguous_goals"),
            (1, "env1", "env1"),
            (2, "env2", "env2"),
        )
        for env_id, split, dataset in cases:
            with self.subTest(dataset=dataset), patch(
                "methods.progprompt.prompt.init_simulator",
                return_value={"nodes": [], "edges": []},
            ) as simulator:
                agent = self.runner.ProgPromptAgent(
                    env_id=env_id, test_set=split, num_tasks=2
                )
                tasks = (
                    load_tasks_from_dir(str(DATASET_ROOT / dataset))
                    if env_id == 0
                    else load_tasks_from_file(
                        str(DATASET_ROOT / "new_env" / f"{dataset}_annotated.json")
                    )
                )
                self.assertEqual(agent.dataset, dataset)
                self.assertEqual(
                    [prompt.task_instruction for prompt in agent.prompt_builder],
                    [normalize_task_name(task) for task in tasks[:2]],
                )
                self.assertEqual(
                    set(agent.ground_truth_graphs),
                    {normalize_task_name(task) for task in tasks},
                )
                mapping = json.loads(
                    (
                        DATASET_ROOT / "ground_truth_graph_mappings" / f"{dataset}.json"
                    ).read_text()
                )
                graphs = json.loads(
                    (
                        DATASET_ROOT / "final_states" / f"final_states_{dataset}.json"
                    ).read_text()
                )
                for task, index in mapping.items():
                    self.assertEqual(agent.ground_truth_graphs[task], graphs[index])
                simulator.assert_called_once_with(env_id)

    def test_programmatic_invalid_selection_fails_before_simulator(self):
        with patch("methods.progprompt.agent.PromptBuilder") as builder:
            for env_id, split in (
                (1, "train"),
                (2, "test_seen"),
                (3, None),
                (0, "unknown"),
                (0, None),
                (1, None),
                (0, "env1"),
            ):
                with self.subTest(env_id=env_id, split=split):
                    with self.assertRaises(ValueError):
                        self.runner.ProgPromptAgent(env_id=env_id, test_set=split)
            builder.assert_not_called()

    def test_explicit_runner_and_cluster_training_reach_agent(self):
        for arguments, expected_split in (
            (self.arguments(0, "test_unseen"), "test_unseen"),
            (self.arguments(1, "env1"), "env1"),
            (self.arguments(2, "env2"), "env2"),
            (self.arguments(0, "train", "all"), "train"),
        ):
            with self.subTest(arguments=arguments), patch.object(
                self.runner, "ProgPromptAgent"
            ) as constructor:
                args = self.runner.parse_args(arguments)
                self.runner.execute_progprompt_agent(args)
                self.assertEqual(constructor.call_args.kwargs["env_id"], args.env_id)
                self.assertEqual(
                    constructor.call_args.kwargs["test_set"], expected_split
                )
                constructor.return_value.generate_task_plans.assert_called_once()
                constructor.return_value.eval.assert_called_once()

    def test_programmatic_runner_rejects_mismatched_scene(self):
        args = self.runner.ProgramArgs(1, "train", "default", 3, "invalid-scene", None)
        with patch.object(self.runner, "ProgPromptAgent") as constructor:
            with self.assertRaisesRegex(ValueError, "requires --env-id 0"):
                self.runner.execute_progprompt_agent(args)
            constructor.assert_not_called()

    def test_shared_resolution_rejects_unknown_names(self):
        with self.assertRaisesRegex(ValueError, "Unknown test set"):
            validate_dataset(0, "test_unseen_ambiguous")
