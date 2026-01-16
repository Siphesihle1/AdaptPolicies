from virtual_home.actions import Action
from virtual_home.task import VHTask
import re

from .environment import ProgPromptEnvironment
from .constants import CURRENT_STATE_PROMPT, MODEL

from methods.llm import LM


def get_current_state_prompt():
    ## fixed function to define "PROMPT for state check"
    objs = ["microwave", "book", "lightswitch", "bookshelf", "cereal"]
    state, asserts = CURRENT_STATE_PROMPT.split("\n\n")
    state = state.split(",")
    state = "You see: " + ", ".join(
        [i.strip() for i in state if any(element in i for element in objs)]
    )
    current_state_prompt = f"{state}\n\n{asserts}"
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
        (assert_cond,) = objs

        assert_objs = re.findall(r"\b[a-z]+", assert_cond)[0::2]
        state = self.env.objs.split(",")
        state = "You see: " + ", ".join(
            [i.strip() for i in state if any(ele in i for ele in assert_objs)]
        )
        action = f"{self.action_name}({assert_cond})"

        current_state = f"{self.current_state_prompt}\n\n{state}\n\n{action}\n"

        _, check_state = LM(
            prompt=current_state, model=MODEL, max_tokens=2, stop=["\n"]
        )

        self.env.log_file.write(
            f"State check:\n{state}\n{action}\n{check_state.strip()}\n"
        )

        return (
            True if "True" in check_state else False if "False" in check_state else None
        )
