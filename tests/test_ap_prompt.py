"""AP prompt text per purpose and placement condition (V6), with stored snapshots.

Set AP_PROMPT_RECORD=1 to re-record the snapshots after a deliberate prompt change.
"""

import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from methods.adaptive.prompt import build_prompt, select_examples
from virtual_home.virtualhome_types import ObjectRef

SNAPSHOTS = Path(__file__).parent / "fixtures" / "ap_prompts.json"
DATASET = Path(__file__).parents[1] / "src" / "methods" / "progprompt" / "data"
EPISODE = "episode-1"
MUG, FRIDGE = ObjectRef(EPISODE, 20, "mug"), ObjectRef(EPISODE, 10, "fridge")
CONTEXT = {"episode_id": EPISODE, "observation_revision": 2, "visible_objects": [FRIDGE, MUG],
           "observation": {"current_room": "kitchen", "visible_objects": ["fridge is CLOSED", "mug"],
                           "relations": ["fridge INSIDE kitchen", "mug INSIDE kitchen"], "held_objects": []}}
INVENTORY = {"object_classes": ["fridge", "mug"], "room_names": ["bedroom", "kitchen"]}
FAILURE = {"program": "# policy\ndef policy():\n    open('fridge')  # <- failed here",
           "failure": "Kind: action\nAction: open(fridge)\nMessage: fridge is locked",
           "progress": "Completed so far:\n- walk(kitchen) succeeded", "bindings": "fridge = fridge"}


def prompts():
    with patch.dict(os.environ, {"ADAPT_DATASET_DIR": str(DATASET)}):
        cases = {}
        for placement in ("both", "explicit", "implicit"):
            examples = select_examples("default", 3, placement=placement)
            cases[f"{placement}/policy"] = build_prompt(EPISODE, "ap_policy", "open the fridge", CONTEXT, examples,
                                                        INVENTORY, placement=placement)
            cases[f"{placement}/function"] = build_prompt(EPISODE, "ap_function", "Implement helper f for call: f(x)",
                                                          None, "", INVENTORY, placement=placement)
            cases[f"{placement}/regenerate"] = build_prompt(
                EPISODE, "ap_function", "Rewrite helper f so that it handles the failure.", CONTEXT, "", INVENTORY,
                placement=placement, failure={k: v for k, v in FAILURE.items() if k != "bindings"})
            cases[f"{placement}/recover"] = build_prompt(EPISODE, "ap_recover", "Recover from the failure below.",
                                                         CONTEXT, "", INVENTORY, placement=placement, failure=FAILURE)
            cases[f"{placement}/replan"] = build_prompt(
                EPISODE, "ap_replan", "open the fridge", CONTEXT, "", INVENTORY, placement=placement,
                failure={k: v for k, v in FAILURE.items() if k != "bindings"})
            cases[f"{placement}/objects"] = build_prompt(EPISODE, "ap_objects", "visible mugs", CONTEXT, "",
                                                         INVENTORY, placement=placement)
            cases[f"{placement}/question"] = build_prompt(EPISODE, "ap_question", "is the fridge open?", CONTEXT,
                                                          "", INVENTORY, placement=placement)
        return cases


def sections(prompt):
    import re
    return re.findall(r"^<([a-z-]+)>$", prompt, re.M)


class PromptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prompts = prompts()

    def test_checkpoint_appears_only_with_explicit_checkpoints(self):
        for name, prompt in self.prompts.items():
            placement, kind = name.split("/")
            with self.subTest(name=name):
                if placement == "implicit" or kind in {"objects", "question"}:
                    self.assertNotIn("checkpoint(", prompt)
                elif kind in {"policy", "function", "replan"}:
                    self.assertIn("checkpoint(description, check)", prompt)

    def test_cap_failure_handling_guidance_is_absent(self):
        for name, prompt in self.prompts.items():
            with self.subTest(name=name):
                self.assertNotIn("check result.status explicitly", prompt)
                self.assertNotIn("Helpers may return booleans", prompt)
                self.assertNotIn("return False", prompt)
                self.assertNotIn('.status != "succeeded"', prompt)
                self.assertNotIn("Return True on success", prompt)

    def test_query_programs_see_no_actions_or_policy_rules(self):
        for placement in ("both", "explicit", "implicit"):
            for kind in ("objects", "question"):
                prompt = self.prompts[f"{placement}/{kind}"]
                self.assertNotIn("grab(item)", prompt)
                self.assertNotIn("parse_objects(description)", prompt)
                self.assertNotIn("helper", prompt.split("<examples>")[0])
                self.assertIn("Use queries only; do not perform actions.", prompt)

    def test_instruction_explains_the_recovery_mechanism(self):
        self.assertIn("The policy runs with checkpoints", self.prompts["both/policy"])
        self.assertIn("Failed actions are recovered automatically", self.prompts["implicit/policy"])
        self.assertIn("as if each step succeeds", self.prompts["both/policy"])

    def test_section_order_puts_the_failure_last(self):
        common = ["instructions", "rules", "api", "environment", "objects", "rooms", "observation", "examples"]
        self.assertEqual(sections(self.prompts["both/recover"]),
                         common + ["request", "program", "failure", "progress", "bindings", "output-format"])
        self.assertEqual(sections(self.prompts["both/replan"]),
                         common + ["task", "program", "failure", "progress", "output-format"])
        self.assertEqual(sections(self.prompts["both/policy"]), common + ["task", "output-format"])

    def test_recovery_rules_by_purpose(self):
        self.assertIn("Do not call checkpoint inside recover", self.prompts["both/recover"])
        for placement in ("both", "explicit", "implicit"):
            recover = self.prompts[f"{placement}/recover"]
            # Recovery code has no checkpoints and no nested recovery.
            self.assertNotIn("checkpoint(description, check)", recover)
            self.assertNotIn("failures are recovered", recover)
            self.assertNotIn("A failed action is recovered before", recover)
            self.assertIn("Failures inside recover are not recovered again", recover)
        self.assertIn("return True if its effect already holds", self.prompts["both/recover"])
        self.assertNotIn("<bindings>", self.prompts["both/replan"])
        self.assertIn("Keep its name and parameters", self.prompts["both/regenerate"])
        self.assertIn("Do not repeat steps that &lt;progress&gt; shows as completed", self.prompts["both/replan"])

    def test_examples_follow_the_placement_condition(self):
        self.assertIn("checkpoint(", self.prompts["both/policy"].split("<examples>")[1])
        self.assertNotIn("checkpoint(", self.prompts["implicit/policy"].split("<examples>")[1])
        self.assertNotIn("checkpoint(", self.prompts["implicit/function"])

    def test_prompts_match_snapshots(self):
        if os.getenv("AP_PROMPT_RECORD") == "1":
            SNAPSHOTS.parent.mkdir(parents=True, exist_ok=True)
            SNAPSHOTS.write_text(json.dumps(self.prompts, indent=1, sort_keys=True) + "\n", encoding="utf-8",
                                 newline="\n")
            self.skipTest("Recorded AP prompt snapshots")
        self.maxDiff = None
        expected = json.loads(SNAPSHOTS.read_text(encoding="utf-8"))
        self.assertEqual(sorted(self.prompts), sorted(expected))
        for name, prompt in expected.items():
            self.assertEqual(self.prompts[name], prompt, name)


if __name__ == "__main__":
    unittest.main()
