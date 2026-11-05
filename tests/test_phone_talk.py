import unittest
import io
from types import SimpleNamespace
from unittest.mock import Mock

from virtual_home.actions import Read, Talk

from virtualhome.simulation.evolving_graph.environment import EnvironmentGraph
from virtualhome.simulation.evolving_graph.execution import ScriptExecutor
from virtualhome.simulation.evolving_graph.scripts import Script, parse_script_line


class PhoneTalkTests(unittest.TestCase):
    def test_generated_actions_select_a_held_instance(self):
        for action_class, name, verb in (
            (Talk, "cellphone", "talk"),
            (Read, "book", "read"),
        ):
            env = SimpleNamespace(
                find_obj=lambda _: [2, 3],
                obj_ids_in_hand=[3],
                found_id=2,
                log_file=io.StringIO(),
                execute=Mock(return_value=True),
                execution_failed=False,
                actions_to_omit=[],
            )
            task = SimpleNamespace(total_steps=0, terminate_current_subtask=False)
            action_class(env, task)(name)
            env.execute.assert_called_once_with(f"<char0> [{verb}] <{name}> (3)")

    def execute(self, name="cellphone", held=True):
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
                    "class_name": name,
                    "category": "Props",
                    "properties": ["GRABBABLE"],
                    "states": ["OFF"],
                },
            ],
            "edges": (
                [{"from_id": 1, "relation_type": "HOLDS_RH", "to_id": 2}]
                if held
                else []
            ),
        }
        executor = ScriptExecutor(EnvironmentGraph(graph), {})
        success, state, _ = executor.execute(
            Script([parse_script_line(f"[talk] <{name}> (2)", 0)])
        )
        return success, state.to_dict()

    def test_talk_requires_a_held_phone(self):
        self.assertTrue(self.execute()[0])
        self.assertFalse(self.execute(held=False)[0])
        self.assertFalse(self.execute(name="radio")[0])

    def test_talk_does_not_switch_power_or_release_phone(self):
        success, graph = self.execute()
        self.assertTrue(success)
        self.assertEqual(
            next(n["states"] for n in graph["nodes"] if n["id"] == 2), ["OFF"]
        )
        self.assertIn(
            {"from_id": 1, "relation_type": "HOLDS_RH", "to_id": 2}, graph["edges"]
        )
