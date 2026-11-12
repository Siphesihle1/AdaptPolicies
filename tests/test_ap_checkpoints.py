"""Checkpoints, implicit action checkpoints and exception checkpoints in the AP runtime."""

import unittest

import test_cap_runtime as runtime_tests
from ap_fakes import FlakyEnvironment, SequenceProvider
from methods.adaptive.agent import AdaptivePolicyRuntime
from methods.adaptive.environment import AdaptiveEnvironment
from methods.adaptive.session import AdaptiveSession
from methods.adaptive.settings import AdaptiveLimits
from virtual_home.task import VHTask

FRIDGE = "fridge = [o for o in get_visible_objects() if o.name == 'fridge'][0]"
FRIDGE_OPEN = "lambda: 'OPEN' in (get_object_states(fridge) or ())"


class APRuntimeCase(unittest.TestCase):
    setUp = runtime_tests.RuntimeTests.setUp

    def run_ap(self, responses, placement="both", environment=None, **limits):
        task = VHTask("test", "offline", ["test"], 100)
        env = (environment or FlakyEnvironment)(task=task)
        self.env = env
        env.stop_after_unity_rejection = False
        runtime = AdaptivePolicyRuntime(AdaptiveEnvironment(env, task),
                                        AdaptiveLimits(task_seconds=limits.pop("task_seconds", 30),
                                                       placement=placement, **limits),
                                        SequenceProvider(responses))
        outcome = runtime.run("test")
        self.events = runtime.events
        return outcome

    def kinds(self, kind):
        return [e for e in self.events if e["kind"] == kind]

    def requests(self, purpose=None):
        return [e for e in self.kinds("generation_request") if purpose is None or e["purpose"] == purpose]


class CheckpointTests(APRuntimeCase):
    def test_passing_checkpoint_makes_no_model_call(self):
        outcome = self.run_ap({"ap_policy": f"""def policy():
    {FRIDGE}
    open(fridge)
    return checkpoint('the fridge is open', {FRIDGE_OPEN})"""})
        self.assertEqual(outcome["status"], "executed", outcome)
        self.assertIs(outcome["result"], True)
        self.assertEqual(len(self.requests()), 1)
        self.assertEqual(len(self.kinds("checkpoint_passed")), 1)
        self.assertFalse(self.kinds("checkpoint_failed"))

    def test_failing_checkpoint_recovers_and_continues_after_it(self):
        outcome = self.run_ap({
            "ap_policy": f"""def policy():
    {FRIDGE}
    checkpoint('the fridge is open', {FRIDGE_OPEN})
    return 'continued'""",
            "ap_recover": "def recover():\n    open(fridge)"})
        self.assertEqual(outcome["status"], "executed", outcome)
        self.assertEqual(outcome["result"], "continued")
        self.assertEqual([r["purpose"] for r in self.requests()], ["ap_policy", "ap_recover"])
        failure = self.kinds("checkpoint_failed")[0]
        self.assertEqual(failure["trigger"], "checkpoint")
        self.assertEqual(failure["description"], "the fridge is open")
        self.assertEqual(failure["bindings"], {"fridge": "fridge"})
        self.assertEqual(self.kinds("recovery_result")[0]["succeeded"], True)
        prompt = self.requests("ap_recover")[0]["prompt"]
        for section in ("<program>", "<failure>", "<progress>", "<bindings>", "<observation>"):
            self.assertIn(section, prompt)
        self.assertIn("checkpoint(&apos;the fridge is open&apos;".replace("&apos;", "'"), prompt)
        self.assertIn("# &lt;- failed here", prompt)
        self.assertIn("fridge = fridge", prompt)
        self.assertLess(prompt.index("<task>") if "<task>" in prompt else prompt.index("<request>"),
                        prompt.index("<failure>"))

    def test_checkpoint_returns_the_check_value_found_by_recovery(self):
        outcome = self.run_ap({
            "ap_policy": """def policy():
    apples = checkpoint('an apple is visible',
                        lambda: [o for o in get_visible_objects() if o.name == 'apple'])
    return apples[0].name""",
            "ap_recover": "def recover():\n    open('fridge')"})
        self.assertEqual(outcome["result"], "apple", outcome)

    def test_check_is_evaluated_again_and_failed_recovery_escalates_to_replan(self):
        outcome = self.run_ap({
            "ap_policy": f"""def policy():
    {FRIDGE}
    checkpoint('the fridge is open', {FRIDGE_OPEN})
    return 'old'""",
            "ap_recover": "def recover():\n    walk(fridge)",
            "ap_replan": "def policy():\n    open('fridge')\n    return 'replanned'"})
        self.assertEqual(outcome["result"], "replanned", outcome)
        local = [r for r in self.kinds("recovery_result") if r["scope"] == "local"]
        self.assertEqual([r["succeeded"] for r in local], [False, False])
        self.assertEqual(len(self.kinds("replan")), 1)
        replan_prompt = self.requests("ap_replan")[0]["prompt"]
        self.assertIn("<progress>", replan_prompt)
        self.assertIn("local recovery for checkpoint 'the fridge is open': failed", replan_prompt)

    def test_checkpoint_api_is_absent_in_the_implicit_condition(self):
        outcome = self.run_ap({"ap_policy": "def policy():\n    return checkpoint('x', lambda: True)",
                               "ap_replan": "def policy():\n    return 'replanned'"}, placement="implicit")
        self.assertEqual(outcome["result"], "replanned", outcome)
        self.assertIn("NameError", self.kinds("checkpoint_failed")[0]["exception"])

    def test_recovery_code_may_not_call_checkpoint_or_reassign_bindings(self):
        outcome = self.run_ap({
            "ap_policy": f"""def policy():
    {FRIDGE}
    checkpoint('the fridge is open', {FRIDGE_OPEN})
    return 'continued'""",
            "ap_recover": ["def recover():\n    checkpoint('x', lambda: True)",
                           "def recover():\n    fridge = 1"],
            "ap_replan": "def policy():\n    return 'replanned'"})
        errors = [r["error"] for r in self.kinds("recovery_result")]
        self.assertIn("recover must not call checkpoint", errors[0])
        self.assertIn("Reserved name: fridge", errors[1])
        self.assertEqual(outcome["result"], "replanned")

    def test_bare_except_is_rejected(self):
        outcome = self.run_ap({"ap_policy": "def policy():\n    try:\n        pass\n    except:\n        pass"})
        self.assertEqual(outcome["status"], "execution_failed")
        self.assertIn("Bare except", outcome["error"])


class ImplicitActionTests(APRuntimeCase):
    def test_failed_action_whose_effect_holds_is_not_retried(self):
        FlakyEnvironment.failures = {"open": 1}
        self.addCleanup(setattr, FlakyEnvironment, "failures", {})
        outcome = self.run_ap({
            "ap_policy": "def policy():\n    result = open('fridge')\n    return [result.status, result.recovered]",
            "ap_recover": "def recover():\n    return True"})
        self.assertEqual(outcome["result"], ["succeeded", True], outcome)
        self.assertEqual(sum("[open]" in call for call in self.env.calls), 1)
        failure = self.kinds("checkpoint_failed")[0]
        self.assertEqual((failure["trigger"], failure["action"]), ("action", "open"))
        self.assertEqual(failure["message"], "open is not possible yet")

    def test_failed_action_is_retried_after_recovery(self):
        FlakyEnvironment.failures = {"open": 1}
        self.addCleanup(setattr, FlakyEnvironment, "failures", {})
        outcome = self.run_ap({
            "ap_policy": "def policy():\n    return open('fridge').status",
            "ap_recover": "def recover():\n    walk('fridge')"})
        self.assertEqual(outcome["result"], "succeeded", outcome)
        self.assertEqual(sum("[open]" in call for call in self.env.calls), 2)

    def test_explicit_condition_returns_failed_actions_to_the_policy(self):
        outcome = self.run_ap({"ap_policy": "def policy():\n    result = touch('mug')\n    return [result.status, result.message]"},
                              placement="explicit")
        self.assertEqual(outcome["result"], ["failed", "touch could not be executed"], outcome)
        self.assertFalse(self.kinds("checkpoint_failed"))

    def test_actions_inside_recovery_are_not_recovered_again(self):
        outcome = self.run_ap({
            "ap_policy": "def policy():\n    return touch('mug').status",
            "ap_recover": "def recover():\n    touch('mug')",
            "ap_replan": "def policy():\n    return 'replanned'"})
        self.assertEqual(outcome["result"], "replanned", outcome)
        self.assertEqual(len(self.kinds("checkpoint_failed")), 1)


class ExceptionTests(APRuntimeCase):
    def test_exception_in_a_helper_is_recovered_and_its_value_used(self):
        outcome = self.run_ap({
            "ap_policy": "def policy():\n    return first_apple()",
            "ap_function": "def first_apple():\n    return [o for o in get_visible_objects() if o.name == 'apple'][0].name",
            "ap_recover": "def recover():\n    return 'recovered value'"})
        self.assertEqual(outcome["result"], "recovered value", outcome)
        failure = self.kinds("checkpoint_failed")[0]
        self.assertEqual(failure["trigger"], "exception")
        self.assertIn("IndexError", failure["exception"])
        self.assertEqual(failure["frames"][0]["helper"], "first_apple")

    def test_exception_in_policy_goes_straight_to_a_replan(self):
        outcome = self.run_ap({
            "ap_policy": "def policy():\n    return [o for o in get_visible_objects() if o.name == 'apple'][0]",
            "ap_replan": "def policy():\n    open('fridge')\n    return 'replanned'"})
        self.assertEqual(outcome["result"], "replanned", outcome)
        self.assertFalse(self.requests("ap_recover"))
        self.assertIn("IndexError", self.requests("ap_replan")[0]["prompt"])

    def test_budget_and_deadline_errors_are_not_recovered(self):
        outcome = self.run_ap({"ap_policy": "def policy():\n    while True:\n        get_visible_objects()"},
                              max_queries=5)
        self.assertEqual(outcome["status"], "execution_failed")
        self.assertIn("queries_limit", outcome["error"])
        self.assertFalse(self.kinds("checkpoint_failed"))

    def test_invalid_initial_policy_is_scored_like_cap(self):
        outcome = self.run_ap({"ap_policy": "def policy(:\n    pass"})
        self.assertEqual(outcome["status"], "execution_failed")
        self.assertFalse(self.kinds("checkpoint_failed"))


class SessionTests(unittest.TestCase):
    def session(self, placement="both"):
        return AdaptiveSession("episode", {"walk": lambda *a: None, "get_visible_objects": lambda: []},
                               {"episode_id": "episode", "observation_revision": 0, "visible_objects": []},
                               AdaptiveLimits(placement=placement))

    def test_checkpoint_is_reserved_in_every_condition(self):
        for placement in ("both", "explicit", "implicit"):
            session = self.session(placement)
            self.assertIn("checkpoint", session.reserved)
            self.assertEqual("checkpoint" in session.namespace, placement != "implicit")
            with self.assertRaises(ValueError):
                session.validate("def checkpoint():\n    pass")

    def test_ap_result_attributes_are_readable(self):
        self.session().validate("def policy():\n    r = walk('x')\n    return r.message, r.recovered")


class MessageTests(unittest.TestCase):
    def test_unity_rejections_are_reduced_to_their_messages(self):
        from methods.adaptive.environment import readable
        raw = ("Unity rejected action: (False, {'0': {'message': 'ScriptExcutor 0: PROCESS WALK: Can not select "
               "object: clothespile. REASON: No interaction positions\\nEXECUTION_GENERAL: Script is impossible to "
               "execute\\n\\n'}})")
        self.assertEqual(readable(raw), "Unity rejected the action: PROCESS WALK: Can not select object: "
                                        "clothespile. REASON: No interaction positions; Script is impossible to execute")
        self.assertEqual(readable("<fridge> (305) is not open"), "<fridge> (305) is not open")
        self.assertEqual(readable("Unity rejected action: not a repr"), "Unity rejected action: not a repr")


if __name__ == "__main__":
    unittest.main()
