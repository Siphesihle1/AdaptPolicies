"""Check symbolic room updates without starting Unity."""

import unittest

from virtualhome.simulation.evolving_graph.environment import (
    EnvironmentGraph,
    EnvironmentState,
    Relation,
)
from virtualhome.simulation.evolving_graph.execution import ScriptExecutor
from virtualhome.simulation.evolving_graph.scripts import Script, parse_script_line
from virtualhome.simulation.evolving_graph.utils import get_visible_nodes


class CarriedObjectRoomTests(unittest.TestCase):
    def make_executor(self, source: int, destination: int):
        def node(identifier: int, name: str, category: str):
            return {
                "id": identifier,
                "class_name": name,
                "category": category,
                "properties": [],
                "states": [],
            }

        def edge(source: int, relation: str, destination: int):
            return {"from_id": source, "relation_type": relation, "to_id": destination}

        graph = EnvironmentGraph(
            {
                "nodes": [
                    node(1, "character", "Characters"),
                    node(10, "kitchen", "Rooms"),
                    node(20, "livingroom", "Rooms"),
                    node(3, "mug", "Props"),
                    node(4, "plate", "Props"),
                    node(30, "sink", "Furniture"),
                ],
                "edges": [
                    edge(1, "INSIDE", source),
                    edge(3, "INSIDE", source),
                    edge(4, "INSIDE", source),
                    edge(1, "HOLDS_RH", 3),
                    edge(1, "HOLDS_LH", 4),
                    edge(30, "INSIDE", destination),
                ],
            }
        )
        return ScriptExecutor(graph, {}), EnvironmentState(
            graph, {}, instance_selection=True
        )

    def assert_room(self, state: EnvironmentState, identifier: int, room: int):
        self.assertEqual(
            {
                node.id
                for node in state.get_nodes_from(
                    state.get_node(identifier), Relation.INSIDE
                )
            },
            {room},
        )

    def test_movement_updates_both_hands_to_the_characters_updated_room(self):
        for action in ("walk", "run", "find"):
            for source, destination in ((10, 20), (20, 10), (10, 10)):
                for in_place in (False, True):
                    with self.subTest(
                        action=action,
                        source=source,
                        destination=destination,
                        in_place=in_place,
                    ):
                        executor, state = self.make_executor(source, destination)
                        before = state.to_dict()
                        target = (
                            "<sink> (30)"
                            if action == "find"
                            else f"<{state.get_node(destination).class_name}> ({destination})"
                        )
                        script = Script([parse_script_line(f"[{action}] {target}", 0)])
                        success, moved = executor.execute_one_step(
                            script, state, in_place=in_place
                        )
                        self.assertTrue(success, executor.info.get_error_string())
                        for identifier in (1, 3, 4):
                            self.assert_room(moved, identifier, destination)
                        self.assertTrue(
                            moved.has_edge(
                                moved.get_node(1), Relation.HOLDS_RH, moved.get_node(3)
                            )
                        )
                        self.assertTrue(
                            moved.has_edge(
                                moved.get_node(1), Relation.HOLDS_LH, moved.get_node(4)
                            )
                        )
                        if not in_place:
                            self.assertEqual(state.to_dict(), before)

    def test_check_only_does_not_move_character_or_carried_objects(self):
        executor, state = self.make_executor(10, 20)
        script = Script([parse_script_line("[walk] <livingroom> (20)", 0)])
        before = state.to_dict()
        self.assertTrue(executor.check_one_step(script, state))
        self.assertEqual(state.to_dict(), before)

    def test_putback_after_cross_room_find_keeps_mug_visible(self):
        executor, state = self.make_executor(20, 10)
        for action in ("[find] <sink> (30)", "[putback] <mug> (3) <sink> (30)"):
            success, state = executor.execute_one_step(
                Script([parse_script_line(action, 0)]), state
            )
            self.assertTrue(success, executor.info.get_error_string())
        self.assert_room(state, 3, 10)
        self.assertTrue(
            state.has_edge(state.get_node(3), Relation.ON, state.get_node(30))
        )
        self.assertFalse(
            state.has_edge(state.get_node(1), Relation.HOLDS_RH, state.get_node(3))
        )
        visible = get_visible_nodes(state.to_dict(), agent_id=1)
        self.assertIn(3, {node["id"] for node in visible["nodes"]})
