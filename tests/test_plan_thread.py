"""Plan thread identity, step nesting and failure traces without network access."""

from contextlib import contextmanager
from io import StringIO
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from methods import telemetry
from virtual_home.actions import Grab


class PlanThreadTests(unittest.TestCase):
    def test_nested_same_thread_keeps_turn_context_and_next_plan_is_separate(self):
        backend = MagicMock()
        with patch.object(telemetry, "backend", return_value=backend):
            with telemetry.thread(thread_id="plan-1"):
                with telemetry.thread(thread_id="plan-1"):
                    pass
            with telemetry.thread(thread_id="plan-2"):
                pass
        self.assertEqual(
            [call.kwargs for call in backend.thread.call_args_list],
            [{"thread_id": "plan-1"}, {"thread_id": "plan-2"}],
        )

    def test_exception_finishes_span_and_propagates_original_error(self):
        backend = MagicMock()
        client = backend.get_client.return_value
        error = RuntimeError("lost simulator")
        with patch.object(telemetry, "backend", return_value=backend):
            with self.assertRaises(RuntimeError) as caught:
                with telemetry.span(
                    "simulator_action", {"script": "grab mug"}
                ) as output:
                    output["stage"] = "render"
                    raise error
        self.assertIs(caught.exception, error)
        client.finish_call.assert_called_once_with(
            client.create_call.return_value, output={"stage": "render"}, exception=error
        )

    def test_disabled_tracing_does_not_load_a_client(self):
        with patch.object(telemetry, "backend", return_value=None):
            with telemetry.thread(thread_id="plan"), telemetry.span(
                "step", {}
            ) as output:
                output["success"] = True
        self.assertEqual(output, {"success": True})

    def test_action_records_result_and_skip_without_adding_executions(self):
        env = SimpleNamespace(
            find_obj=lambda _: [3],
            obj_ids_in_hand=[],
            found_id=3,
            log_file=StringIO(),
            execute=MagicMock(return_value=False),
            execution_failed=False,
            actions_to_omit=[],
        )
        task = SimpleNamespace(
            thread_id="plan",
            task_instruction="grab_mug",
            current_subtask="pick up",
            total_steps=0,
            terminate_current_subtask=False,
        )
        outputs = []

        @contextmanager
        def capture(name, inputs):
            output = {}
            outputs.append((name, inputs, output))
            yield output

        with patch.object(telemetry, "backend", return_value=None), patch.object(
            telemetry, "span", side_effect=capture
        ):
            Grab(env, task)("mug")
            env.execution_failed = True
            Grab(env, task)("mug")
        env.execute.assert_called_once_with("<char0> [grab] <mug> (3)")
        self.assertEqual(outputs[0][2], {"result": False, "status": "failed"})
        self.assertEqual(
            outputs[1][2], {"status": "skipped", "reason": "previous_unity_failure"}
        )
        self.assertEqual(task.total_steps, 2)
