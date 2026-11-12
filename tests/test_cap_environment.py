import unittest
from virtual_home.actions import Grab
from virtual_home.task import VHTask
from virtual_home.virtualhome_types import ObjectRef
from methods.cap.environment import CaPEnvironment
from cap_fakes import FakeEnvironment


class EnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.task = VHTask("test", "thread", ["test"], 100)
        self.env = FakeEnvironment(task=self.task)
        self.api = CaPEnvironment(self.env, self.task)

    def test_visibility_uncertainty_and_revision(self):
        objects = self.api.get_visible_objects()
        self.assertEqual([o.id for o in objects], [10, 20, 21])
        fridge, mug = objects[:2]
        self.assertEqual(self.api.get_object_states(mug), frozenset())
        self.assertIsNone(self.api.get_objects_in(fridge))
        result = self.api.action("open", fridge)
        self.assertEqual(result.status, "succeeded")
        self.assertEqual(result.observation_revision, 1)
        self.assertEqual([o.id for o in self.api.get_objects_in(fridge)], [30])
        self.assertEqual(self.api.get_objects_in(mug), [])
        with self.assertRaises(TypeError):
            bool(result)

    def test_stale_and_forged_instance_rejected(self):
        for ref in [ObjectRef("previous-episode", 20, "mug"), ObjectRef(self.env.episode_id, 20, "apple")]:
            with self.assertRaises(ValueError):
                self.api.get_object_states(ref)
            with self.assertRaises(ValueError):
                Grab(self.env, self.task)(ref)
        self.assertEqual(self.env.calls, [])

    def test_exact_duplicate_held_string_and_failure_results(self):
        mug = self.api.get_visible_objects()[-1]
        self.assertEqual(self.api.action("grab", mug).status, "succeeded")
        self.assertIn("<mug> (21)", self.env.calls[-1])
        self.assertTrue(self.api.is_holding(mug))
        self.assertEqual(self.api.action("touch", "mug").status, "failed")
        self.assertIn("<mug> (21)", self.env.calls[-1])
        self.env.actions_to_omit = [("grab", "mug")]
        self.assertEqual(self.api.action("grab", mug).status, "skipped")

    def test_hidden_current_states_are_unknown(self):
        apple = ObjectRef(self.env.episode_id, 30, "apple")
        self.assertIsNone(self.api.get_object_states(apple))
        with self.assertRaisesRegex(ValueError, "not_currently_observed"):
            self.api.action("grab", apple)

    def test_native_failure_is_terminal(self):
        self.env.execution_failed = self.env.native_state_uncertain = True
        with self.assertRaisesRegex(RuntimeError, "uncertain_native_state"):
            self.api.action("open", "fridge")

    def test_clean_native_rejection_is_a_failed_action(self):
        def reject(script):
            self.env.execution_failed = True
            return False
        self.env.execute = reject
        self.assertEqual(self.api.action("open", "fridge").status, "failed")
        self.assertEqual(self.api.action("open", "fridge").status, "skipped")

    def test_context_describes_only_visible_states_and_relations(self):
        context = self.api.context()
        observation = context["observation"]
        self.assertEqual(observation["current_room"], "kitchen")
        self.assertIn("fridge is CLOSED", observation["visible_objects"])
        self.assertIn("mug (2)", observation["visible_objects"])
        self.assertIn("fridge INSIDE kitchen", observation["relations"])
        self.assertFalse(any("apple" in fact for fact in observation["visible_objects"] + observation["relations"]))
        self.assertFalse(any("bedroom" in fact for fact in observation["relations"]))
        self.api.action("open", "fridge")
        fresh = self.api.context()["observation"]
        self.assertIn("apple INSIDE fridge", fresh["relations"])
        self.assertIn("fridge is OPEN", fresh["visible_objects"])
        self.assertIn("fridge is CLOSED", observation["visible_objects"])

    def test_context_tracks_room_and_possession_after_moving(self):
        mug = self.api.get_visible_objects()[1]
        self.api.action("grab", mug)
        for edge in self.env.graph["edges"]:
            if edge["from_id"] == self.env.agent and edge["relation_type"] == "INSIDE":
                edge["to_id"] = 2
        self.env.get_current_state()
        observation = self.api.context()["observation"]
        self.assertEqual(observation["current_room"], "bedroom")
        self.assertEqual(observation["held_objects"], ["mug"])
        self.assertIn("character HOLDS_RH mug", observation["relations"])
        self.assertNotIn("fridge is CLOSED", observation["visible_objects"])

    def test_derived_effects_persist_but_hidden_state_is_not_disclosed(self):
        apple = ObjectRef(self.env.episode_id, 30, "apple")
        self.env.nodes_with_additonal_states[30] = {"states": ["OPEN", "WASHED"]}
        self.assertIsNone(self.api.get_object_states(apple))
        self.assertFalse(any("WASHED" in fact for fact in self.api.context()["observation"]["visible_objects"]))
        self.api.action("open", "fridge")
        self.assertEqual(self.api.get_object_states(apple), frozenset({"WASHED"}))
        self.assertIn("apple is WASHED", self.api.context()["observation"]["visible_objects"])
