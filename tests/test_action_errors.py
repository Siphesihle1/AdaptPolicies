"""Action failure messages and the optional stop after a Unity rejection."""

import unittest

from cap_fakes import FakeEnvironment
import test_unity_execution
from virtual_home import actions
from virtual_home.task import VHTask
from virtual_home.virtualhome_types import ObjectRef


class UnityRejectionTests(unittest.TestCase):
    environment = test_unity_execution.UnityExecutionTests.environment

    def test_rejection_is_recoverable_when_the_method_continues(self):
        env = self.environment((False, {"0": {"message": "Rejected"}}))
        env.stop_after_unity_rejection = False
        self.assertFalse(env.execute("<char0> [grab] <mug> (3)"))
        # Nothing ran: no state change, no uncertainty, and later actions still run.
        self.assertFalse(env.execution_failed)
        self.assertFalse(env.native_state_uncertain)
        self.assertFalse(env.native_in_flight)
        self.assertEqual(env.task.executable_steps, 0)
        env.update_executor.assert_not_called()
        env.get_observation.assert_not_called()
        self.assertIn("Unity rejected action", env.last_action_error)
        self.assertIn("Rejected", env.last_action_error)
        # The next action is sent to Unity instead of being skipped.
        self.assertFalse(env.execute("<char0> [putback] <mug> (3) <sink> (4)"))
        self.assertEqual(env.comm.render_script.call_count, 2)
        self.assertEqual(env.executor.execute.call_count, 2)

    def test_rejection_still_stops_the_task_by_default(self):
        env = self.environment((False, {"0": {"message": "Rejected"}}))
        self.assertTrue(env.stop_after_unity_rejection)
        self.assertFalse(env.execute("<char0> [grab] <mug> (3)"))
        self.assertTrue(env.execution_failed)
        self.assertFalse(env.execute("<char0> [putback] <mug> (3) <sink> (4)"))
        self.assertEqual(env.last_action_error, "Task stopped after Unity failure")
        env.comm.render_script.assert_called_once()

    def test_symbolic_and_parse_failures_record_their_message(self):
        env = self.environment()
        self.assertFalse(env.execute("<char0> invalid"))
        self.assertIn("Failed to parse script line", env.last_action_error)
        env.executor.execute.return_value = (False, "unchanged", [])
        self.assertFalse(env.execute("<char0> [grab] <mug> (3)"))
        self.assertEqual(env.last_action_error, "Invalid action")


class ActionMessageTests(unittest.TestCase):
    def setUp(self):
        self.task = VHTask("test", "offline", ["test"], 100)
        self.env = FakeEnvironment(task=self.task)

    def test_unresolved_objects_and_generic_failures_have_messages(self):
        self.assertFalse(actions.Grab(self.env, self.task)("sofa"))
        self.assertEqual(self.env.last_action_error, "Object sofa not found")
        self.assertFalse(actions.PutIn(self.env, self.task)("mug", "fridge"))
        self.assertEqual(self.env.last_action_error, "Object mug not in hand")
        mug = ObjectRef(self.env.episode_id, 20, "mug")
        self.assertFalse(actions.PutIn(self.env, self.task)(mug, "fridge"))
        self.assertEqual(self.env.last_action_error, "Object mug (20) not in hand")
        # The fake simulator rejects touch without giving a reason.
        self.assertFalse(actions.Touch(self.env, self.task)("mug"))
        self.assertEqual(self.env.last_action_error, "touch could not be executed")

    def test_success_clears_the_previous_message(self):
        self.assertFalse(actions.Grab(self.env, self.task)("sofa"))
        self.assertTrue(actions.Open(self.env, self.task)("fridge"))
        self.assertIsNone(self.env.last_action_error)


if __name__ == "__main__":
    unittest.main()
