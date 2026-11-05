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

    def test_ground_truth_mappings_cover_all_current_datasets(self):
        for dataset, count in (
            ("train", 24),
            ("test_seen", 10),
            ("test_unseen", 10),
            ("test_unseen_ambiguous_goals", 5),
            ("env1", 10),
            ("env2", 10),
        ):
            with self.subTest(dataset=dataset):
                if dataset.startswith("env"):
                    tasks = load_tasks_from_file(
                        str(DATASET_ROOT / "new_env" / f"{dataset}_annotated.json")
                    )
                else:
                    tasks = load_tasks_from_dir(str(DATASET_ROOT / dataset))
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
                self.assertEqual(len(mapping), count)
                self.assertEqual(
                    set(mapping), {"_".join(task.split(" ")) for task in tasks}
                )
                self.assertEqual(len(set(mapping.values())), len(mapping))
                for index in mapping.values():
                    self.assertIs(type(index), int)
                    self.assertGreaterEqual(index, 0)
                    self.assertLess(index, len(graphs))
                    self.assertIsInstance(graphs[index]["nodes"], list)
                    self.assertIsInstance(graphs[index]["edges"], list)

    def test_cutlery_goal_matches_corrected_sink_placements(self):
        mapping = json.loads(
            (DATASET_ROOT / "ground_truth_graph_mappings/test_seen.json").read_text()
        )
        graphs = json.loads(
            (DATASET_ROOT / "final_states/final_states_test_seen.json").read_text()
        )
        graph = graphs[mapping["put_all_the_cutlery_in_the_sink"]]
        edges = {
            (edge["from_id"], edge["relation_type"], edge["to_id"])
            for edge in graph["edges"]
        }
        for identifier in (280, 272):
            self.assertIn((identifier, "ON", 247), edges)
            self.assertNotIn((identifier, "INSIDE", 247), edges)

    def test_plate_washing_uses_feasible_plate_and_matching_kitchen_faucet(self):
        records = json.loads(
            (DATASET_ROOT / "test_unseen/file1_annotated.json").read_text()
        )
        steps = next(
            record["wash the plate"] for record in records if "wash the plate" in record
        )
        actions = [action for instructions in steps.values() for action in instructions]
        self.assertEqual(len(actions), 18)
        self.assertEqual(
            [key for key, value in steps.items() if not value],
            ["5: scrub plate", "6: rinse plate", "8: Done"],
        )
        self.assertIn("<char0> [putback] <plate> (199) <sink> (247)", actions)
        self.assertIn("<char0> [switchon] <faucet> (248)", actions)
        self.assertIn("<char0> [switchoff] <faucet> (248)", actions)
        self.assertFalse(
            any(
                "<plate> (193)" in action or "<faucet> (50)" in action
                for action in actions
            )
        )
        mapping = json.loads(
            (DATASET_ROOT / "ground_truth_graph_mappings/test_unseen.json").read_text()
        )
        self.assertEqual(mapping["wash_the_plate"], 7)
        graph = json.loads(
            (DATASET_ROOT / "final_states/final_states_test_unseen.json").read_text()
        )[7]
        edges = {
            (edge["from_id"], edge["relation_type"], edge["to_id"])
            for edge in graph["edges"]
        }
        nodes = {node["id"]: node for node in graph["nodes"]}
        for identifier in (199, 267):
            self.assertIn((identifier, "ON", 247), edges)
            self.assertIn((identifier, "INSIDE", 205), edges)
            self.assertNotIn((identifier, "INSIDE", 247), edges)
            self.assertIn("WASHED", nodes[identifier]["states"])
        self.assertIn((193, "ON", 108), edges)
        self.assertNotIn((193, "INSIDE", 247), edges)
        self.assertIn((1, "INSIDE", 205), edges)
        self.assertIn((1, "CLOSE", 248), edges)
        for identifier in (50, 248):
            self.assertIn("OFF", nodes[identifier]["states"])

    def test_mappings_select_environment_specific_goal_objects(self):
        cases = (
            ("train", "refrigerate_the_salmon", 327, "INSIDE", 305),
            ("test_unseen_ambiguous_goals", "cook_lunch", 327, "ON", 269),
            ("env1", "put_chicken_in_the_fridge", 241, "INSIDE", 225),
            ("env2", "put_milk_in_the_fridge", 177, "INSIDE", 162),
        )
        for dataset, task, source, relation, target in cases:
            with self.subTest(dataset=dataset, task=task):
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
                self.assertTrue(
                    any(
                        edge["from_id"] == source
                        and edge["relation_type"] == relation
                        and edge["to_id"] == target
                        for edge in graphs[mapping[task]]["edges"]
                    )
                )
