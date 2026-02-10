import os
import json
import random
from dataclasses import dataclass
from typing import List, Dict, Any, Literal, Optional
from virtual_home.graph_query import N
from virtualhome.simulation.unity_simulator import UnityCommunication

from .constants import DEFAULT_EXAMPLES, TASK_FUNCTION_PROMPT_PREAMBLE

Env0TestSet = Literal["test_unseen", "test_seen", "test_unseen_ambiguous_goals"]
ExamplesType = Literal["default", "random"]


def init_simulator(env_id: int) -> Dict[str, Any]:
    comm = UnityCommunication(file_name=None, port=os.getenv("SIM_PORT", "8082"))
    comm.reset(env_id)
    return comm.environment_graph()[1]


def load_task_prompt_examples() -> Dict[str, str]:
    with open(
        f"{os.getenv('PROGPROMPT_DATASET_DIR')}/pythonic_plans/train_complete_plan_set.json",
        "r",
    ) as f:
        tmp = json.load(f)
        prompt_examples = {}
        for k, v in tmp.items():
            prompt_examples[k] = v

    return prompt_examples


def load_tasks_from_file(file_path: str) -> List[str]:
    tasks: List[str] = []

    with open(file_path, "r") as f:
        for line in f.readlines():
            tasks.append(list(json.loads(line.strip()).keys())[0])
    return tasks


def load_tasks_from_dir(dir_path: str) -> List[str]:
    tasks: List[str] = []

    for file in sorted(os.listdir(dir_path))[::-1]:
        with open(os.path.join(dir_path, file), "r") as f:
            for line in f.readlines():
                tasks.append(list(json.loads(line.strip()).keys())[0])
    return tasks


@dataclass(frozen=True)
class Prompt:
    text: str
    task_instruction: str


class PromptBuilder:
    def __init__(self, env_id: int):
        self._imports: List[str] = []
        self._objects: List[str] = []
        self._examples: List[str] = []
        self._tasks: List[str] = []
        self.env_id = env_id
        self.graph = init_simulator(env_id)

    def with_imports(self, imports: List[str]):
        self._imports.extend(imports)
        return self

    def with_objects(self):
        objects: List[str] = list(set(N(self.graph).select("class_name")))  # type: ignore
        self._objects.extend(objects)
        return self

    def with_examples(self, examples_type: ExamplesType, num_examples=3, seed=42):
        prompt_examples = load_task_prompt_examples()
        example_keys: List[str] = []

        if examples_type == "default":
            example_keys = DEFAULT_EXAMPLES[:num_examples]
        else:
            random.seed(seed)
            example_keys = random.sample(list(prompt_examples.keys()), num_examples)

        examples = [prompt_examples[k] for k in example_keys]

        self._examples.extend(examples)
        return self

    def with_tasks(
        self,
        test_set: Optional[Env0TestSet] = None,
        num_tasks: Optional[int] = None,
    ):
        tasks: List[str] = []

        if test_set is not None:
            dir_path = f"{os.getenv('PROGPROMPT_DATASET_DIR')}/{test_set}"
            tasks = load_tasks_from_dir(dir_path)
        else:
            file_path = f"{os.getenv('PROGPROMPT_DATASET_DIR')}/new_env/env{self.env_id}_annotated.json"
            tasks = load_tasks_from_file(file_path)

        self._tasks = tasks[:num_tasks] if num_tasks else tasks
        return self

    def _build_prompt(
        self, task: str, include_preamble=True, include_section_divisions=True
    ) -> Prompt:
        sections: List[str] = []

        if include_preamble:
            sections.append(TASK_FUNCTION_PROMPT_PREAMBLE)

        if len(self._imports) > 0:
            actions_section_heading = (
                "# Available actions\n" if include_section_divisions else ""
            )
            imports_code = "\n".join(self._imports)
            sections.append(f"{actions_section_heading}{imports_code}")

        if len(self._objects) > 0:
            objects_section_heading = (
                "# Available objects\n" if include_section_divisions else ""
            )
            sections.append(f"{objects_section_heading}objects = {self._objects}")

        if len(self._examples) > 0:
            examples_section_heading = (
                f"# Example task function{'s' if len(self._examples) > 1 else ''}\n"
                if include_section_divisions
                else ""
            )
            examples_code = "\n\n".join(self._examples)
            sections.append(f"{examples_section_heading}{examples_code}")

        task_section_heading = (
            "# Now complete the following task function\n"
            if include_section_divisions
            else ""
        )
        task_function_name = "_".join(task.split(" "))
        sections.append(f"{task_section_heading}def {task_function_name}():")

        final_prompt = "\n\n".join(sections)

        return Prompt(text=f"{final_prompt}\n\t", task_instruction=task_function_name)

    def __iter__(self):
        for task in self._tasks:
            yield self._build_prompt(task)
