from methods.shared.evaluation import EvaluationMixin, get_object_relations, get_object_states
from methods.shared.experiment import ExperimentMixin, TaskRecord
from methods.shared.code_fence import strip_code_fence
from importlib import invalidate_caches
import json
import os
from pathlib import Path
import sys

from virtual_home.graph_query import N
from uuid_utils import uuid7
from methods import telemetry as weave
from methods.config import get_config
from methods.chat_transcript import PlanChatTranscript, capture_transcript

from methods.llm import generate
from .constants import (
    TASK_FUNCTION_PROMPT_PREAMBLE_QWEN,
    TASK_PROMPT_ACTION_IMPORTS,
)
from .ground_truth import load_ground_truth_graphs
from .datasets import Dataset, validate_dataset
from .prompt import (
    ExamplesType,
    PromptBuilder,
    load_tasks_from_dir,
    load_tasks_from_file,
)
from .task_scripts import exec_task, generate_task_scripts

from typing import Any, Dict, List, Optional, Set, TypedDict

sys.path.insert(0, os.getenv("JOB_OUTPUT_DIR", ""))












class ProgPromptAgent(ExperimentMixin, EvaluationMixin):
    def __init__(
        self,
        env_id: int,
        test_set: Dataset,
        examples_type: ExamplesType = "default",
        examples_num=3,
        num_tasks: Optional[int] = None,
    ):
        validate_dataset(env_id, test_set)
        self.env_id = env_id
        self.test_set = test_set
        self.dataset = test_set
        dataset_dir = Path(os.environ.get("ADAPT_DATASET_DIR") or os.environ["PROGPROMPT_DATASET_DIR"])
        task_names = (
            load_tasks_from_dir(str(dataset_dir / test_set))
            if env_id == 0
            else load_tasks_from_file(
                str(dataset_dir / "new_env" / f"env{env_id}_annotated.json")
            )
        )
        self.ground_truth_graphs = load_ground_truth_graphs(self.dataset, task_names)
        self.prompt_builder = (
            PromptBuilder(env_id=env_id, preamble=TASK_FUNCTION_PROMPT_PREAMBLE_QWEN)
            .with_imports([TASK_PROMPT_ACTION_IMPORTS])
            .with_objects()
            .with_examples(examples_type, examples_num)
            .with_tasks(test_set=test_set, num_tasks=num_tasks)
        )
        # Register every intended task before generation so failed requests still
        # count in evaluation and appear in incremental exports and Weave rows.
        self.plans: Dict[str, List[str]] = {
            prompt.task_instruction: [] for prompt in self.prompt_builder
        }
        self.final_states: List[Dict[str, Any]] = []
        self.initial_states: List[Dict[str, Any]] = []
        self.exec_per_task: Dict[str, float] = {}
        self.results: Dict[str, Dict[str, float]] = {}
        self.task_records: dict[str, TaskRecord] = {}
        self.chat_transcripts: dict[str, PlanChatTranscript] = {}
        self.evaluation_logger = weave.evaluation_logger(
            name=f"{os.getenv('EXPERIMENT_NAME')}:{uuid7()}",
            model=get_config()["llm"]["model"],
            dataset=self.dataset,
            eval_attributes={
                **weave.experiment_attributes(),
                "experiment_name": os.getenv("EXPERIMENT_NAME"),
                "dataset": self.dataset,
                "environment_id": self.env_id,
            },
        )
        self.num_tasks_parsed = 0
        self.num_tasks_executed = 0





    def generate_task_plans(self):
        self.export_results()
        plan_parsing_status_file = open(
            f"{os.getenv('JOB_OUTPUT_DIR')}/plan_parsing_status.txt", "w"
        )

        for prompt in self.prompt_builder:
            task = prompt.task_instruction
            prompt_text = prompt.text
            thread_id = f"{os.getenv('EXPERIMENT_NAME')}:{task}:{str(uuid7())}"

            self.plans[task] = []
            record = self.task_record(task)
            record.update(thread_id=thread_id, prompt=prompt_text)
            self.chat_transcripts[task] = PlanChatTranscript()
            try:
                with capture_transcript(self.chat_transcripts[task]), weave.thread(
                    thread_id=thread_id
                ):
                    with weave.attributes({"task_instruction": task}):
                        plan = generate(
                            prompt=prompt_text,
                            purpose="plan",
                            __weave={"display_name": thread_id},
                        )
            except Exception as error:
                record.update(
                    status="generation_failed", error=f"{type(error).__name__}: {error}"
                )
                self.publish_task_chat(task)
                plan_parsing_status_file.write(f"Task: {task}, Success: False\n")
                plan_parsing_status_file.flush()
                self.export_results()
                continue

            # Contract compliance is judged on the raw response, before cleanup.
            raw_plan = plan
            raw_format_compliant = (
                raw_plan.strip().startswith("def") and "```" not in raw_plan
            )
            plan, fence_stripped = strip_code_fence(raw_plan)
            record.update(
                plan=plan,
                status="generated",
                raw_format_compliant=raw_format_compliant,
                fence_stripped=fence_stripped,
            )
            if fence_stripped:
                record.update(raw_plan=raw_plan)

            if not plan.strip().startswith("def"):
                print(
                    f"\n\n---Plan for task '{task}' does not start with a function definition.---\n\n{plan}"
                )
                self.plans[task] = []
                record.update(
                    status="parse_failed",
                    error="Plan does not start with a function definition",
                )
                self.publish_task_chat(task)
                plan_parsing_status_file.write(f"Task: {task}, Success: False\n")
                self.export_results()
                continue

            if plan.strip().count("def") > 1:
                print(
                    f"\n\n---Plan for task '{task}' contains multiple function definitions.---\n\n{plan}"
                )
                self.plans[task] = []
                record.update(
                    status="parse_failed",
                    error="Plan contains multiple function definitions",
                )
                self.publish_task_chat(task)
                plan_parsing_status_file.write(f"Task: {task}, Success: False\n")
                self.export_results()
                continue

            if "```" in plan.strip():
                print(
                    f"\n\n---Plan for task '{task}' contains code block formatting.---\n\n{plan}"
                )
                self.plans[task] = []
                record.update(
                    status="parse_failed", error="Plan contains Markdown code fences"
                )
                self.publish_task_chat(task)
                plan_parsing_status_file.write(f"Task: {task}, Success: False\n")
                self.export_results()
                continue

            self.plans[task] = [plan.strip(), thread_id]
            self.export_results()

        with open(f"{os.getenv('JOB_OUTPUT_DIR')}/plans.json", "w") as f:
            json.dump(self.plans, f, indent=4)

        plan_parsing_status_file.close()

    def generate_tasks_scripts(self):
        plan_parsing_status_file = open(
            f"{os.getenv('JOB_OUTPUT_DIR')}/plan_parsing_status.txt", "a"
        )

        for task, task_artifacts in self.plans.items():
            log_file_prefix = f"{os.getenv('JOB_OUTPUT_DIR')}/task_logs/{task}"
            task_scripts_prefix = f"{os.getenv('JOB_OUTPUT_DIR')}/tasks"

            if len(task_artifacts) != 2:
                continue

            plan, thread_id = task_artifacts
            success = generate_task_scripts(
                log_file_prefix,
                task_scripts_prefix,
                task,
                thread_id,
                plan,
                self.env_id,
            )

            if success:
                self.num_tasks_parsed += 1
                self.task_record(task)["status"] = "parsed"
            else:
                self.task_record(task).update(
                    status="parse_failed",
                    error="Plan could not be compiled; see task_logs.txt",
                )
                self.publish_task_chat(task)
                self.plans[task] = []

            plan_parsing_status_file.write(f"Task: {task}, Success: {success}\n")
            plan_parsing_status_file.flush()
            self.export_results()

        plan_parsing_status_file.close()

    def exec_plans(self):
        invalidate_caches()

        plan_execution_status_file = open(
            f"{os.getenv('JOB_OUTPUT_DIR')}/plan_execution_status.txt", "w"
        )

        for task, task_artifacts in self.plans.items():
            if len(task_artifacts) != 2:
                continue

            log_file_prefix = f"{os.getenv('JOB_OUTPUT_DIR')}/task_logs/{task}"

            with capture_transcript(self.chat_transcripts[task]), weave.thread(
                thread_id=task_artifacts[1]
            ), weave.attributes(
                {
                    "task_instruction": task,
                    "dataset": self.dataset,
                    "environment_id": self.env_id,
                }
            ), weave.span(
                "execute_plan", {"task_instruction": task}
            ) as execution:
                task_results = exec_task(task, log_file_prefix)
                execution["status"] = (
                    "returned" if task_results is not None else "execution_failed"
                )
                if task_results is not None:
                    execution["executability"] = task_results[2]
                if task_results is None:
                    error_path = Path(log_file_prefix) / "execution_error.json"
                    execution["error"] = (
                        json.loads(error_path.read_text(encoding="utf-8"))
                        if error_path.exists()
                        else {"message": "Task returned no execution result"}
                    )

            if task_results is None:
                plan_execution_status_file.write(f"Task: {task}, Success: False\n")
                error_path = Path(log_file_prefix) / "execution_error.json"
                error = (
                    json.loads(error_path.read_text(encoding="utf-8"))
                    if error_path.exists()
                    else {"message": "Task returned no execution result"}
                )
                self.task_record(task).update(status="execution_failed", error=error)
                self.publish_task_chat(task)
                self.plans[task] = []
                plan_execution_status_file.flush()
                self.export_results()
                continue

            plan_execution_status_file.write(f"Task: {task}, Success: True\n")
            self.num_tasks_executed += 1

            final_state, initial_state, task_exec, _ = task_results

            self.final_states.append(final_state)
            self.initial_states.append(initial_state)
            self.exec_per_task[task] = task_exec
            self.task_record(task)["status"] = "executed"
            state_path = Path(log_file_prefix) / "states.json"
            state_path.write_text(
                json.dumps({"initial_state": initial_state, "final_state": final_state})
                + "\n",
                encoding="utf-8",
            )
            self.task_record(task)["states_file"] = str(
                state_path.relative_to(os.environ["JOB_OUTPUT_DIR"])
            )
            self.publish_task_chat(task)
            plan_execution_status_file.flush()
            self.export_results()

        plan_execution_status_file.close()


    # Adapted from https://github.com/tan90cot0/progprompt-vh/blob/main/scripts/run_eval.py#L37
