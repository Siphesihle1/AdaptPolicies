import ast
import copy
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

import test_cap_runtime as runtime_tests
from cap_fakes import FakeEnvironment, FakeProvider
from methods.cap.agent import CaPAgent
from methods.cap.runtime import Limits
from methods.cap.prompt import load_examples, select_examples
from methods.shared.evaluation import EvaluationMixin


class ExecutionTests(unittest.TestCase):
    setUp = runtime_tests.RuntimeTests.setUp

    def test_few_shot_helper_bodies_compose_with_specialized_lmps(self):
        text = "\n\n".join(row["code"] for row in load_examples("cap_function"))
        tree = ast.parse(text)
        helpers = {node.name + "(": ast.unparse(node) for node in tree.body}
        examples = select_examples("default", 3)
        self.assertIn("place_held_in_container(", examples)
        self.assertIn("parse_question(", examples)
        self.assertNotIn("def acquire_object", examples)
        agent, output = self.agent({
            "cap_policy": '''def policy():
    mugs = parse_objects('visible mugs')
    fridges = parse_objects('visible fridge')
    if acquire_object(mugs[0]):
        return load_washing_machine(mugs[0], fridges[0])''',
            "cap_objects": {
                "visible mugs": "ret_val = [o for o in get_visible_objects() if o.name == 'mug']",
                "visible fridge": "ret_val = [o for o in get_visible_objects() if o.name == 'fridge']",
            },
            "cap_function": helpers,
        }, tasks=("store mug",))
        execution = json.loads((output / "tasks/store_mug/execution.json").read_text())
        self.assertEqual(execution["status"], "executed", execution)
        self.assertIs(execution["result"], True)
        dependencies = json.loads((output / "tasks/store_mug/dependencies.json").read_text())
        self.assertTrue(any(edge["caller"] == "load_washing_machine" and
                            edge["dependency"] == "place_held_in_container" for edge in dependencies["edges"]))
        self.assertTrue(any(edge["caller"] == "place_held_in_container" and
                            edge["dependency"] == "ensure_open" for edge in dependencies["edges"]))

    def agent(self, responses, tasks=("open fridge", "bad program"), factory=FakeEnvironment):
        initial = FakeEnvironment().graph
        final = copy.deepcopy(initial)
        final["nodes"][3]["states"] = ["OPEN"]
        graphs = {"_".join(t.split()): final for t in tasks}
        output = Path(self.directory.name) / "run"
        with patch.dict(os.environ, {"JOB_OUTPUT_DIR": str(output), "EXPERIMENT_NAME": "offline-cap"}), \
             patch("methods.cap.agent.load_tasks", return_value=list(tasks)), \
             patch("methods.cap.agent.load_ground_truth_graphs", return_value=graphs):
            agent = CaPAgent(0, "test_seen", generator=FakeProvider(responses), environment_factory=factory,
                             limits=Limits(task_seconds=30))
            agent.execute_tasks()
        return agent, output

    def test_full_task_scoring_failures_and_artifacts(self):
        agent, output = self.agent({"cap_policy": {
            "open fridge": "def policy():\n    return open('fridge').status",
            "bad program": "def policy():\n    return invalid syntax!"}})
        results = json.loads((output / "results.json").read_text())
        self.assertEqual(results["summary"]["num_tasks"], 2)
        self.assertEqual(results["summary"]["SR"], .5)
        self.assertEqual(results["tasks"]["open_fridge"]["metrics"]["SR"], 1)
        self.assertEqual(results["tasks"]["bad_program"]["metrics"]["SR"], 0)
        self.assertEqual(results["tasks"]["bad_program"]["status"], "execution_failed")
        for name in ("policy.py", "helpers.py", "dependencies.json", "generation.json", "execution.json",
                     "initial_state.json", "final_state.json", "chat.json"):
            self.assertTrue((output / "tasks" / "open_fridge" / name).is_file(), name)
        generation = json.loads((output / "tasks" / "open_fridge" / "generation.json").read_text())
        self.assertTrue(generation[0]["prompt"].startswith("<instructions>"))
        self.assertNotIn("episode_id", generation[0]["prompt"])
        chat = (output / "tasks" / "open_fridge" / "chat.json").read_text()
        self.assertIn("CaP policy", chat)
        self.assertIn("CaP observation", chat)
        # Shared implementation is the very same scorer used by ProgPrompt.
        from methods.progprompt.agent import ProgPromptAgent
        self.assertIs(ProgPromptAgent.eval, EvaluationMixin.eval)

    def test_zero_action_policy_is_execution_not_goal_success(self):
        agent, output = self.agent({"cap_policy": "def policy():\n    pass"}, tasks=("open fridge",))
        self.assertEqual(agent.results["open_fridge"]["Exec"], 0)
        self.assertEqual(agent.results["open_fridge"]["SR"], 0)
        self.assertEqual(agent.num_tasks_executed, 1)
        self.assertTrue(agent.task_record("open_fridge")["dependency_resolution_succeeded"])

    def test_nested_helpers_and_specialized_program_in_worker(self):
        agent, output = self.agent({
            "cap_policy": "def policy():\n    objects = parse_objects('visible mugs')\n    return count_mugs(objects)",
            "cap_objects": "ret_val = [o for o in get_visible_objects() if o.name == 'mug']",
            "cap_function": "def count_mugs(objects):\n    return len(objects)",
        }, tasks=("count mugs",))
        execution = json.loads((output / "tasks" / "count_mugs" / "execution.json").read_text())
        self.assertEqual(execution["result"], 2)
        self.assertEqual(execution["generation_counts"]["model_requests"], 3)
        generations = json.loads((output / "tasks" / "count_mugs" / "generation.json").read_text())
        requests = [row for row in generations if row["kind"] == "generation_request"]
        self.assertEqual({r["purpose"] for r in requests}, {"cap_policy", "cap_function", "cap_objects"})
        self.assertEqual(len({r["episode_id"] for r in requests}), 1)

    def test_uncertain_native_state_has_no_fabricated_final_and_stops_run(self):
        class UncertainEnvironment(FakeEnvironment):
            def execute(self, script):
                self.execution_failed = True
                return False
        agent, output = self.agent({"cap_policy": "def policy():\n    open('fridge')"}, factory=UncertainEnvironment)
        self.assertFalse((output / "tasks" / "open_fridge" / "final_state.json").exists())
        self.assertEqual(agent.task_record("bad_program")["status"], "not_executed")
        results = json.loads((output / "results.json").read_text())
        self.assertEqual(results["summary"]["num_tasks"], 2)
        self.assertEqual(results["summary"]["SR"], 0)

    def test_specialized_context_is_fresh_and_query_results_are_not_implicit_input(self):
        agent, output = self.agent({
            "cap_policy": '''def policy():
    fridge = [o for o in get_visible_objects() if o.name == 'fridge'][0]
    old_states = get_object_states(fridge)
    open(fridge)
    return parse_question('is fridge open?')''',
            "cap_question": "fridge = [o for o in get_visible_objects() if o.name == 'fridge'][0]\nret_val = 'OPEN' in get_object_states(fridge)",
        }, tasks=("open fridge",))
        events = json.loads((output / "tasks" / "open_fridge" / "generation.json").read_text())
        requests = [e for e in events if e["kind"] == "generation_request"]
        self.assertEqual(requests[0]["observation_revision"], 0)
        self.assertEqual(requests[1]["observation_revision"], 1)
        self.assertNotIn("observation_revision", requests[1]["prompt"])
        self.assertNotIn("old_states", requests[1]["prompt"])
        self.assertEqual(requests[1]["parent_call_id"], requests[0]["call_id"])
        execution = json.loads((output / "tasks" / "open_fridge" / "execution.json").read_text())
        self.assertTrue(execution["result"])
        self.assertEqual(execution["counts"]["model_requests"], 2)

    def test_failed_recursive_generation_preserves_sources_and_partial_edges(self):
        agent, output = self.agent({
            "cap_policy": "def policy():\n    return helper_a()",
            "cap_function": {
                "helper_a(": "def helper_a():\n    return helper_b()",
                "helper_b(": "def helper_b(:\n    invalid syntax!",
            },
        }, tasks=("open fridge",))
        directory = output / "tasks" / "open_fridge"
        self.assertIn("def helper_b(:", (directory / "helpers.py").read_text())
        dependencies = json.loads((directory / "dependencies.json").read_text())
        self.assertEqual(dependencies["edges"][0]["caller"], "helper_a")
        self.assertEqual(dependencies["edges"][0]["dependency"], "helper_b")
        self.assertFalse(agent.task_record("open_fridge")["dependency_resolution_succeeded"])
        self.assertEqual(agent.task_record("open_fridge")["status"], "execution_failed")
