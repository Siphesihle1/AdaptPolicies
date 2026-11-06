import unittest

from virtualhome.simulation.evolving_graph.environment import EnvironmentGraph
from virtualhome.simulation.evolving_graph.execution import ScriptExecutor
from virtualhome.simulation.evolving_graph.scripts import Script, parse_script_line


class ToolActionTests(unittest.TestCase):
    def executor(
        self, opened=True, held=True, applied=False, prefab="PRE_PRO_Toothbrush_01"
    ):
        nodes = [
            dict(
                id=1,
                class_name="character",
                category="Characters",
                properties=[],
                states=[],
            ),
            dict(
                id=62,
                class_name="toothpaste",
                prefab_name="SHP_PRE_Toothpaste",
                properties=["GRABBABLE", "CAN_OPEN"],
                states=["OPEN" if opened else "CLOSED"],
            ),
            dict(
                id=65,
                class_name="toothbrush",
                prefab_name=prefab,
                properties=["GRABBABLE"],
                states=["CLEAN"] + (["APPLIED"] if applied else []),
            ),
        ]
        edges = [dict(from_id=1, relation_type="HOLDS_RH", to_id=65)]
        if held:
            edges.append(dict(from_id=1, relation_type="HOLDS_LH", to_id=62))
        return ScriptExecutor(EnvironmentGraph(dict(nodes=nodes, edges=edges)), {})

    def run_script(self, executor, actions):
        return executor.execute(
            Script([parse_script_line(action, i) for i, action in enumerate(actions)])
        )

    def test_apply_then_use_consumes_preparation_and_retains_other_state(self):
        executor = self.executor()
        success, state, _ = self.run_script(
            executor,
            ["[apply] <toothpaste> (62) <toothbrush> (65)", "[use] <toothbrush> (65)"],
        )
        self.assertTrue(success, executor.info.get_error_string())
        graph = state.to_dict()
        self.assertEqual(
            set(next(n for n in graph["nodes"] if n["id"] == 65)["states"]),
            {"CLEAN", "USED"},
        )
        self.assertEqual(len(graph["edges"]), 2)

    def test_invalid_source_and_repeated_preparation_reject(self):
        for options in (
            {"opened": False},
            {"held": False},
            {"applied": True},
            {"prefab": "unsupported"},
        ):
            with self.subTest(options=options):
                self.assertFalse(
                    self.run_script(
                        self.executor(**options),
                        ["[apply] <toothpaste> (62) <toothbrush> (65)"],
                    )[0]
                )

    def test_dry_or_repeated_use_rejects(self):
        self.assertFalse(
            self.run_script(self.executor(), ["[use] <toothbrush> (65)"])[0]
        )
        self.assertFalse(
            self.run_script(
                self.executor(applied=True),
                ["[use] <toothbrush> (65)", "[use] <toothbrush> (65)"],
            )[0]
        )
