import unittest
from typing import Any, Dict, Sequence, Tuple

from virtual_home.utils import add_additional_obj_states, add_sink_states


class SinkWashingTests(unittest.TestCase):
    def test_washing_uses_only_the_supplied_state(self) -> None:
        graph = self.graph()
        derived: Dict[int, Any] = {}
        add_additional_obj_states(
            {"nodes": [], "edges": []},
            ([], [], [], [], [], [10], [11, 12]),
            derived,
        )
        self.assertEqual(derived, {})
        add_additional_obj_states(graph, ([], [], [], [], [], [10], [11, 12]), derived)
        self.assertEqual(derived[20]["states"], ["WASHED"])

    def graph(
        self, relation: str = "ON", kitchen_on: bool = True, bathroom_on: bool = False
    ) -> Dict[str, Any]:
        def node(
            identifier: int,
            name: str,
            states: Sequence[str] = (),
            center: Tuple[float, float, float] = (0, 0, 0),
            category: str = "Furniture",
        ) -> Dict[str, Any]:
            return {
                "id": identifier,
                "class_name": name,
                "states": list(states),
                "category": category,
                "bounding_box": {"center": center},
            }

        def edge(source: int, relation: str, target: int) -> Dict[str, Any]:
            return {"from_id": source, "relation_type": relation, "to_id": target}

        return {
            "nodes": [
                node(1, "kitchen", category="Rooms"),
                node(2, "bathroom", category="Rooms"),
                node(10, "sink"),
                node(11, "faucet", ["ON" if kitchen_on else "OFF"]),
                node(12, "faucet", ["ON" if bathroom_on else "OFF"]),
                node(20, "mug", category="Props"),
            ],
            "edges": [
                edge(10, "INSIDE", 1),
                edge(11, "INSIDE", 1),
                edge(12, "INSIDE", 2),
                edge(20, relation, 10),
            ],
        }

    def test_on_and_inside_sink_are_washed_with_matching_faucet(self) -> None:
        for relation in ("ON", "INSIDE"):
            with self.subTest(relation=relation):
                graph = self.graph(relation)
                derived = {}
                add_sink_states(graph, [11, 12], [10], derived)
                add_sink_states(graph, [11, 12], [10], derived)
                self.assertEqual(derived[20]["states"], ["WASHED"])

    def test_another_rooms_faucet_does_not_wash_mug(self) -> None:
        graph = self.graph(kitchen_on=False, bathroom_on=True)
        derived = {}
        add_sink_states(graph, [11, 12], [10], derived)
        self.assertEqual(derived, {})
        self.assertEqual(graph["nodes"][-1]["states"], [])

    def test_nearest_faucet_must_be_on(self) -> None:
        graph = self.graph(kitchen_on=False, bathroom_on=True)
        graph["edges"][2]["to_id"] = 1
        graph["nodes"][4]["bounding_box"]["center"] = (10, 0, 0)
        derived = {}
        add_sink_states(graph, [11, 12], [10], derived)
        self.assertEqual(derived, {})

    def test_objects_on_other_surfaces_are_not_washed(self) -> None:
        graph = self.graph()
        graph["edges"][-1]["to_id"] = 1
        derived = {}
        add_sink_states(graph, [11, 12], [10], derived)
        self.assertEqual(derived, {})

    def test_faucet_without_geometry_is_ignored(self) -> None:
        graph = self.graph(bathroom_on=True)
        graph["edges"][2]["to_id"] = 1
        del graph["nodes"][4]["bounding_box"]
        derived = {}
        add_sink_states(graph, [11, 12], [10], derived)
        self.assertEqual(derived[20]["states"], ["WASHED"])

    def test_nearest_active_faucet_is_selected_regardless_of_node_order(self) -> None:
        graph = self.graph(kitchen_on=True, bathroom_on=False)
        graph["edges"][2]["to_id"] = 1
        graph["nodes"][4]["bounding_box"]["center"] = (10, 0, 0)
        graph["nodes"][3:5] = reversed(graph["nodes"][3:5])
        derived: Dict[int, Any] = {}
        add_sink_states(graph, [12, 11], [10], derived)
        self.assertEqual(derived[20]["states"], ["WASHED"])

    def test_faucet_with_null_geometry_is_ignored(self) -> None:
        graph = self.graph(bathroom_on=True)
        graph["edges"][2]["to_id"] = 1
        graph["nodes"][4]["bounding_box"] = None
        derived: Dict[int, Any] = {}
        add_sink_states(graph, [11, 12], [10], derived)
        self.assertEqual(derived[20]["states"], ["WASHED"])

    def test_all_faucets_without_geometry_do_not_wash(self) -> None:
        graph = self.graph(bathroom_on=True)
        graph["edges"][2]["to_id"] = 1
        graph["nodes"][3]["bounding_box"] = None
        graph["nodes"][4]["bounding_box"] = None
        derived: Dict[int, Any] = {}
        add_sink_states(graph, [11, 12], [10], derived)
        self.assertEqual(derived, {})

    def test_missing_sink_or_matching_faucet_does_not_wash(self) -> None:
        for faucets, sinks in (([], [10]), ([11, 12], [999])):
            with self.subTest(faucets=faucets, sinks=sinks):
                derived: Dict[int, Any] = {}
                add_sink_states(self.graph(), faucets, sinks, derived)
                self.assertEqual(derived, {})
