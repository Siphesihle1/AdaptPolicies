from typing import Tuple

from openai.types.completion import Completion
import weave
from virtual_home.actions import Action
from virtual_home.task import VHTask
import re
import os

from .environment import ProgPromptEnvironment
from .constants import ASSERT_PROMPT_PREAMBLE, CURRENT_STATE_PROMPT, MODEL

from methods.llm import LLMOpenAI


# Adapted from https://github.com/NVlabs/progprompt-vh/blob/main/scripts/utils_execute.py#L48
def get_current_state_prompt():
    ## fixed function to define "PROMPT for state check"
    objs = ["microwave", "book", "lightswitch", "bookshelf", "cereal"]
    state, asserts = CURRENT_STATE_PROMPT.split("\n\n")
    state = state.split(",")
    state = "You see: " + ", ".join(
        [i.strip() for i in state if any(element in i for element in objs)]
    )
    current_state_prompt = f"{ASSERT_PROMPT_PREAMBLE}{state}\n\n{asserts}"
    return current_state_prompt


class Assert(Action):
    def __init__(self, env: ProgPromptEnvironment, task: VHTask):
        self.env = env
        self.task = task
        self.action_name = "assert"
        self.current_state_prompt = get_current_state_prompt()

    def __call__(self, assert_cond: str):
        return super().run(assert_cond)

    def action(self, *objs: str):
        # Adapted from https://github.com/NVlabs/progprompt-vh/blob/main/scripts/utils_execute.py#L148
        (assert_cond,) = objs

        assert_objs = re.findall(r"\b[a-z]+", assert_cond)[0::2]
        state = self.env.objs.split(",")
        state = "You see: " + ", ".join(
            [i.strip() for i in state if any(ele in i for ele in assert_objs)]
        )
        action = f"{self.action_name}({assert_cond})"

        current_state = f"{ASSERT_PROMPT_PREAMBLE}\n\n{state}\n\n{action}\n"
        weave_display_name = (
            f"{os.getenv('EXPERIMENT_NAME')}:{self.task.task_instruction}"
        )

        with weave.attributes(
            {
                "task_instruction": self.task.task_instruction,
                "subtask": self.task.current_subtask,
            }
        ):
            llmResult: Tuple[Completion, str] = LLMOpenAI(
                prompt=current_state,
                model=MODEL,
                thread_id=self.task.thread_id,
                __weave={
                    "display_name": weave_display_name,
                },
            )

        _, check_state = llmResult

        self.env.log_file.write(
            f"State check:\n{state}\n{action}\n{check_state.strip()}\n"
        )

        return (
            True if "True" in check_state else False if "False" in check_state else None
        )
