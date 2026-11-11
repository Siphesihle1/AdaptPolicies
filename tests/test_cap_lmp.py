import json
import unittest
from methods.cap.prompt import build_prompt
from methods.cap.lmp import Session
from methods.cap.runtime import Limits
from virtual_home.virtualhome_types import ObjectRef
from cap_fakes import FakeProvider


class LMPTests(unittest.TestCase):
    def test_prompt_groups_duplicate_objects_without_serializing_references(self):
        objects = [ObjectRef("active-episode", index, "mug") for index in range(200)]
        context = {"episode_id": "active-episode", "observation_revision": 12,
                   "visible_objects": objects}
        prompt = build_prompt("active-episode", "cap_question", "How many mugs?", context)
        summary = json.JSONDecoder().raw_decode(prompt.split("Permitted observation:\n")[1])[0]
        self.assertEqual(summary, {"episode_id": "active-episode", "observation_revision": 12,
                                  "visible_object_counts": {"mug": 200}})
        self.assertNotIn('"id":', prompt)
        self.assertNotIn('"visible_objects":', prompt)
        self.assertIn("Output raw Python only", prompt)
        self.assertEqual(context["visible_objects"], objects)

    def test_compact_context_keeps_runtime_references_and_duplicate_selection(self):
        objects = [ObjectRef("episode", 20, "mug"), ObjectRef("episode", 21, "mug")]
        session = self.session({"cap_objects": "ret_val = [obj for obj in get_visible_objects() if obj.id == 21]"},
                               bindings={"get_visible_objects": lambda: objects})
        session.context = {"episode_id": "episode", "observation_revision": 7,
                           "visible_objects": objects}
        session.context_query = lambda: session.context
        self.assertEqual(session.parse_objects("second mug"), [objects[1]])

    def test_output_contract_follows_the_task_and_matches_program_role(self):
        policy = build_prompt("episode", "cap_policy", "Open a fridge")
        self.assertGreater(policy.index("Start with the exact line def policy():"),
                           policy.index("Request:\nOpen a fridge"))
        question = build_prompt("episode", "cap_question", "Is it open?")
        self.assertIn("assigning the computed answer to ret_val", question.split("Request:\n")[1])

    def session(self, responses, bindings=None, limits=None):
        self.events = []
        self.ref = ObjectRef("episode", 20, "mug")
        self.context = {"episode_id": "episode", "observation_revision": 7, "visible_objects": [self.ref]}
        return Session("episode", bindings or {"get_visible_objects": lambda: [self.ref]}, self.context,
                       limits or Limits(), FakeProvider(responses), lambda kind, value: self.events.append((kind, value)))

    def test_specialized_nested_call_executes_computed_answer(self):
        session = self.session({"cap_policy": '''def policy():
    objects = get_visible_objects()
    if objects:
        return parse_question("how many mugs?")''', "cap_question": "ret_val = len(get_visible_objects())"})
        self.assertEqual(session.policy("count"), 1)
        requests = [v for k, v in self.events if k == "generation_request"]
        self.assertEqual([r["purpose"] for r in requests], ["cap_policy", "cap_question"])
        for request in requests:
            self.assertTrue(request["prompt"].startswith("Active episode_id: episode"))
            self.assertIn('"observation_revision": 7', request["prompt"])

    def test_missing_return_and_invalid_objects_explicit(self):
        for source, error in [("x = 1", "missing_return"), ("ret_val = ['mug']", "invalid_object")]:
            session = self.session({"cap_objects": source})
            with self.assertRaisesRegex(ValueError, error):
                session.parse_objects("mugs")

    def test_queries_do_not_generate_or_mutate_model_input(self):
        session = self.session({"cap_policy": "def policy():\n    return len(get_visible_objects())"})
        self.assertEqual(session.policy("count"), 1)
        self.assertEqual(session.budget.counts["model_requests"], 1)

    def test_session_helpers_do_not_cross_episodes(self):
        first = self.session({"cap_function": "def foo():\n    return 3"})
        self.assertEqual(first.execute("ret_val = foo()", "ret_val"), 3)
        second = self.session({})
        self.assertEqual(second.functions.sources, {})

    def test_request_and_output_limits(self):
        session = self.session({"cap_question": "ret_val = 'too long'"}, limits=Limits(max_output_bytes=2))
        with self.assertRaisesRegex(ValueError, "output_size_limit"):
            session.parse_question("answer")
        session = self.session({"cap_question": "ret_val = parse_question('again')"}, limits=Limits(max_model_requests=2))
        with self.assertRaisesRegex(RuntimeError, "model_requests_limit"):
            session.parse_question("again")
