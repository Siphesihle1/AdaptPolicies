from io import StringIO
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock

from virtual_home.actions import Find, Grab, PutBack


class ObjectResolutionTests(unittest.TestCase):
    def environment(self):
        nodes = [
            {"id": 10, "class_name": "book"},
            {"id": 20, "class_name": "book"},
            {"id": 30, "class_name": "sofa"},
        ]
        return SimpleNamespace(
            graph={"nodes": nodes, "edges": []},
            find_obj=lambda name: [
                node["id"] for node in nodes if node["class_name"] == name
            ],
            obj_ids_in_hand=[],
            obj_ids_close=[20],
            object_bindings={},
            found_id=None,
            execute=MagicMock(return_value=True),
            log_file=StringIO(),
        )

    def test_find_other_class_does_not_lose_previously_selected_object(self):
        env = self.environment()
        Find(env, None).action("book")
        self.assertEqual(env.object_bindings["book"], 20)
        Find(env, None).action("sofa")
        env.obj_ids_close = []
        Grab(env, None).action("book")
        env.execute.assert_called_with("<char0> [grab] <book> (20)")

    def test_held_object_is_not_shadowed_by_local_duplicate(self):
        env = self.environment()
        env.find_obj = lambda name: [20] if name == "book" else [30]
        env.obj_ids_in_hand = [10]
        env.object_bindings = {"book": 20}
        env.found_id = 30
        PutBack(env, None).action("book", "sofa")
        env.execute.assert_called_with("<char0> [putback] <book> (10) <sofa> (30)")

    def test_failed_navigation_does_not_commit_binding_or_last_find(self):
        env = self.environment()
        env.execute.return_value = False
        self.assertFalse(Find(env, None).action("book"))
        self.assertEqual(env.object_bindings, {})
        self.assertIsNone(env.found_id)

    def test_resolution_is_stable_and_does_not_replace_rejected_actions(self):
        env = self.environment()
        env.obj_ids_close = []
        env.graph["nodes"].reverse()
        env.execute.return_value = False
        self.assertFalse(Grab(env, None).action("book"))
        env.execute.assert_called_once_with("<char0> [grab] <book> (10)")
        self.assertIn("selected=10", env.log_file.getvalue())

    def test_unbound_duplicate_prefers_nearest_native_position(self):
        env = self.environment()
        env.obj_ids_close = []
        env.object_distances = {10: 10.6, 20: 0.65}
        Find(env, None).action("book")
        env.execute.assert_called_once_with("<char0> [find] <book> (20)")
