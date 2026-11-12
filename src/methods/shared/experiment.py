import os
import json
from pathlib import Path
from typing import Any, TypedDict
from methods import telemetry as weave
from methods.config import get_config

class TaskRecordFields(TypedDict):
    status: str
    plan: str | None
    thread_id: str | None
    error: str | dict[str, Any] | None


class TaskRecord(TaskRecordFields, total=False):
    method: str
    episode_id: str
    generated: bool
    code_valid: bool
    dependency_resolution_succeeded: bool
    final_state_available: bool
    prompt: str
    states_file: str
    chat_file: str
    chat_call_id: str
    raw_plan: str
    raw_format_compliant: bool
    fence_stripped: bool
    fenced_generations: int


class ExperimentMixin:
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
