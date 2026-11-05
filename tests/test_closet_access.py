import unittest

from virtualhome.simulation.evolving_graph.environment import EnvironmentGraph
from virtualhome.simulation.evolving_graph.execution import ScriptExecutor
from virtualhome.simulation.evolving_graph.scripts import Script, parse_script_line


class ClosetAccessTests(unittest.TestCase):
    def executor(self, container, held=False, close=True):
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
                    "category": "Furniture",
                    "properties": ["CAN_OPEN", "CONTAINERS"],
                    "states": ["CLOSED"],
                },
                {
                    "id": 3,
                    "class_name": "clothespile",
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
                [
                    {"from_id": 1, "relation_type": "CLOSE", "to_id": target}
                    for target in (3, 20)
                ]
            )
        return ScriptExecutor(EnvironmentGraph(graph), {})

    def test_closet_access_matches_native_controls_without_opening_it(self):
        for held, action in (
            (False, "[grab] <clothespile> (3)"),
            (True, "[putin] <clothespile> (3) <closet> (20)"),
        ):
            executor = self.executor("closet", held=held)
            success, state, _ = executor.execute(Script([parse_script_line(action, 0)]))
            self.assertTrue(success, executor.info.get_error_string())
            closet = next(n for n in state.to_dict()["nodes"] if n["id"] == 20)
            self.assertEqual(closet["states"], ["CLOSED"])

    def test_closed_fridge_and_cabinet_still_block_access(self):
        for container in ("fridge", "kitchencabinet", "washingmachine"):
            for held in (False, True):
                executor = self.executor(container, held=held)
                action = (
                    f"[putin] <clothespile> (3) <{container}> (20)"
                    if held
                    else "[grab] <clothespile> (3)"
                )
                success, _, _ = executor.execute(Script([parse_script_line(action, 0)]))
                self.assertFalse(success)

    def test_closet_access_still_requires_proximity_and_a_held_source(self):
        executor = self.executor("closet", held=True, close=False)
        success, _, _ = executor.execute(
            Script([parse_script_line("[putin] <clothespile> (3) <closet> (20)", 0)])
        )
        self.assertFalse(success)
        executor = self.executor("closet", held=False)
        success, _, _ = executor.execute(
            Script([parse_script_line("[putin] <clothespile> (3) <closet> (20)", 0)])
        )
        self.assertFalse(success)
