import unittest

from virtualhome.simulation.evolving_graph.environment import EnvironmentGraph
from virtualhome.simulation.evolving_graph.execution import ScriptExecutor
from virtualhome.simulation.evolving_graph.scripts import Script, parse_script_line


class RugFoldingTests(unittest.TestCase):
    def executor(
        self,
        held=True,
        folded=False,
        full_hands=False,
        prefab="PRE_DEC_Rug_03_08",
        class_name="rug",
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
                    "id": 2,
                    "class_name": class_name,
                    "prefab_name": prefab,
                    "properties": ["GRABBABLE"],
                    "states": ["CLEAN"] + (["FOLDED"] if folded else []),
                },
                {
                    "id": 3,
                    "class_name": "book",
                    "properties": ["GRABBABLE"],
                    "states": [],
                },
            ],
            "edges": (
                [{"from_id": 1, "relation_type": "HOLDS_RH", "to_id": 2}]
                if held
                else []
            )
            + (
                [{"from_id": 1, "relation_type": "HOLDS_LH", "to_id": 3}]
                if full_hands
                else []
            ),
        }
        return ScriptExecutor(EnvironmentGraph(graph), {})

    def run_action(self, executor, action):
        return executor.execute(Script([parse_script_line(f"[{action}] <rug> (2)", 0)]))

    def test_fold_and_unfold_preserve_holding_and_other_states(self):
        for folded, action, expected in (
            (False, "fold", "FOLDED"),
            (True, "unfold", "UNFOLDED"),
        ):
            with self.subTest(action=action):
                executor = self.executor(folded=folded)
                success, state, _ = self.run_action(executor, action)
                self.assertTrue(success, executor.info.get_error_string())
                graph = state.to_dict()
                self.assertEqual(
                    set(next(n for n in graph["nodes"] if n["id"] == 2)["states"]),
                    {"CLEAN", expected},
                )
                self.assertIn(
                    {"from_id": 1, "relation_type": "HOLDS_RH", "to_id": 2},
                    graph["edges"],
                )

    def test_repeated_or_unheld_actions_are_rejected(self):
        for options, action in (
            ({"folded": True}, "fold"),
            ({}, "unfold"),
            ({"held": False}, "fold"),
            ({"full_hands": True}, "fold"),
        ):
            with self.subTest(options=options, action=action):
                self.assertFalse(self.run_action(self.executor(**options), action)[0])

    def test_unsupported_objects_do_not_gain_fold_states(self):
        for options in (
            {"prefab": "PRE_DEC_Rug_03_09"},
            {"prefab": None},
            {"class_name": "paper"},
        ):
            with self.subTest(options=options):
                self.assertFalse(self.run_action(self.executor(**options), "fold")[0])
