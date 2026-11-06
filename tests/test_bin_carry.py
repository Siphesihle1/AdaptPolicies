import unittest

from virtualhome.simulation.evolving_graph.environment import EnvironmentGraph
from virtualhome.simulation.evolving_graph.execution import ScriptExecutor
from virtualhome.simulation.evolving_graph.scripts import Script, parse_script_line


class BinCarryTests(unittest.TestCase):
    def executor(
        self,
        prefab="Garbage_can_8",
        class_name="garbagecan",
        movable=True,
        filled=False,
        close=True,
        full_hands=False,
        enclosed=False,
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
                    "class_name": class_name,
                    "category": "Furniture",
                    "prefab_name": prefab,
                    "properties": ["CONTAINERS", "CAN_OPEN"]
                    + (["MOVABLE"] if movable else []),
                    "states": ["CLOSED"],
                },
                {
                    "id": 3,
                    "class_name": "apple",
                    "category": "Props",
                    "properties": ["GRABBABLE"],
                    "states": [],
                },
                {
                    "id": 4,
                    "class_name": "plum",
                    "category": "Props",
                    "properties": ["GRABBABLE"],
                    "states": [],
                },
            ],
            "edges": [
                {"from_id": 1, "relation_type": "INSIDE", "to_id": 10},
                {"from_id": 20, "relation_type": "INSIDE", "to_id": 10},
                {
                    "from_id": 3,
                    "relation_type": "INSIDE",
                    "to_id": 20 if filled else 10,
                },
                {"from_id": 4, "relation_type": "INSIDE", "to_id": 10},
            ],
        }
        if close:
            graph["edges"].append({"from_id": 1, "relation_type": "CLOSE", "to_id": 20})
        if full_hands:
            graph["edges"].extend(
                [
                    {"from_id": 1, "relation_type": "HOLDS_RH", "to_id": 3},
                    {"from_id": 1, "relation_type": "HOLDS_LH", "to_id": 4},
                ]
            )
        if enclosed:
            graph["nodes"].append(
                {
                    "id": 30,
                    "class_name": "fridge",
                    "category": "Furniture",
                    "properties": ["CONTAINERS", "CAN_OPEN"],
                    "states": ["CLOSED"],
                }
            )
            graph["edges"].append(
                {"from_id": 20, "relation_type": "INSIDE", "to_id": 30}
            )
        return ScriptExecutor(EnvironmentGraph(graph), {})

    def test_empty_native_verified_movable_bin_can_be_held(self):
        executor = self.executor()
        success, state, _ = executor.execute(
            Script([parse_script_line("[grab] <garbagecan> (20)", 0)])
        )
        self.assertTrue(success, executor.info.get_error_string())
        self.assertIn(
            {"from_id": 1, "relation_type": "HOLDS_RH", "to_id": 20},
            state.to_dict()["edges"],
        )

    def test_other_bins_and_missing_prefabs_keep_existing_grab_rules(self):
        for prefab in ("Garbage_can_2", "Garbage_can_6", "Garbage_can_99", None):
            with self.subTest(prefab=prefab):
                executor = self.executor(prefab=prefab)
                success, _, _ = executor.execute(
                    Script([parse_script_line("[grab] <garbagecan> (20)", 0)])
                )
                self.assertFalse(success)

    def test_filled_nonmovable_distant_or_enclosed_bin_is_rejected(self):
        for options in (
            {"filled": True},
            {"movable": False},
            {"close": False},
            {"full_hands": True},
            {"enclosed": True},
        ):
            with self.subTest(options=options):
                executor = self.executor(**options)
                success, _, _ = executor.execute(
                    Script([parse_script_line("[grab] <garbagecan> (20)", 0)])
                )
                self.assertFalse(success)

    def test_prefab_name_cannot_unlock_other_furniture(self):
        executor = self.executor(class_name="fridge")
        success, _, _ = executor.execute(
            Script([parse_script_line("[grab] <fridge> (20)", 0)])
        )
        self.assertFalse(success)

    def test_bin_cannot_be_grabbed_twice(self):
        executor = self.executor()
        script = Script(
            [parse_script_line("[grab] <garbagecan> (20)", i) for i in range(2)]
        )
        success, _, _ = executor.execute(script)
        self.assertFalse(success)
