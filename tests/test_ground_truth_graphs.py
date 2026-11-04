import json
from pathlib import Path
import tempfile
import unittest

from methods.progprompt.ground_truth import load_ground_truth_graphs


class GroundTruthGraphTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        (self.root / "final_states").mkdir()
        (self.root / "ground_truth_graph_mappings").mkdir()
        self.mapping_path = self.root / "ground_truth_graph_mappings/example.json"
        self.graphs = [
            {
                "nodes": [{"id": 1, "class_name": "radio", "states": [state]}],
                "edges": [],
            }
            for state in ("OFF", "ON")
        ]
        (self.root / "final_states/final_states_example.json").write_text(
            json.dumps(self.graphs)
        )
        self.mapping_path.write_text(json.dumps({"radio_on": 1, "radio_off": 0}))

    def tearDown(self):
        self.directory.cleanup()

    def load(self, tasks=("radio on", "radio off")):
        return load_ground_truth_graphs("example", tasks, self.root)

    def test_task_order_does_not_change_selected_graphs(self):
        first = self.load()
        reordered = self.load(("radio off", "radio on"))
        self.assertEqual(first, reordered)
        self.assertEqual(first["radio_on"], self.graphs[1])
        self.assertEqual(first["radio_off"], self.graphs[0])

    def test_duplicate_mapping_key_is_rejected(self):
        self.mapping_path.write_text('{"radio_on": 1, "radio_on": 0, "radio_off": 0}')
        with self.assertRaisesRegex(ValueError, "Duplicate ground_truth_graph mapping"):
            self.load()

    def test_duplicate_normalized_dataset_task_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate task names"):
            self.load(("radio on", "radio_on"))

    def test_missing_task_is_rejected(self):
        self.mapping_path.write_text('{"radio_on": 1}')
        with self.assertRaisesRegex(ValueError, "missing tasks=.*radio_off"):
            self.load()

    def test_unknown_task_is_rejected(self):
        self.mapping_path.write_text('{"radio_on": 1, "radio_off": 0, "other": 0}')
        with self.assertRaisesRegex(ValueError, "unexpected tasks=.*other"):
            self.load()

    def test_invalid_indexes_are_rejected(self):
        for index in (-1, 2, True, "1", 1.5, None):
            with self.subTest(index=index):
                self.mapping_path.write_text(
                    json.dumps({"radio_on": index, "radio_off": 0})
                )
                with self.assertRaisesRegex(
                    ValueError, "Invalid ground_truth_graph index"
                ):
                    self.load()

    def test_missing_mapping_does_not_fall_back_to_position(self):
        self.mapping_path.unlink()
        with self.assertRaisesRegex(ValueError, "Missing ground_truth_graph mapping"):
            self.load()

    def test_mapping_must_be_an_object(self):
        self.mapping_path.write_text("[1, 0]")
        with self.assertRaisesRegex(ValueError, "must be a JSON object"):
            self.load()

    def test_selected_graph_must_have_nodes_and_edges(self):
        (self.root / "final_states/final_states_example.json").write_text("[{}, {}]")
        with self.assertRaisesRegex(ValueError, "Invalid ground_truth_graph"):
            self.load()

    def test_real_test_seen_mapping_covers_tasks_and_selects_radio_and_wash_mug(self):
        root = Path(__file__).resolve().parents[1] / "src/methods/progprompt/data"
        tasks = [
            task
            for filename in (root / "test_seen").glob("*.json")
            for record in json.loads(filename.read_text())
            for task in record
        ]
        graphs = load_ground_truth_graphs("test_seen", tasks, root)
        radio = next(
            node for node in graphs["listen_to_radio"]["nodes"] if node["id"] == 176
        )
        self.assertIn("ON", radio["states"])
        mug = next(node for node in graphs["wash_mug"]["nodes"] if node["id"] == 447)
        self.assertIn("WASHED", mug["states"])
        self.assertTrue(
            any(
                edge["from_id"] == 447
                and edge["relation_type"] == "ON"
                and edge["to_id"] == 247
                for edge in graphs["wash_mug"]["edges"]
            )
        )

    def test_all_real_dataset_mappings_are_complete_and_order_independent(self):
        root = Path(__file__).resolve().parents[1] / "src/methods/progprompt/data"
        for dataset, count in (
            ("train", 24),
            ("test_seen", 10),
            ("test_unseen", 10),
            ("test_unseen_ambiguous_goals", 5),
            ("env1", 10),
            ("env2", 10),
        ):
            with self.subTest(dataset=dataset):
                paths = (
                    [root / "new_env" / f"{dataset}_annotated.json"]
                    if dataset.startswith("env")
                    else (root / dataset).glob("*.json")
                )
                tasks = [
                    name
                    for path in paths
                    for record in json.loads(path.read_text())
                    for name in record
                ]
                graphs = load_ground_truth_graphs(dataset, tasks, root)
                self.assertEqual(len(graphs), count)
                self.assertEqual(
                    graphs, load_ground_truth_graphs(dataset, reversed(tasks), root)
                )
