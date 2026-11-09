import io
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from methods.progprompt.actions import Assert


class AssertObservationTests(unittest.TestCase):
    def test_second_held_object_keeps_explicit_possession_in_filtered_prompt(self):
        env = SimpleNamespace(
            objs="bed, clothespants, clothesshirt. You have clothespants, clothesshirt.",
            objs_in_hand=["clothespants", "clothesshirt"],
            log_file=io.StringIO(),
        )
        task = SimpleNamespace(
            thread_id="held-observation",
            task_instruction="place_clothes",
            current_subtask="place",
        )
        with patch(
            "methods.progprompt.actions.generate", return_value="True"
        ) as generate:
            self.assertTrue(Assert(env, task).action("'clothesshirt' in 'hands'"))
        prompt = generate.call_args.kwargs["prompt"]
        self.assertIn("\nYou have clothesshirt.", prompt)

    def test_unheld_object_is_not_reported_as_held(self):
        env = SimpleNamespace(
            objs="clothesshirt ON bed. You have clothespants.",
            objs_in_hand=["clothespants"],
            log_file=io.StringIO(),
        )
        task = SimpleNamespace(
            thread_id="unheld-observation",
            task_instruction="place_clothes",
            current_subtask="place",
        )
        with patch(
            "methods.progprompt.actions.generate", return_value="False"
        ) as generate:
            self.assertFalse(Assert(env, task).action("'clothesshirt' in 'hands'"))
        self.assertNotIn("You have clothesshirt", generate.call_args.kwargs["prompt"])
