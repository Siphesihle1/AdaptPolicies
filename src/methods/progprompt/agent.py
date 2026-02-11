from importlib import invalidate_caches
import json
import os
import sys

from ollama import GenerateResponse

from virtual_home.graph_query import N
from uuid_utils import uuid7
import weave

from methods.llm import LMOllama
from .constants import MODEL, TASK_PROMPT_ACTION_IMPORTS
from .prompt import Env0TestSet, ExamplesType, PromptBuilder
from .task_scripts import exec_task, generate_task_scripts

from typing import Any, Dict, List, Optional, Set

sys.path.insert(0, os.getenv("JOB_OUTPUT_DIR", ""))


def get_object_relations(state: Dict[str, Any]) -> Set[str]:
    obj_ids = dict(N(state).select("id", "class_name"))

    return set(
        [
            " ".join([obj_ids[e["from_id"]], e["relation_type"], obj_ids[e["to_id"]]])
            for e in state["edges"]
        ]
    )


def get_object_states(state: Dict[str, Any]) -> Set[str]:
    return set(
        [n["class_name"] + " " + st for n in state["nodes"] for st in n["states"]]
    )


def get_ground_truth_final_states(test_set: str) -> List[Dict[str, Any]]:
    final_states_gt: List[Dict[str, Any]] = []

    with open(
        f"{os.getenv('PROGPROMPT_DATASET_DIR')}/final_states/final_states_{test_set}.json",
        "r",
    ) as f:
        for line in f.readlines():
            final_states_gt.append(json.loads(line))

    return final_states_gt


class ProgPromptAgent:
    def __init__(
        self,
        env_id: int,
        examples_type: ExamplesType = "default",
        examples_num=3,
        test_set: Optional[Env0TestSet] = None,
        num_tasks: Optional[int] = None,
    ):
        self.env_id = env_id
        self.test_set = test_set
        self.prompt_builder = (
            PromptBuilder(env_id=env_id)
            .with_imports([TASK_PROMPT_ACTION_IMPORTS])
            .with_objects()
            .with_examples(examples_type, examples_num)
            .with_tasks(test_set=test_set, num_tasks=num_tasks)
        )
        self.plans: Dict[str, List[str]] = {}
        self.final_states: List[Dict[str, Any]] = []
        self.dataset = test_set if test_set else f"env{env_id}"
        self.final_states_gt = get_ground_truth_final_states(self.dataset)
        self.initial_states: List[Dict[str, Any]] = []
        self.exec_per_task: Dict[str, float] = {}
        self.results: Dict[str, Dict[str, float]] = {}
        self.evaluation_logger = weave.EvaluationLogger(
            model=MODEL,
            dataset=self.dataset,
            eval_attributes={
                "experiment_name": os.getenv("EXPERIMENT_NAME"),
                "dataset": self.dataset,
                "environment_id": self.env_id,
            },
        )

    def generate_task_plans(self):
        for prompt in self.prompt_builder:
            task = prompt.task_instruction
            prompt_text = prompt.text
            thread_id = f"{os.getenv('EXPERIMENT_NAME')}:{task}:{str(uuid7())}"

            with weave.thread(thread_id=thread_id):
                with weave.attributes(
                    {
                        "task_instruction": task,
                    }
                ):
                    response: GenerateResponse = LMOllama(
                        prompt=prompt_text,
                        model=MODEL,
                        __weave={
                            "display_name": thread_id,
                        },
                    )

            plan = response.response or ""

            if not plan.strip().startswith("def"):
                print(
                    f"\n\n---Plan for task '{task}' does not start with a function definition.---\n\n{plan}"
                )
                continue

            if plan.strip().count("def") > 1:
                print(
                    f"\n\n---Plan for task '{task}' contains multiple function definitions.---\n\n{plan}"
                )
                continue

            if "```" in plan.strip():
                print(
                    f"\n\n---Plan for task '{task}' contains code block formatting.---\n\n{plan}"
                )
                continue

            self.plans[task] = [plan.strip(), thread_id]

        with open(f"{os.getenv('JOB_OUTPUT_DIR')}/plans.json", "w") as f:
            json.dump(self.plans, f, indent=4)

    def generate_tasks_scripts(self):
        for task, (plan, thread_id) in self.plans.items():
            log_file_prefix = f"{os.getenv('JOB_OUTPUT_DIR')}/task_logs/{task}"
            task_scripts_prefix = f"{os.getenv('JOB_OUTPUT_DIR')}/tasks"

            generate_task_scripts(
                log_file_prefix,
                task_scripts_prefix,
                task,
                thread_id,
                plan,
                self.env_id,
            )

    def exec_plans(self):
        invalidate_caches()

        for task, _ in self.plans.items():
            log_file_prefix = f"{os.getenv('JOB_OUTPUT_DIR')}/task_logs/{task}"

            task_results = exec_task(task, log_file_prefix)

            if task_results is None:
                continue

            final_state, initial_state, task_exec, _ = task_results

            self.final_states.append(final_state)
            self.initial_states.append(initial_state)
            self.exec_per_task[task] = task_exec

    def log_eval_results(self):
        for task, metrics in self.results.items():
            if task == "overall":
                continue

            inputs = {
                "task_instruction": task,
            }

            pred = self.evaluation_logger.log_prediction(
                inputs=inputs, output=self.plans[task][0]
            )

            for metric_name, metric_value in metrics.items():
                pred.log_score(metric_name, metric_value)

            pred.finish()

        if "overall" in self.results:
            self.evaluation_logger.log_summary(
                self.results["overall"], auto_summarize=False
            )

    # Adapted from https://github.com/tan90cot0/progprompt-vh/blob/main/scripts/run_eval.py#L37
    def eval(self):
        ## the evaluation criteria is not perfect
        ## since sometimes the tasks are underspecified, like which object to interact with
        ## for example "turn off lightswitch" could happen in multiple locations
        ## the evaluation happens w.r.t one possible valid state
        ## that the annotator provides

        sr: List[float] = []
        unchanged_conds: List[int] = []
        total_unchanged_conds: List[int] = []
        test_tasks = self.plans.keys()

        for g, g_gt, g_in, task in zip(
            self.final_states, self.final_states_gt, self.initial_states, test_tasks
        ):
            relations_in = get_object_relations(g_in)
            obj_states_in = get_object_states(g_in)

            relations = get_object_relations(g)
            obj_states = get_object_states(g)

            relations_gt = get_object_relations(g_gt)
            obj_states_gt = get_object_states(g_gt)

            changed_gt_relations = relations_gt - relations_in
            changed_gt_obj_states = obj_states_gt - obj_states_in
            changed_relations = relations - relations_in
            changed_obj_states = obj_states - obj_states_in

            unsatisfied_relations = changed_gt_relations - changed_relations
            unsatisfied_obj_states = changed_gt_obj_states - changed_obj_states

            task_log_file = f"{os.getenv('JOB_OUTPUT_DIR')}/task_logs/{'_'.join(task.split(' '))}/task_logs.txt"

            with open(task_log_file, "a") as f:
                f.write(
                    f"\nchanged ground truth relations: {changed_gt_relations}, changed ground truth states: {changed_gt_obj_states}"
                )
                f.write(
                    f"\nchanged relations: {changed_relations}, changed object states: {changed_obj_states}"
                )
                f.write(
                    f"\nunsatisfied state conditions: relations: {unsatisfied_relations}, object states: {unsatisfied_obj_states}"
                )

            unsatisf_conds = len(unsatisfied_relations) + len(unsatisfied_obj_states)
            total_goal_conds = len(changed_gt_relations) + len(changed_gt_obj_states)

            sr.append(1 - unsatisf_conds / total_goal_conds)

            unchanged_conds.append(
                len(relations_gt.intersection(relations_in) - relations)
                + len(obj_states_gt.intersection(obj_states_in) - obj_states)
            )
            total_unchanged_conds.append(
                len(relations_gt.intersection(relations_in))
                + len(obj_states_gt.intersection(obj_states_in))
            )

            self.results[task] = {
                "PSR": sr[-1],
                "SR": sr[-1:].count(1.0),
                "Precision": 1 - unchanged_conds[-1] / total_unchanged_conds[-1],
                "Exec": self.exec_per_task[task],
            }

        if len(test_tasks) > 0:
            self.results["overall"] = {
                "PSR": sum(sr) / len(sr),
                "SR": sr.count(1.0) / len(sr),
                "Precision": 1 - sum(unchanged_conds) / sum(total_unchanged_conds),
                "Exec": sum(self.exec_per_task.values()) / len(self.exec_per_task),
            }
