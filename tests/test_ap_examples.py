"""Static checks of the AP few-shot examples (V1); simulator replays are separate."""

import ast
import json
from pathlib import Path
import unittest

from methods.adaptive.session import AdaptiveSession
from methods.adaptive.settings import AdaptiveLimits
from methods.adaptive.validate_examples import ExampleGenerator, SCENARIOS, load_rows, strip_checkpoints
from methods.adaptive.prompt import load_examples
from methods.shared.lmp_environment import ACTION_CLASSES, QUERY_NAMES

ROOT = Path(__file__).parents[1] / "src" / "methods"
TRAIN = set(json.loads((ROOT / "progprompt" / "data" / "ground_truth_graph_mappings" / "train.json").read_text()))


def session(placement):
    bindings = {name: (lambda *a: None) for name in [*ACTION_CLASSES, *QUERY_NAMES]}
    return AdaptiveSession("episode", bindings, {"episode_id": "episode", "observation_revision": 0,
                                                 "visible_objects": []}, AdaptiveLimits(placement=placement))


def failure_handling(source):
    """CaP-style failure handling the AP examples must not teach."""
    tree = ast.parse(source)
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Constant) and node.value.value is False:
            found.append("return False")
        if isinstance(node, ast.Attribute) and node.attr == "status":
            found.append("status check")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "parse_question":
            found.append("parse_question self-check")
    return found


class ExampleTests(unittest.TestCase):
    def test_policy_examples_cover_cap_identities_and_validate(self):
        cap = json.loads((ROOT / "cap" / "examples" / "policy.json").read_text())
        for name, placement in (("policy", "both"), ("policy_implicit", "implicit")):
            examples = load_rows(name)
            self.assertEqual(list(examples), list(cap), name)
            self.assertLessEqual(set(examples), TRAIN)
            for identity, source in examples.items():
                with self.subTest(file=name, identity=identity):
                    tree = session(placement).validate(source)
                    self.assertEqual([node.name for node in tree.body], ["policy"])
                    self.assertEqual(failure_handling(source), [])

    def test_helper_examples_validate_and_achieve_states(self):
        for name, placement in (("function_gen", "both"), ("function_gen_implicit", "implicit")):
            for row in load_rows(name):
                with self.subTest(file=name, helper=row["request"]):
                    tree = session(placement).validate(row["code"])
                    self.assertEqual(len(tree.body), 1)
                    self.assertEqual(tree.body[0].name, row["request"].split("(")[0])
                    self.assertEqual(failure_handling(row["code"]), [])
                    self.assertNotIn("Return True on success", row["code"])

    def test_implicit_examples_are_explicit_ones_without_checkpoints(self):
        for explicit, implicit in (("policy", "policy_implicit"), ("function_gen", "function_gen_implicit")):
            first, second = load_rows(explicit), load_rows(implicit)
            if isinstance(first, list):
                first = {row["request"]: row["code"] for row in first}
                second = {row["request"]: row["code"] for row in second}
            for key, source in first.items():
                with self.subTest(file=implicit, key=key):
                    self.assertEqual(second[key], strip_checkpoints(source))
                    self.assertNotIn("checkpoint", second[key])
                    if explicit == "policy":
                        # Helpers whose effect cannot be observed (run cycles) have none.
                        self.assertIn("checkpoint(", source)

    def test_specialized_examples_are_cap_examples(self):
        for name in ("parse_objects", "parse_question"):
            cap = json.loads((ROOT / "cap" / "examples" / f"{name}.json").read_text())
            self.assertEqual(load_rows(name), cap)

    def test_recovery_examples_come_from_validated_training_scenarios(self):
        scenarios = {s["id"]: s for s in SCENARIOS}
        for name, entry in (("recover", "recover"), ("regenerate_helper", "regenerate"), ("replan", "replan")):
            for row in load_rows(name):
                with self.subTest(file=name, example=row["id"]):
                    scenario = scenarios[row["id"]]
                    self.assertEqual(scenario["file"], name)
                    self.assertIn(row["task"], TRAIN)
                    self.assertEqual(row["code"], scenario[entry][-1])
                    for field in ("failure", "progress", "observation"):
                        self.assertTrue(row[field], field)
                    tree = session("both").validate(row["code"])
                    if name == "recover":
                        self.assertNotIn("checkpoint", row["code"])
                        self.assertEqual([n.name for n in tree.body], ["recover"])

    def test_strip_checkpoints_unwraps_values_and_drops_statements(self):
        source = '''def policy():
    find("x")
    xs = checkpoint("x is visible",
                    lambda: [o for o in get_visible_objects() if o.name == "x"])
    checkpoint("holding", lambda: is_holding(xs[0]))
    if xs:
        grab(xs[0])
    return checkpoint("done", lambda: True)'''
        self.assertEqual(strip_checkpoints(source), '''def policy():
    find("x")
    xs = [o for o in get_visible_objects() if o.name == "x"]
    if xs:
        grab(xs[0])''')

    def test_runtime_only_recovery_examples_validate_without_checkpoint_api(self):
        for name in ("recover", "regenerate_helper", "replan"):
            for row in load_examples(name, "implicit"):
                with self.subTest(file=name, example=row["id"]):
                    self.assertNotEqual(row["trigger"], "checkpoint")
                    self.assertNotIn("checkpoint(", row["code"])
                    session("implicit").validate(row["code"])

    def test_runtime_only_scenario_generator_strips_every_generated_program(self):
        for scenario in SCENARIOS:
            if scenario["trigger"] == "checkpoint":
                continue
            generator = ExampleGenerator("implicit", scenario)
            sources = [generator.scenario["program"], *generator.helpers.values(),
                       *(code for queue in generator.queues.values() for code in queue)]
            for source in sources:
                with self.subTest(scenario=scenario["id"], source=source):
                    self.assertNotIn("checkpoint(", source)
                    session("implicit").validate(source)


if __name__ == "__main__":
    unittest.main()
