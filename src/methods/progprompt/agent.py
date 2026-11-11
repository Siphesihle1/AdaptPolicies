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


def strip_code_fence(plan: str) -> tuple[str, bool]:
    """Remove one Markdown code block wrapping the whole response.

    Returns the plan and whether a wrapper was removed. Only a response that is a
    single ```...``` block is unwrapped; anything else is returned unchanged, so
    the format checks still reject stray or multiple fences.
    """
    lines = plan.strip().splitlines()
    if (
        len(lines) >= 2
        and lines[0].strip().startswith("```")
        and lines[-1].strip() == "```"
        and not any(line.strip().startswith("```") for line in lines[1:-1])
    ):
        return "\n".join(lines[1:-1]), True
    return plan, False


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


class TaskRecordFields(TypedDict):
    status: str
    plan: str | None
    thread_id: str | None
    error: str | dict[str, Any] | None


class TaskRecord(TaskRecordFields, total=False):
    prompt: str
    states_file: str
    chat_file: str
    chat_call_id: str
    raw_plan: str
    raw_format_compliant: bool
    fence_stripped: bool


class ProgPromptAgent:
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
        dataset_dir = Path(os.environ["PROGPROMPT_DATASET_DIR"])
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

    def task_record(self, task: str) -> TaskRecord:
        artifacts = self.plans.get(task, [])
        return self.task_records.setdefault(
            task,
            {
                "status": "pending",
                "plan": artifacts[0] if artifacts else None,
                "thread_id": artifacts[1] if len(artifacts) == 2 else None,
                "error": None,
            },
        )

    def evaluation_summary(self) -> dict[str, Any]:
        count = len(self.plans)
        metrics = [self.results[task] for task in self.plans if task in self.results]
        return {
            "num_tasks": count,
            "num_tasks_parsed": self.num_tasks_parsed,
            "num_tasks_executed": self.num_tasks_executed,
            "num_tasks_evaluated": len(metrics),
            "num_tasks_without_results": count - len(metrics),
            **{
                name: sum(row[name] for row in metrics) / count if count else 0
                for name in ("SR", "PSR", "Exec")
            },
            "conditional_metrics": self.results.get("overall", {}),
        }

    def publish_task_chat(self, task: str) -> None:
        record = self.task_record(task)
        transcript = self.chat_transcripts.get(task)
        if transcript is None or not record["thread_id"] or record.get("chat_call_id"):
            return
        final_message = f"Execution status: {record['status']}"
        if record["error"]:
            final_message += f"\nError: {record['error']}"
        with weave.thread(thread_id=record["thread_id"]):
            call_id = weave.publish_plan_chat(transcript.messages, final_message, task)
        if call_id:
            record["chat_call_id"] = call_id

    def export_results(
        self, run_status: str = "running", error: str | None = None
    ) -> None:
        rows = {}
        for task in self.plans:
            if task in self.chat_transcripts:
                chat_path = (
                    Path(os.environ["JOB_OUTPUT_DIR"]) / "task_chats" / f"{task}.json"
                )
                chat_path.parent.mkdir(parents=True, exist_ok=True)
                chat_path.write_text(
                    json.dumps(
                        {
                            "messages": self.chat_transcripts[task].messages,
                            "status": self.task_record(task)["status"],
                            "error": self.task_record(task)["error"],
                        },
                        indent=2,
                    )
                    + "\n",
                    encoding="utf-8",
                )
                self.task_record(task)["chat_file"] = str(
                    chat_path.relative_to(os.environ["JOB_OUTPUT_DIR"])
                )
            record = dict(self.task_record(task))
            record["metrics"] = self.results.get(
                task, {"SR": 0, "PSR": 0, "Exec": 0, "Precision": None}
            )
            rows[task] = record
        output = {
            "schema_version": 1,
            "evaluation_protocol": {
                "headline_denominator": "all_intended_tasks",
                "missing_result_scores": {
                    "SR": 0,
                    "PSR": 0,
                    "Exec": 0,
                    "Precision": None,
                },
                "precision_scope": "evaluated_tasks_only",
                "object_resolution": "held_class_binding_close_room_native_distance_id_v1",
            },
            "experiment_name": os.getenv("EXPERIMENT_NAME"),
            "dataset": self.dataset,
            "environment_id": self.env_id,
            "run_status": run_status,
            "error": error,
            "configuration": get_config(),
            "summary": self.evaluation_summary(),
            "tasks": rows,
        }
        path = Path(os.environ["JOB_OUTPUT_DIR"]) / "results.json"
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)

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

    def log_eval_results(
        self, run_status: str = "completed", error: str | None = None
    ) -> None:
        if self.evaluation_logger is None:
            return

        for task in self.plans:
            record = self.task_record(task)
            metrics = self.results.get(task, {"SR": 0, "PSR": 0, "Exec": 0})

            inputs = {
                "task_instruction": task,
            }

            pred = self.evaluation_logger.log_prediction(
                inputs=inputs,
                output={key: record[key] for key in ("plan", "status", "error")},
            )

            for metric_name, metric_value in metrics.items():
                pred.log_score(metric_name, metric_value)

            pred.finish()

        summary = {
            **self.evaluation_summary(),
            "run_status": run_status,
            "error": error,
        }
        self.evaluation_logger.log_summary(summary, auto_summarize=False)

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
        test_tasks = list(self.plans)

        for g, g_in, task in zip(
            self.final_states, self.initial_states, self.exec_per_task
        ):
            ground_truth_graph = self.ground_truth_graphs[task]

            relations_in = get_object_relations(g_in)
            obj_states_in = get_object_states(g_in)

            relations = get_object_relations(g)
            obj_states = get_object_states(g)

            relations_gt = get_object_relations(ground_truth_graph)
            obj_states_gt = get_object_states(ground_truth_graph)

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

            sr.append(
                1 - unsatisf_conds / total_goal_conds if total_goal_conds > 0 else 0
            )

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
                "Precision": (
                    1 - unchanged_conds[-1] / total_unchanged_conds[-1]
                    if total_unchanged_conds[-1] > 0
                    else 0
                ),
                "Exec": self.exec_per_task[task],
            }
            self.task_record(task)["status"] = "evaluated"

        if len(test_tasks) > 0:
            self.results["overall"] = {
                "PSR": sum(sr) / len(sr) if sr else 0,
                "SR": sr.count(1.0) / len(sr) if sr else 0,
                "Precision": (
                    1 - sum(unchanged_conds) / sum(total_unchanged_conds)
                    if sum(total_unchanged_conds) > 0
                    else 0
                ),
                "Exec": (
                    sum(self.exec_per_task.values()) / len(self.exec_per_task)
                    if self.exec_per_task
                    else 0
                ),
            }
