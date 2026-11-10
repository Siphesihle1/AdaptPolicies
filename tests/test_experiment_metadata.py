from contextlib import contextmanager
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from methods import generation_metrics, telemetry
from methods.progprompt import run_eval


class ExperimentMetadataTests(unittest.TestCase):
    def test_main_context_covers_entire_run_and_names_each_repeat(self):
        args = SimpleNamespace(expt_name="condition", test_set="test_seen", env_id=0)
        active = []

        @contextmanager
        def capture(values):
            active.append(values)
            yield
            active.pop()

        with patch.dict(
            os.environ, {"EXPERIMENT_REPEAT": "2", "EXPERIMENT_RUN_ID": "run-2"}
        ), patch.object(run_eval, "parse_args", return_value=args), patch.object(
            telemetry, "attributes", side_effect=capture
        ), patch.object(
            run_eval, "execute_progprompt_agent"
        ) as execute:
            execute.side_effect = lambda _: self.assertEqual(
                active[0]["experiment_name"], "condition"
            )
            run_eval.main([])
            self.assertEqual(os.environ["EXPERIMENT_NAME"], "condition")
        self.assertEqual(active, [])

    def test_chat_explicitly_keeps_experiment_metadata(self):
        backend = MagicMock()
        with patch.object(telemetry, "backend", return_value=backend), patch.object(
            telemetry,
            "experiment_attributes",
            return_value={"experiment_name": "condition", "repeat_index": 2},
        ):
            telemetry.publish_plan_chat([], "done", "task")
        attributes = backend.get_client.return_value.create_call.call_args.kwargs[
            "attributes"
        ]
        self.assertEqual(attributes["experiment_name"], "condition")
        self.assertEqual(attributes["repeat_index"], 2)
        self.assertEqual(attributes["source"], "recorded_plan_execution")

    def test_measurements_preserve_missing_usage_and_failed_requests(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(
            telemetry,
            "experiment_attributes",
            return_value={"experiment_name": "condition"},
        ):
            path = Path(directory) / "calls.jsonl"
            response = SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content=""), finish_reason="length"
                    )
                ],
                usage=None,
            )
            with patch.dict(os.environ, {"LLM_METRICS_FILE": str(path)}):
                generation_metrics.record_completion(
                    "plan", "prompt", {"max_tokens": 4}, 2.0, response=response
                )
                generation_metrics.record_completion(
                    "plan", "prompt", {}, 3.0, error=TimeoutError("deadline")
                )
            rows = [json.loads(line) for line in path.read_text().splitlines()]
        self.assertIsNone(rows[0]["usage"])
        self.assertEqual(rows[0]["finish_reason"], "length")
        self.assertEqual(rows[0]["prompt_sha256"], rows[1]["prompt_sha256"])
        self.assertEqual(rows[1]["error"], "TimeoutError: deadline")
