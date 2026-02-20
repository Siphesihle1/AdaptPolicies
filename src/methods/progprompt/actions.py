from openai.types.chat import ChatCompletion
import weave
from virtual_home.actions import Action
from virtual_home.task import VHTask
import re

from .environment import ProgPromptEnvironment
from .constants import ASSERT_PROMPT_PREAMBLE_SHORT, CURRENT_STATE_PROMPT_EXAMPLE, MODEL

from methods.llm import LLMOpenAI


# Adapted from https://github.com/NVlabs/progprompt-vh/blob/main/scripts/utils_execute.py#L48
def get_current_state_prompt():
    ## fixed function to define "PROMPT for state check"
    objs = ["microwave", "book", "lightswitch", "bookshelf", "cereal"]
    state, asserts = CURRENT_STATE_PROMPT_EXAMPLE.split("\n\n")
    state = state.split(",")
    state = "You see: " + ", ".join(
        [i.strip() for i in state if any(element in i for element in objs)]
    )
    return (
        f"{ASSERT_PROMPT_PREAMBLE_SHORT}\n\n<example>\n{state}\n\n{asserts}\n</example>"
    )


class Assert(Action):
    def __init__(self, env: ProgPromptEnvironment, task: VHTask):
        self.env = env
        self.task = task
        self.action_name = "assert"

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

        current_state = f"{get_current_state_prompt()}\n\n{state}\n\n{action}\n"

        with weave.thread(thread_id=self.task.thread_id):
            with weave.attributes(
                {
                    "task_instruction": self.task.task_instruction,
                    "subtask": self.task.current_subtask,
                }
            ):
                response: ChatCompletion = LLMOpenAI(
                    prompt=current_state,
                    temperature=0,
                    model=MODEL,
                    __weave={
                        "display_name": self.task.thread_id,
                    },
                )

        check_state = response.choices[0].message.content or ""

        self.env.log_file.write(
            f"State check:\n{state}\n{action}\n{check_state.strip()}\n"
        )

        return (
            True if "True" in check_state else False if "False" in check_state else None
        )
