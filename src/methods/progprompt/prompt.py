import os
import json
import random
from dataclasses import dataclass
from typing import List, Dict, Any, Literal, Optional
from graph_query import N
from unity_simulator.comm_unity import UnityCommunication

from .constants import DEFAULT_EXAMPLES

Env0TestSet = Literal["test_unseen", "test_seen", "test_unseen_ambiguous_goals"]
ExamplesType = Literal["default", "random"]


def init_simulator(env_id: int) -> Dict[str, Any]:
    comm = UnityCommunication(file_name=None, port=os.getenv("SIM_PORT", "8082"))
    comm.reset(env_id)
    return comm.environment_graph()[1]


def load_task_prompt_examples() -> Dict[str, str]:
    with open(
        f"{os.getenv('DATASET_DIR')}/pythonic_plans/train_complete_plan_set.json",
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

    for file in os.listdir(dir_path):
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
        objects: List[str] = N(self.graph).select("class_name")  # type: ignore
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
    ):
        tasks: List[str] = []

        if test_set is not None:
            dir_path = f"{os.getenv('DATASET_DIR')}/data/{test_set}"
            tasks = load_tasks_from_dir(dir_path)
        else:
            file_path = (
                f"{os.getenv('DATASET_DIR')}/new_env/env{self.env_id}_annotated.json"
            )
            tasks = load_tasks_from_file(file_path)

        self._tasks.extend(tasks)
        return self

    def _build_prompt(self, task: str) -> Prompt:
        sections: List[str] = []

        sections.append("\n".join(self._imports))

        if len(self._objects) > 0:
            sections.append(f"objects = {self._objects}")

        sections.append("\n\n".join(self._examples))

        task_function_name = "_".join(task.split(" "))
        sections.append(f"def {task_function_name}():")

        final_prompt = "\n\n".join(sections)

        return Prompt(text=f"{final_prompt}\n\t", task_instruction=task)

    def __iter__(self):
        for task in self._tasks:
            yield self._build_prompt(task)
