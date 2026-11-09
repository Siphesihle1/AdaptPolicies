"""Chat presentation retains execution events without adding model requests."""

from types import SimpleNamespace
import json
import unittest
from unittest.mock import MagicMock, patch

from PIL import Image

from methods import llm, telemetry
from methods.chat_transcript import PlanChatTranscript, capture_transcript, code_block


class ChatTranscriptTests(unittest.TestCase):
    def test_complete_chat_contains_planning_assertions_actions_and_observations(self):
        transcript = PlanChatTranscript()
        provider = MagicMock()
        provider.settings = {"plan": {}, "assertion": {}}
        provider.generate.side_effect = ["def task():\n    grab('mug')", "True"]
        with patch.object(telemetry, "backend", return_value=None), patch.object(
            llm, "get_provider", return_value=provider
        ), capture_transcript(transcript):
            llm.generate("planning context", "plan")
            with telemetry.span(
                "plan_action", {"action": "grab", "objects": ["mug"]}
            ) as action:
                with telemetry.span(
                    "simulator_action", {"script_instruction": "[grab] <mug> (3)"}
                ) as native:
                    native.update(success=True, unity_response=[True, "Success"])
                with telemetry.span("initial_image", {}) as observation:
                    observation["image"] = Image.new("RGB", (2, 2))
                with telemetry.span("observe_state", {"step": 1}) as observation:
                    observation.update(state="You have mug.", room="kitchen")
                action.update(result=True, status="succeeded")
            llm.generate("assert mug in hands", "assertion")
        messages = transcript.messages
        text = "\n".join(str(message["content"]) for message in messages)
        for expected in [
            "planning context",
            "def task",
            "grab('mug')",
            "Success",
            "You have mug.",
            "assert mug in hands",
            "True",
        ]:
            self.assertIn(expected, text)
        self.assertEqual(provider.generate.call_count, 2)
        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[1]["role"], "assistant")
        self.assertFalse(any(message["role"] == "system" for message in messages))
        self.assertIn("```python\ndef task():", messages[1]["content"])
        result_message = next(
            message["content"]
            for message in messages
            if isinstance(message["content"], str)
            and "**Action result**" in message["content"]
        )
        self.assertIn("\n\n```json\n{\n", result_message)
        self.assertTrue(
            any(
                isinstance(message["content"], list)
                and message["content"][1]["image_url"]["url"].startswith(
                    "data:image/png;base64,"
                )
                for message in messages
            )
        )

    def test_separate_plans_and_exceptions_are_not_merged(self):
        first, second = PlanChatTranscript(), PlanChatTranscript()
        with patch.object(telemetry, "backend", return_value=None):
            with capture_transcript(first), self.assertRaisesRegex(
                RuntimeError, "failed"
            ):
                with telemetry.span(
                    "plan_action", {"action": "grab", "objects": ["mug"]}
                ):
                    raise RuntimeError("failed")
            with capture_transcript(second), telemetry.span(
                "observe_state", {}
            ) as output:
                output["state"] = "another plan"
        self.assertIn("RuntimeError: failed", first.messages[-1]["content"])
        self.assertNotIn("another plan", str(first.messages))
        self.assertNotIn("failed", str(second.messages))

    def test_published_call_uses_chat_shapes_and_identifies_recorded_source(self):
        backend = MagicMock()
        client = backend.get_client.return_value
        client.create_call.return_value = SimpleNamespace(id="chat-call")
        messages = [
            {"role": "user", "content": "prompt"},
            {"role": "assistant", "content": "plan"},
        ]
        with patch.object(telemetry, "backend", return_value=backend):
            self.assertEqual(
                telemetry.publish_plan_chat(
                    messages, "Execution finished", "refrigerate_the_salmon"
                ),
                "chat-call",
            )
        self.assertEqual(
            client.create_call.call_args.kwargs["inputs"], {"messages": messages}
        )
        self.assertEqual(
            client.create_call.call_args.kwargs["display_name"],
            "refrigerate_the_salmon",
        )
        self.assertEqual(
            client.create_call.call_args.kwargs["attributes"],
            {"source": "recorded_plan_execution"},
        )
        output = client.finish_call.call_args.kwargs["output"]
        self.assertEqual(
            output["choices"][0]["message"],
            {"role": "assistant", "content": "Execution finished"},
        )
        self.assertNotIn("usage", output)

    def test_code_block_preserves_embedded_fences_and_indentation(self):
        snippet = 'def task():\n    value = "```"\n    return value'
        self.assertEqual(code_block(snippet, "python"), f"````python\n{snippet}\n````")

    def test_native_angle_brackets_do_not_disable_weave_markdown(self):
        from methods.chat_transcript import record_request

        transcript = PlanChatTranscript()
        instruction = "<char0> [walk] <bathroom> (11)"
        with patch.object(telemetry, "backend", return_value=None), capture_transcript(
            transcript
        ):
            record_request("<rules>Use actions</rules>", "plan")
            with telemetry.span(
                "simulator_action", {"script_instruction": instruction}
            ) as output:
                output.update(success=True)
        prompt, request, result = [
            message["content"] for message in transcript.messages
        ]
        self.assertIn("&lt;rules&gt;", prompt)
        self.assertIn("&lt;char0&gt;", request)
        self.assertNotIn("<char0>", result)
        body = result.split("```json\n", 1)[1].rsplit("\n```", 1)[0]
        self.assertEqual(json.loads(body)["script_instruction"], instruction)

    def test_prompt_fences_do_not_display_escaped_entities_as_source_code(self):
        from methods.chat_transcript import format_prompt

        prompt = "<rules>\n```\nassert(<condition>)\n    else: <action>\n```\n```python\nx = a & b\n```"
        formatted = format_prompt(prompt)
        self.assertIn("> assert(&lt;condition&gt;)", formatted)
        self.assertIn("> &nbsp;&nbsp;&nbsp;&nbsp;else:", formatted)
        self.assertIn("```python\nx = a & b\n```", formatted)

    def test_prompt_function_header_and_body_share_a_python_block(self):
        from methods.chat_transcript import format_prompt

        example = (
            "def refrigerate_the_salmon():\n\t# Find the salmon.\n\tfind('salmon')"
        )
        prompt = f"Example:\n\n{example}\n\n<task>\ndef wash_clothes():"
        formatted = format_prompt(prompt)
        self.assertIn(code_block(example, "python"), formatted)
        self.assertIn(code_block("def wash_clothes():", "python"), formatted)
        self.assertIn("&lt;task&gt;", formatted)
        self.assertEqual(
            format_prompt(code_block(example, "python")), code_block(example, "python")
        )
        transcript = PlanChatTranscript()
        provider = MagicMock()
        provider.settings = {"plan": {}}
        provider.generate.return_value = "def wash_clothes():\n    pass"
        with patch.object(telemetry, "backend", return_value=None), patch.object(
            llm, "get_provider", return_value=provider
        ), capture_transcript(transcript):
            llm.generate(prompt, "plan")
        self.assertEqual(provider.generate.call_args.args[0], prompt)
        self.assertIn(code_block(example, "python"), transcript.messages[0]["content"])
