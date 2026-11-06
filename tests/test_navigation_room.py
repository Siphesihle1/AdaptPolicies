import copy
import unittest

from virtual_home.environment import reconcile_navigation_room


class NavigationRoomTests(unittest.TestCase):
    def graphs(self):
        graph = {
            "nodes": [
                {"id": 1, "class_name": "character", "category": "Characters"},
                {"id": 205, "class_name": "kitchen", "category": "Rooms"},
                {"id": 335, "class_name": "livingroom", "category": "Rooms"},
                {"id": 418, "class_name": "wallpictureframe", "category": "Props"},
            ],
            "edges": [
                {"from_id": 1, "relation_type": "INSIDE", "to_id": 205},
                {"from_id": 1, "relation_type": "CLOSE", "to_id": 418},
                {"from_id": 418, "relation_type": "INSIDE", "to_id": 205},
            ],
        }
        native = copy.deepcopy(graph)
        native["edges"][0]["to_id"] = 335
        return graph, native

    def test_boundary_approach_uses_actual_character_room_and_preserves_object_ownership(
        self,
    ):
        graph, native = self.graphs()
        before = copy.deepcopy(graph)
        result = reconcile_navigation_room(graph, native)
        self.assertIn(native["edges"][0], result["edges"])
        self.assertNotIn(graph["edges"][0], result["edges"])
        self.assertEqual(result["nodes"], graph["nodes"])
        for edge in graph["edges"][1:]:
            self.assertIn(edge, result["edges"])
        self.assertEqual(graph, before)

    def test_ambiguous_or_unknown_native_room_rejects(self):
        graph, native = self.graphs()
        for edges in (
            [],
            [*native["edges"], graph["edges"][0]],
            [{"from_id": 1, "relation_type": "INSIDE", "to_id": 418}],
        ):
            with self.subTest(edges=edges):
                native["edges"] = edges
                with self.assertRaises(ValueError):
                    reconcile_navigation_room(graph, native)
