"""The recovery ladder: helper regeneration, escalation, no-progress termination and artifacts."""

import copy
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from ap_fakes import FlakyEnvironment, SequenceProvider
from cap_fakes import FakeEnvironment
from methods.adaptive.agent import AdaptiveAgent
from methods.adaptive.settings import AdaptiveLimits
from test_ap_checkpoints import APRuntimeCase

FAIL_CHECK = "checkpoint('the fridge is open', lambda: 'OPEN' in (get_object_states(fridge) or ()))"


class LadderTests(APRuntimeCase):
    def test_helper_is_regenerated_and_called_again_with_the_same_arguments(self):
        outcome = self.run_ap({
            "ap_policy": "def policy():\n    fridge = [o for o in get_visible_objects() if o.name == 'fridge'][0]\n"
                         "    return use_fridge(fridge, 'kept')",
            "ap_function": {
                "Implement helper use_fridge": f"def use_fridge(fridge, label):\n    {FAIL_CHECK}\n    return label",
                "Rewrite helper use_fridge": "def use_fridge(fridge, label):\n    open(fridge)\n"
                                             f"    {FAIL_CHECK}\n    return label + ' after regeneration'",
            },
            "ap_recover": "def recover():\n    walk(fridge)"})
        self.assertEqual(outcome["result"], "kept after regeneration", outcome)
        scopes = [(r["scope"], r["succeeded"]) for r in self.kinds("recovery_result")]
        self.assertEqual(scopes, [("local", False), ("local", False), ("helper", True)])
        regenerated = self.kinds("helper_regenerated")[0]
        self.assertEqual(regenerated["name"], "use_fridge")
        prompt = next(r["prompt"] for r in self.requests("ap_function") if "<failure>" in r["prompt"])
        self.assertIn("Rewrite the failing helper", prompt)
        self.assertNotIn("<bindings>", prompt)

    def test_escalation_moves_up_the_generated_call_stack(self):
        outcome = self.run_ap({
            "ap_policy": "def policy():\n    return outer()",
            "ap_function": {
                "Implement helper outer": "def outer():\n    return inner()",
                "Implement helper inner": f"def inner():\n    fridge = [o for o in get_visible_objects() if o.name == 'fridge'][0]\n    {FAIL_CHECK}\n    return 'inner'",
                "Rewrite helper inner": f"def inner():\n    fridge = [o for o in get_visible_objects() if o.name == 'fridge'][0]\n    {FAIL_CHECK}\n    return 'inner again'",
                "Rewrite helper outer": "def outer():\n    open('fridge')\n    return 'outer fixed'",
            },
            "ap_recover": "def recover():\n    walk(fridge)"}, max_recoveries_per_checkpoint=1)
        self.assertEqual(outcome["result"], "outer fixed", outcome)
        regenerated = [e["name"] for e in self.kinds("helper_regenerated")]
        self.assertEqual(regenerated, ["inner", "outer"])
        self.assertFalse(self.kinds("replan"))

    def test_a_failure_that_recurs_after_a_replan_without_progress_ends_the_episode(self):
        policy = f"def policy():\n    fridge = [o for o in get_visible_objects() if o.name == 'fridge'][0]\n    {FAIL_CHECK}"
        outcome = self.run_ap({"ap_policy": policy, "ap_recover": "def recover():\n    pass",
                               "ap_replan": policy})
        self.assertEqual(outcome["status"], "execution_failed")
        self.assertIn("NoProgress", outcome["error"])
        self.assertEqual(len(self.kinds("replan")), 1)
        self.assertEqual(len(self.kinds("terminated_no_progress")), 1)

    def test_progress_between_failures_allows_another_replan(self):
        FlakyEnvironment.failures = {}
        policy = ("def policy():\n    walk('kitchen')\n"
                  "    fridge = [o for o in get_visible_objects() if o.name == 'fridge'][0]\n"
                  f"    {FAIL_CHECK}\n    return 'done'")
        outcome = self.run_ap({"ap_policy": policy, "ap_recover": "def recover():\n    pass",
                               "ap_replan": [policy, "def policy():\n    open('fridge')\n    return 'opened'"]})
        self.assertEqual(outcome["result"], "opened", outcome)
        self.assertEqual(len(self.kinds("replan")), 2)

    def test_recovery_requests_count_against_the_model_budget(self):
        policy = "def policy():\n    walk('kitchen')\n    return touch('mug')"
        outcome = self.run_ap({"ap_policy": policy, "ap_recover": "def recover():\n    walk('kitchen')",
                               "ap_replan": policy}, max_model_requests=6)
        self.assertEqual(outcome["status"], "execution_failed")
        self.assertIn("model_requests_limit", outcome["error"])


class AgentTests(unittest.TestCase):
    setUp = APRuntimeCase.setUp

    def run_agent(self, responses, tasks=("open fridge",), factory=FakeEnvironment, placement="both"):
        initial = FakeEnvironment().graph
        final = copy.deepcopy(initial)
        final["nodes"][3]["states"] = ["OPEN"]
        graphs = {"_".join(t.split()): final for t in tasks}
        output = Path(self.directory.name) / "run"
        with patch.dict(os.environ, {"JOB_OUTPUT_DIR": str(output), "EXPERIMENT_NAME": "offline-ap"}), \
             patch("methods.adaptive.agent.load_tasks", return_value=list(tasks)), \
             patch("methods.adaptive.agent.load_ground_truth_graphs", return_value=graphs):
            agent = AdaptiveAgent(0, "test_seen", generator=SequenceProvider(responses), environment_factory=factory,
                                  limits=AdaptiveLimits(task_seconds=30, placement=placement))
            agent.execute_tasks()
        return agent, output

    def test_episode_artifacts_record_checkpoints_recoveries_and_policy_versions(self):
        agent, output = self.run_agent({
            "ap_policy": "def policy():\n    fridge = [o for o in get_visible_objects() if o.name == 'fridge'][0]\n"
                         f"    {FAIL_CHECK}\n    return 'old'",
            "ap_recover": "def recover():\n    pass",
            "ap_replan": "def policy():\n    open('fridge')\n    "
                         "checkpoint('the fridge is open', lambda: [o for o in get_visible_objects() if 'OPEN' in (get_object_states(o) or ())])"})
        directory = output / "tasks" / "open_fridge"
        record = agent.task_record("open_fridge")
        self.assertEqual(record["status"], "evaluated")
        self.assertEqual(record["method"], "adaptive")
        self.assertEqual(record["termination"], "returned")
        self.assertEqual(record["replans"], 1)
        self.assertEqual(record["failures_by_trigger"], {"checkpoint": 1})
        self.assertEqual(record["recoveries_by_scope"]["local"], {"attempted": 2, "succeeded": 0})
        self.assertEqual(record["checkpoints_passed"], 1)
        self.assertEqual(record["checkpoints_placed"], 2)
        self.assertEqual(record["checkpoints_reached"], 2)
        self.assertEqual(record["model_calls_by_purpose"], {"ap_policy": 1, "ap_recover": 2, "ap_replan": 1})
        self.assertEqual(record["placement"], "both")
        self.assertEqual(agent.results["open_fridge"]["SR"], 1)
        self.assertEqual(record["without_recovery"], {"PSR": 0, "SR": 0})
        self.assertEqual(record["without_exception_recovery"], {"PSR": 1, "SR": 1})
        self.assertTrue((directory / "first_failure_state.json").is_file())
        self.assertFalse((directory / "first_exception_state.json").exists())
        self.assertTrue((directory / "policy.replan-1.py").is_file())
        self.assertIn("return 'old'", (directory / "policy.py").read_text())
        recoveries = json.loads((directory / "recoveries.json").read_text())
        self.assertEqual([e["kind"] for e in recoveries][:2], ["checkpoint_failed", "recovery_generated"])
        configuration = json.loads((output / "configuration.json").read_text())
        self.assertEqual(configuration["resolved_adaptive"]["placement"], "both")
        self.assertEqual(configuration["resolved_adaptive"]["max_model_requests"], 64)
        results = json.loads((output / "results.json").read_text())
        self.assertEqual(results["method"], "adaptive")
        chat = (directory / "chat.json").read_text()
        self.assertIn("AP recovery", chat)
        self.assertIn("AP observation", chat)

    def test_agent_keeps_running_after_a_unity_rejection(self):
        class RejectingOnce(FakeEnvironment):
            rejected = False

            def execute(self, script):
                if "[open]" in script and not self.rejected:
                    self.rejected = True
                    if self.stop_after_unity_rejection:
                        self.execution_failed = True
                    self.last_action_error = "Unity rejected action: (False, {})"
                    return False
                return super().execute(script)
        agent, output = self.run_agent({"ap_policy": "def policy():\n    return open('fridge').status",
                                        "ap_recover": "def recover():\n    walk('fridge')"},
                                       factory=RejectingOnce)
        execution = json.loads((output / "tasks" / "open_fridge" / "execution.json").read_text())
        self.assertEqual(execution["result"], "succeeded", execution)
        self.assertEqual(agent.results["open_fridge"]["SR"], 1)
        failure = json.loads((output / "tasks" / "open_fridge" / "recoveries.json").read_text())[0]
        self.assertIn("Unity rejected the action", failure["message"])

    def test_exception_counterfactual_scores_the_state_before_replanning(self):
        agent, output = self.run_agent({
            "ap_policy": "def policy():\n    return [][0]",
            "ap_replan": "def policy():\n    open('fridge')"})
        record = agent.task_record("open_fridge")
        self.assertEqual(agent.results["open_fridge"]["SR"], 1)
        self.assertEqual(record["without_recovery"], {"PSR": 0, "SR": 0})
        self.assertEqual(record["without_exception_recovery"], {"PSR": 0, "SR": 0})
        self.assertTrue((output / "tasks" / "open_fridge" / "first_exception_state.json").is_file())


class FailureStateTests(unittest.TestCase):
    def test_reused_output_drops_previous_episode_failure_snapshots(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from types import SimpleNamespace
        from methods.adaptive.agent import AdaptiveAgent
        with TemporaryDirectory() as temporary:
            directory = Path(temporary)
            for name in ("first_failure", "first_exception"):
                (directory / f"{name}_state.json").write_text('{}')
            agent = AdaptiveAgent.__new__(AdaptiveAgent)
            agent.num_tasks_parsed = 0
            agent.save_execution(directory, SimpleNamespace(events=[], failure_states={}),
                                 {"status": "executed"}, {})
            self.assertFalse((directory / "first_failure_state.json").exists())
            self.assertFalse((directory / "first_exception_state.json").exists())

    def test_snapshots_are_independent_and_include_only_derived_physical_effects(self):
        from types import SimpleNamespace
        from methods.adaptive.agent import AdaptivePolicyRuntime
        env = SimpleNamespace(native_state_uncertain=False,
                              graph={"nodes": [{"id": 2, "states": []}], "edges": []},
                              nodes_with_additonal_states={2: {"states": ["WASHED", "CLOSED"]}})
        runtime = AdaptivePolicyRuntime.__new__(AdaptivePolicyRuntime)
        runtime.adapter = SimpleNamespace(env=env)
        runtime.failure_states = {}
        runtime.on_event({"kind": "checkpoint_failed", "trigger": "action"})
        self.assertEqual(env.graph["nodes"][0]["states"], [])
        env.graph["nodes"][0]["states"].append("OPEN")
        runtime.on_event({"kind": "checkpoint_failed", "trigger": "exception"})
        self.assertEqual(runtime.failure_states["first_failure"]["nodes"][0]["states"], ["WASHED"])
        self.assertEqual(runtime.failure_states["first_exception"]["nodes"][0]["states"], ["OPEN", "WASHED"])


if __name__ == "__main__":
    unittest.main()
