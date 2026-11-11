from methods.shared.datasets import load_tasks_from_dir, load_tasks_from_file, dataset_root
import os
import re
import json
import random
from dataclasses import dataclass
from typing import List, Dict, Any, Literal, Optional
from virtual_home.graph_query import N
from virtualhome.simulation.unity_simulator import UnityCommunication

from .constants import DEFAULT_EXAMPLES
from .datasets import Dataset, validate_dataset
from .ground_truth import normalize_task_name

ExamplesType = Literal["default", "random"]


def init_simulator(env_id: int) -> Dict[str, Any]:
    comm = UnityCommunication(file_name=None, port=os.getenv("SIM_PORT", "8082"))
    comm.reset(env_id)
    return comm.environment_graph()[1]


def load_task_prompt_examples() -> Dict[str, str]:
    with open(
        dataset_root() / "pythonic_plans" / "train_complete_plan_set.json",
        "r",
    ) as f:
        return {
            name: plan for example in json.load(f) for name, plan in example.items()
        }






@dataclass(frozen=True)
class Prompt:
    text: str
    task_instruction: str


class PromptBuilder:
    def __init__(self, env_id: int, preamble: Optional[str] = None):
        self._imports: List[str] = []
        self._objects: List[str] = []
        self._examples: List[str] = []
        self._tasks: List[str] = []
        self.env_id = env_id
        self.graph = init_simulator(env_id)
        self.preamble = preamble

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
        test_set: Dataset,
        num_tasks: Optional[int] = None,
    ):
        validate_dataset(self.env_id, test_set)
        tasks: List[str] = []

        if self.env_id == 0:
            dir_path = str(dataset_root() / test_set)
            tasks = load_tasks_from_dir(dir_path)
        else:
            file_path = str(dataset_root() / "new_env" / f"env{self.env_id}_annotated.json")
            tasks = load_tasks_from_file(file_path)

        self._tasks = tasks[:num_tasks] if num_tasks else tasks
        return self

    def _build_prompt(
        self, task: str, include_preamble=True, include_section_divisions=True
    ) -> Prompt:
        sections: List[str] = []

        if include_preamble and self.preamble is not None:
            sections.append(self.preamble)

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
        task_function_name = normalize_task_name(task)
        sections.append(f"{task_section_heading}def {task_function_name}():")

        final_prompt = "\n\n".join(sections)

        return Prompt(text=f"{final_prompt}\n\t", task_instruction=task_function_name)

    def __iter__(self):
        for task in self._tasks:
            yield self._build_prompt(task)
