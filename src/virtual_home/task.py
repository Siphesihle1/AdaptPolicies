import os

from typing import List, TYPE_CHECKING
import copy
from uuid_utils import uuid7


if TYPE_CHECKING:
    from .environment import VHEnvironment


class VHTask:
    def __init__(
        self,
        task_instruction: str,
        thread_id: str,
        subtasks: List[str],
        max_steps: int = -1,
    ):
        self.task_instruction = task_instruction
        self.subtasks = subtasks
        self.current_subtask_index = 0
        self.current_subtask = subtasks[0]
        self.step = 1
        self.total_steps = 0
        self.executable_steps = 0
        self.max_steps = max_steps
        self.terminate_current_subtask = False
        self.thread_id = thread_id

    def track_subtask(self, subtask_index: int):
        self.step = 1
        self.current_subtask_index = subtask_index
        self.current_subtask = self.subtasks[subtask_index]

    @property
    def terminate_current_subtask(self):
        if self.step != -1 and self.step > self.max_steps:
            return True

        return self._skip_actions

    @terminate_current_subtask.setter
    def terminate_current_subtask(self, value: bool):
        self._skip_actions = value

    def finish(self, env: "VHEnvironment"):
        # Adapted from https://github.com/NVlabs/progprompt-vh/blob/main/scripts/utils_execute.py#L160
        final_state = copy.deepcopy(env.graph)
        initial_state = copy.deepcopy(env.initial_state)
        nodes_with_additional_states = env.nodes_with_additonal_states

        # augment state with additional state info
        for idx in range(len(final_state["nodes"])):
            if final_state["nodes"][idx]["id"] in nodes_with_additional_states.keys():
                final_state["nodes"][idx] = nodes_with_additional_states[
                    final_state["nodes"][idx]["id"]
                ]

        env.log_file.close()

        # get final state for eval
        return (
            final_state,
            initial_state,
            self.executable_steps / self.total_steps,
            env.images,
        )
