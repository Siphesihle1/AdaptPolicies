import unittest
from methods.cap.function_gen import unresolved_calls
from methods.cap.lmp import Session
from methods.cap.runtime import Limits
from cap_fakes import FakeProvider


class FunctionGenerationTests(unittest.TestCase):
    def session(self, responses, limits=None):
        return Session("episode", {}, {"episode_id": "episode", "observation_revision": 0},
                       limits or Limits(), FakeProvider({"cap_function": responses}))

    def test_dependency_order_and_python_control_flow(self):
        session = self.session({"helper_a(": "def helper_a(x):\n    return helper_b(x) + 1",
                                "helper_b(": "def helper_b(x):\n    return x * 2"})
        source = '''def policy():
    total = 0
    def local(x):
        return x + 1
    for value in range(3):
        if value != 1:
            total += helper_a(local(value))
    return total'''
        self.assertEqual(session.execute(source, policy=True), 10)
        self.assertEqual(list(session.functions.sources), ["helper_b", "helper_a"])
        self.assertEqual(session.functions.dependencies["helper_a"], ["helper_b"])

    def test_lexical_parameters_nested_bindings_and_attributes(self):
        source = '''def outer(callback):
    alias = callback
    def inner():
        return alias(1)
    return inner()
items = [1]
items.append(2)
ret_val = outer(len)'''
        self.assertEqual(unresolved_calls(source, {"len"}), [])

    def test_cycle_signature_depth_and_helper_budget(self):
        cases = [
            ({"helper_a(": "def helper_a():\n    return helper_a()"}, Limits(), "cycle"),
            ({"helper_a(": "def helper_a(x):\n    return x"}, Limits(), "missing a required"),
            ({"helper_a(": "def helper_a():\n    return helper_b()"}, Limits(max_depth=1), "depth_limit"),
            ({"helper_a(": "def helper_a():\n    return helper_b()"}, Limits(max_helpers=1), "count_limit"),
        ]
        for responses, limits, error in cases:
            with self.subTest(error=error), self.assertRaisesRegex((ValueError, RuntimeError, TypeError), error):
                self.session(responses, limits).execute("ret_val = helper_a()", "ret_val")

    def test_invalid_helper_not_repaired(self):
        session = self.session("not python at all!")
        with self.assertRaises(SyntaxError):
            session.execute("ret_val = foo()", "ret_val")
        self.assertEqual(session.budget.counts["model_requests"], 1)
