import unittest

from virtualhome.simulation.evolving_graph.environment import EnvironmentGraph
from virtualhome.simulation.evolving_graph.execution import ScriptExecutor
from virtualhome.simulation.evolving_graph.scripts import Script, parse_script_line


class LidlessBinAccessTests(unittest.TestCase):
    def executor(
        self, prefab="Garbage_can_8", container="garbagecan", held=True, close=True
    ):
        graph = {
            "nodes": [
                {
                    "id": 1,
                    "class_name": "character",
                    "category": "Characters",
                    "properties": [],
                    "states": [],
                },
                {
                    "id": 10,
                    "class_name": "kitchen",
                    "category": "Rooms",
                    "properties": [],
                    "states": [],
                },
                {
                    "id": 20,
                    "class_name": container,
                    "category": "Props",
                    "prefab_name": prefab,
                    "properties": ["CAN_OPEN", "CONTAINERS"],
                    "states": ["CLOSED"],
                },
                {
                    "id": 3,
                    "class_name": "apple",
                    "category": "Props",
                    "properties": ["GRABBABLE"],
                    "states": [],
                },
            ],
            "edges": [
                {"from_id": 1, "relation_type": "INSIDE", "to_id": 10},
                {"from_id": 20, "relation_type": "INSIDE", "to_id": 10},
                {"from_id": 3, "relation_type": "INSIDE", "to_id": 10 if held else 20},
            ],
        }
        if held:
            graph["edges"].append(
                {"from_id": 1, "relation_type": "HOLDS_RH", "to_id": 3}
            )
        if close:
            graph["edges"].extend(
                {"from_id": 1, "relation_type": "CLOSE", "to_id": target}
                for target in (3, 20)
            )
        return ScriptExecutor(EnvironmentGraph(graph), {})

    def test_native_verified_lidless_prefabs_allow_insertion_and_retrieval(self):
        for prefab in ("Garbage_can_2", "Garbage_can_6", "Garbage_can_8"):
            for held in (True, False):
                with self.subTest(prefab=prefab, held=held):
                    executor = self.executor(prefab=prefab, held=held)
                    action = (
                        "[putin] <apple> (3) <garbagecan> (20)"
                        if held
                        else "[grab] <apple> (3)"
                    )
                    success, state, _ = executor.execute(
                        Script([parse_script_line(action, 0)])
                    )
                    self.assertTrue(success, executor.info.get_error_string())
                    result = state.to_dict()
                    self.assertEqual(
                        next(n for n in result["nodes"] if n["id"] == 20)["states"],
                        ["CLOSED"],
                    )
                    if held:
                        self.assertIn(
                            {"from_id": 3, "relation_type": "INSIDE", "to_id": 20},
                            result["edges"],
                        )
                    else:
                        self.assertTrue(
                            any(
                                edge["from_id"] == 1
                                and edge["to_id"] == 3
                                and edge["relation_type"] in {"HOLDS_LH", "HOLDS_RH"}
                                for edge in result["edges"]
                            )
                        )

    def test_unknown_bin_prefabs_still_require_opening(self):
        for prefab in ("Garbage_can_1", "Garbage_can_99", None):
            for held in (True, False):
                executor = self.executor(prefab=prefab, held=held)
                action = (
                    "[putin] <apple> (3) <garbagecan> (20)"
                    if held
                    else "[grab] <apple> (3)"
                )
                success, _, _ = executor.execute(Script([parse_script_line(action, 0)]))
                self.assertFalse(success)

    def test_prefab_name_does_not_unlock_a_different_container_class(self):
        for container in ("fridge", "washingmachine", "kitchencabinet"):
            executor = self.executor(container=container)
            action = f"[putin] <apple> (3) <{container}> (20)"
            success, _, _ = executor.execute(Script([parse_script_line(action, 0)]))
            self.assertFalse(success)

    def test_lidless_access_requires_proximity_and_a_held_source(self):
        for held, close in ((True, False), (False, True)):
            executor = self.executor(held=held, close=close)
            success, _, _ = executor.execute(
                Script([parse_script_line("[putin] <apple> (3) <garbagecan> (20)", 0)])
            )
            self.assertFalse(success)
