"""Verify that rejected native actions cannot advance symbolic execution."""

import io
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from virtual_home.environment import VHEnvironment, unity_execution_succeeded


class UnityExecutionTests(unittest.TestCase):
    def environment(self, response=(True, {"0": {"message": "Success"}})):
        env = VHEnvironment.__new__(VHEnvironment)
        env.execution_failed = env.native_state_uncertain = False
        env.log_file = io.StringIO()
        env.task = SimpleNamespace(step=0, executable_steps=0, thread_id="test")
        env.comm = SimpleNamespace(render_script=Mock(return_value=response))
        env.executor = SimpleNamespace(
            execute=Mock(return_value=(True, "candidate-state", [])),
            info=SimpleNamespace(get_error_string=lambda: "Invalid action"),
        )
        env.update_executor = Mock()
        env.get_observation = Mock()
        env.get_current_state = Mock()
        env.partial_graph = {"nodes": [], "edges": []}
        env.graph = env.partial_graph
        env.obj_ids_for_adding_states = ([], [], [], [], [], [], [])
        env.nodes_with_additonal_states = {}
        return env

    def test_response_requires_transport_and_character_success(self):
        for response in (
            (False, {"0": {"message": "Success"}}),
            (True, {"0": {"message": "Script impossible to execute"}}),
            (True, {"0": {"message": "Success"}, "1": {"message": "Failed"}}),
            (True, {}),
            (True, None),
            None,
        ):
            with self.subTest(response=response):
                self.assertFalse(unity_execution_succeeded(response))
        self.assertTrue(unity_execution_succeeded((True, "Success")))
        self.assertTrue(
            unity_execution_succeeded((True, {"0": {"message": "Success"}}))
        )

    def test_native_rejection_preserves_state_and_blocks_later_actions(self):
        env = self.environment((False, {"0": {"message": "Rejected"}}))
        self.assertFalse(env.execute("<char0> [grab] <mug> (3)"))
        self.assertTrue(env.execution_failed)
        self.assertFalse(env.native_state_uncertain)
        self.assertFalse(env.native_in_flight)
        self.assertEqual(env.task.executable_steps, 0)
        env.update_executor.assert_not_called()
        env.get_observation.assert_not_called()
        self.assertFalse(env.execute("<char0> [putback] <mug> (3) <sink> (4)"))
        env.comm.render_script.assert_called_once()
        env.executor.execute.assert_called_once()

    def test_invalid_script_and_symbolic_rejection_never_reach_unity(self):
        env = self.environment()
        self.assertFalse(env.execute("<char0> invalid"))
        env.executor.execute.return_value = (False, "unchanged", [])
        self.assertFalse(env.execute("<char0> [grab] <mug> (3)"))
        env.comm.render_script.assert_not_called()
        env.update_executor.assert_not_called()
        self.assertEqual(env.task.executable_steps, 0)

    def test_contact_failure_blocks_later_actions(self):
        env = self.environment()
        env.comm.render_script.side_effect = ConnectionError("lost contact")
        with self.assertRaises(ConnectionError):
            env.execute("<char0> [grab] <mug> (3)")
        self.assertTrue(env.execution_failed)
        self.assertTrue(env.native_state_uncertain)
        env.update_executor.assert_not_called()

    def test_joint_success_commits_candidate_once(self):
        env = self.environment()
        with patch("virtual_home.environment.weave.thread"):
            self.assertTrue(env.execute("<char0> [grab] <mug> (3)"))
        self.assertFalse(env.execution_failed)
        self.assertEqual(env.task.executable_steps, 1)
        env.update_executor.assert_called_once_with("candidate-state")
        env.get_current_state.assert_called_once()
        env.comm.render_script.assert_called_once_with(
            ["<char0> [grab] <mug> (3)"],
            recording=False,
            skip_animation=True,
            find_solution=False,
        )

    def test_closed_washer_derives_effects_without_exposing_hidden_contents(self):
        env = self.environment()
        washer = {"id": 72, "class_name": "washingmachine", "category": "Appliances",
                  "states": ["CLOSED", "ON"], "properties": ["CAN_OPEN"]}
        clothes = {"id": 286, "class_name": "clothespile", "category": "Props",
                   "states": ["CLOSED"], "properties": []}
        env.graph = {"nodes": [washer, clothes],
                     "edges": [{"from_id": 286, "to_id": 72, "relation_type": "INSIDE"}]}
        env.partial_graph = {"nodes": [washer], "edges": []}
        env.obj_ids_for_adding_states = ([], [], [], [], [72], [], [])
        with patch("virtual_home.environment.weave.thread"):
            self.assertTrue(env.execute("<char0> [switchon] <washingmachine> (72)"))
        self.assertIn("WASHED", env.nodes_with_additonal_states[286]["states"])
        self.assertEqual([node["id"] for node in env.partial_graph["nodes"]], [72])

    def test_navigation_refreshes_resolution_distances_from_native_pose(self):
        env = self.environment()
        env.comm.environment_graph = Mock(
            return_value=(
                True,
                {
                    "nodes": [
                        {
                            "id": 1,
                            "class_name": "character",
                            "bounding_box": {"center": [10, 1, 0]},
                        },
                        {
                            "id": 2,
                            "class_name": "mug",
                            "bounding_box": {"center": [0, 1, 0]},
                        },
                        {
                            "id": 3,
                            "class_name": "mug",
                            "bounding_box": {"center": [11, 1, 0]},
                        },
                    ],
                    "edges": [],
                },
            )
        )
        with patch("virtual_home.environment.weave.thread"):
            self.assertTrue(env.execute("<char0> [find] <mug> (3)"))
        self.assertEqual(env.object_distances[2], 100)
        self.assertEqual(env.object_distances[3], 1)

    def test_only_confirmed_phone_talk_derives_used(self):
        for native_success in (True, False):
            with self.subTest(native_success=native_success):
                env = self.environment((native_success, {"0": {"message": "Success"}}))
                env.partial_graph["nodes"] = [
                    {
                        "id": 3,
                        "class_name": "cellphone",
                        "category": "Props",
                        "states": ["OFF"],
                    }
                ]
                with patch("virtual_home.environment.weave.thread"):
                    self.assertEqual(
                        env.execute("<char0> [talk] <cellphone> (3)"), native_success
                    )
                self.assertEqual(3 in env.nodes_with_additonal_states, native_success)
                if native_success:
                    self.assertEqual(
                        env.nodes_with_additonal_states[3]["states"], ["OFF", "USED"]
                    )

    def test_distance_cache_uses_all_three_axes_and_excludes_partial_centers(self):
        env = self.environment()
        env.update_object_distances(
            {
                "nodes": [
                    {
                        "id": 1,
                        "class_name": "character",
                        "bounding_box": {"center": [1, 2, 3]},
                    },
                    {
                        "id": 2,
                        "class_name": "mug",
                        "bounding_box": {"center": [3, 5, 9]},
                    },
                    {"id": 3, "class_name": "mug", "bounding_box": {"center": [1, 2]}},
                    {"id": 4, "class_name": "mug"},
                ],
                "edges": [],
            }
        )
        self.assertEqual(env.object_distances, {1: 0, 2: 49})
        env.update_object_distances({"nodes": [], "edges": []})
        self.assertEqual(env.object_distances, {})
