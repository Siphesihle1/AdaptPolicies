import unittest
from methods.cap.lmp import Session
from methods.cap.runtime import Limits
from virtual_home.virtualhome_types import ObjectRef
from cap_fakes import FakeProvider


class LMPTests(unittest.TestCase):
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
