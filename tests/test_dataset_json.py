"""Dataset format and loader checks without starting a simulator."""

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from methods.progprompt.constants import DEFAULT_EXAMPLES
from methods.progprompt.prompt import (
    load_task_prompt_examples,
    load_tasks_from_dir,
    load_tasks_from_file,
)

DATASET_ROOT = Path(__file__).resolve().parents[1] / "src/methods/progprompt/data"


class DatasetJsonTests(unittest.TestCase):
    def test_all_dataset_collections_are_arrays_of_objects(self):
        for path in DATASET_ROOT.rglob("*.json"):
            if path.parent.name in (
                "zero_shot_baseline_data",
                "ground_truth_graph_mappings",
            ):
                continue
            with self.subTest(path=path.relative_to(DATASET_ROOT)):
                records = json.loads(path.read_text(encoding="utf-8"))
                self.assertIsInstance(records, list)
                self.assertTrue(records or path.parent.name == "train")
                self.assertTrue(all(isinstance(record, dict) for record in records))
                if path.parent.name == "final_states":
                    for graph in records:
                        self.assertIsInstance(graph["nodes"], list)
                        self.assertIsInstance(graph["edges"], list)

    def test_file_loader_reads_multiline_array_and_preserves_task_order(self):
        records = [{"second task": {"0: find mug": []}}, {"first task": {}}]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tasks.json"
            path.write_text(json.dumps(records, indent=2), encoding="utf-8")
            self.assertEqual(
                load_tasks_from_file(str(path)), ["second task", "first task"]
            )

    def test_directory_loader_preserves_numeric_file_and_record_order(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "file10_annotated.json").write_text('[{"last": {}}]')
            (root / "file2_annotated.json").write_text(
                '[{"second": {}}, {"first": {}}]'
            )
            self.assertEqual(
                load_tasks_from_dir(directory), ["second", "first", "last"]
            )

    def test_task_loader_requires_a_single_json_document(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tasks.json"
            path.write_text('{"first": {}}\n{"second": {}}\n')
            with self.assertRaises(json.JSONDecodeError):
                load_tasks_from_file(str(path))

    def test_real_task_splits_load_with_existing_counts(self):
        for dataset, count in (
            ("train", 24),
            ("test_seen", 10),
            ("test_unseen", 10),
            ("test_unseen_ambiguous_goals", 5),
        ):
            with self.subTest(dataset=dataset):
                self.assertEqual(
                    len(load_tasks_from_dir(str(DATASET_ROOT / dataset))), count
                )
        for env_id in (1, 2):
            path = DATASET_ROOT / "new_env" / f"env{env_id}_annotated.json"
            self.assertEqual(len(load_tasks_from_file(str(path))), 10)

    def test_prompt_examples_keep_names_contents_and_order(self):
        path = DATASET_ROOT / "pythonic_plans/train_complete_plan_set.json"
        records = json.loads(path.read_text(encoding="utf-8"))
        with patch.dict(os.environ, {"PROGPROMPT_DATASET_DIR": str(DATASET_ROOT)}):
            examples = load_task_prompt_examples()
        self.assertEqual(len(examples), 24)
        self.assertEqual(
            list(examples), [name for record in records for name in record]
        )
        for name in DEFAULT_EXAMPLES:
            self.assertIsInstance(examples[name], str)
        self.assertEqual(
            examples,
            {name: plan for record in records for name, plan in record.items()},
        )

    def test_task_splits_and_prompt_examples_do_not_overlap(self):
        def normalize(name: str):
            return " ".join(name.lower().replace("_", " ").split())

        owners = {}
        training_tasks = set()
        for dataset in (
            "train",
            "test_seen",
            "test_unseen",
            "test_unseen_ambiguous_goals",
        ):
            for task in load_tasks_from_dir(str(DATASET_ROOT / dataset)):
                name = normalize(task)
                self.assertNotIn(name, owners, f"Duplicate task: {task}")
                owners[name] = dataset
                if dataset == "train":
                    training_tasks.add(name)

        self.assertEqual(owners["wash mug"], "test_seen")
        path = DATASET_ROOT / "pythonic_plans/train_complete_plan_set.json"
        examples = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(
            {normalize(name) for record in examples for name in record}, training_tasks
        )
        self.assertTrue(
            all(normalize(name) in training_tasks for name in DEFAULT_EXAMPLES)
        )
