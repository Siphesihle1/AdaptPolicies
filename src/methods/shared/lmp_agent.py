"""Task lifecycle and durable failure-inclusive experiments for the LMP methods.

Shared by Code as Policies and Adaptive Policies. A method subclasses LMPAgent
to name itself and to supply its environment adapter, runtime and examples.
"""

import json
import os
from pathlib import Path
from uuid import uuid4

from methods import telemetry
from methods.chat_transcript import PlanChatTranscript, capture_transcript
from methods.config import get_config, require_method_profiles
from methods.shared.datasets import load_tasks
from methods.shared.ground_truth import load_ground_truth_graphs, normalize_task_name
from methods.shared.evaluation import EvaluationMixin
from methods.shared.experiment import ExperimentMixin
from virtual_home.environment import VHEnvironment
from virtual_home.task import VHTask
from .lmp_runtime import Limits, serialize


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(serialize(value), indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


class LMPAgent(ExperimentMixin, EvaluationMixin):
    # Set by each method: its name (also its configuration section and model
    # profile set), the environment adapter and the PolicyRuntime subclass.
    method = None
    adapter_class = None
    runtime_class = None

    def load_tasks(self, env_id, test_set):
        return load_tasks(env_id, test_set)

    def load_ground_truth_graphs(self, test_set, tasks):
        return load_ground_truth_graphs(test_set, tasks)

    def select_examples(self, examples_type, examples_num, task_names, exclude_tasks):
        raise NotImplementedError

    def limits_from_config(self, config):
        return Limits(**config.get(self.method, {}))

    def configure_environment(self, env):
        """Apply method-specific simulator settings to a freshly initialized episode."""

    def __init__(self, env_id, test_set, examples_type="default", examples_num=3,
                 num_tasks=None, *, environment_factory=VHEnvironment, generator=None,
                 limits=None, example_tasks=None, exclude_example_tasks=()):
        config = get_config()
        if generator is None:
            require_method_profiles(self.method)
        self.limits = limits or self.limits_from_config(config)
        self.env_id, self.dataset = env_id, test_set
        self.environment_factory, self.generator = environment_factory, generator
        all_tasks = self.load_tasks(env_id, test_set)
        self.ground_truth_graphs = self.load_ground_truth_graphs(test_set, all_tasks)
        selected = all_tasks[:num_tasks] if num_tasks else all_tasks
        self.plans = {normalize_task_name(t): [] for t in selected}
        self.instructions = {normalize_task_name(t): t for t in selected}
        if len(self.plans) != len(selected):
            raise ValueError("Duplicate task identity")
        self.exclude_example_tasks = tuple(exclude_example_tasks)
        self.examples = self.select_examples(examples_type, examples_num, task_names=example_tasks,
                                             exclude_tasks=self.exclude_example_tasks)
        self.final_states, self.initial_states = [], []
        self.exec_per_task, self.results, self.task_records, self.chat_transcripts = {}, {}, {}, {}
        self.num_tasks_parsed = self.num_tasks_executed = 0
        self.evaluation_logger = telemetry.evaluation_logger(
            name=f"{os.getenv('EXPERIMENT_NAME')}:{uuid4()}", model=config["llm"]["model"],
            dataset=test_set, eval_attributes={**telemetry.experiment_attributes(),
                "method": self.method, "dataset": test_set, "environment_id": env_id})
        self.output = Path(os.environ["JOB_OUTPUT_DIR"])
        self.output.mkdir(parents=True, exist_ok=True)
        write_json(self.output / "configuration.json", {**config, f"resolved_{self.method}": self.limits,
                   "examples_type": examples_type, "examples_num": examples_num,
                   "example_tasks": example_tasks, "excluded_example_tasks": self.exclude_example_tasks,
                   "example_seed": 42, "instance_selection": "episode_scoped_explicit_id_or_legacy_class"})

    def execute_tasks(self):
        self.export_results()
        terminal_error = None
        for task in self.plans:
            record = self.task_record(task)
            directory = self.output / "tasks" / task
            directory.mkdir(parents=True, exist_ok=True)
            logs = self.output / "task_logs" / task
            logs.mkdir(parents=True, exist_ok=True)
            thread_id = f"{os.getenv('EXPERIMENT_NAME')}:{task}:{uuid4()}"
            record.update(thread_id=thread_id, method=self.method)
            self.chat_transcripts[task] = PlanChatTranscript()
            if terminal_error:
                record.update(status="not_executed", error=terminal_error)
                self.export_results()
                continue
            env = runtime = None
            task_state = VHTask(task, thread_id, [self.instructions[task]], self.limits.max_actions)
            log = (logs / "task_logs.txt").open("a", encoding="utf-8")
            try:
                with capture_transcript(self.chat_transcripts[task]), telemetry.thread(thread_id=thread_id), telemetry.attributes({
                    "method": self.method, "task_instruction": task, "dataset": self.dataset,
                    "environment_id": self.env_id}):
                    # Same environment, initial room, character and omitted action as ProgPrompt.
                    env = self.environment_factory(self.env_id, "kitchen", task_state, log)
                    env.actions_to_omit = [("grab", "wallphone")]
                    self.configure_environment(env)
                    adapter = self.adapter_class(env, task_state)
                    record["episode_id"] = env.episode_id
                    write_json(directory / "initial_state.json", env.initial_state)
                    inventory = {
                        "object_classes": sorted({n["class_name"] for n in env.graph["nodes"]
                                                  if n.get("category") != "Rooms" and n["class_name"] != "character"}),
                        "room_names": sorted({n["class_name"] for n in env.graph["nodes"] if n.get("category") == "Rooms"}),
                    }
                    runtime = self.runtime_class(adapter, self.limits, self.generator)
                    execution = runtime.run(self.instructions[task], self.examples, inventory, thread_id,
                                            exclude_example_tasks=self.exclude_example_tasks)
                    record.update(status=execution["status"], error=execution.get("error"),
                                  final_state_available=execution["final_state_available"])
                    self.save_execution(directory, runtime, execution, record)
                    if execution["final_state_available"]:
                        final, initial, executability, _ = task_state.finish(env)
                        self.final_states.append(final)
                        self.initial_states.append(initial)
                        self.exec_per_task[task] = executability
                        write_json(directory / "final_state.json", final)
                    else:
                        terminal_error = "Run stopped after uncertain native state; simulator requires restart"
                    if execution["status"] == "executed":
                        self.num_tasks_executed += 1
            except Exception as error:
                record.update(status="execution_failed", error=f"{type(error).__name__}: {error}")
                # Initialization or finalization may have contacted Unity. Never
                # initialize another task after an unverified native failure.
                if env is None or getattr(env, "native_state_uncertain", False):
                    terminal_error = "Run stopped after simulator initialization/native failure"
            finally:
                # Pending native calls may still reference their log. The launcher
                # owns simulator cleanup; do not continue with that simulator.
                if not (runtime and runtime.native_pending):
                    log.close()
                record["final_state_available"] = task in self.exec_per_task
                write_json(directory / "chat.json", self.chat_transcripts[task].messages)
                self.publish_task_chat(task)
                self.export_results()
        self.eval()
        self.export_results(run_status="aborted" if terminal_error else "completed", error=terminal_error)
        self.log_eval_results(run_status="aborted" if terminal_error else "completed", error=terminal_error)

    def save_execution(self, directory, runtime, execution, record):
        events = runtime.events
        generations = [e for e in events if e["kind"].startswith("generation")]
        helpers = [e for e in events if e["kind"] == "helper"]
        policies = [e for e in events if e["kind"] == "policy"]
        if policies:
            source = policies[0]["source"]
            (directory / "policy.py").write_text(source, encoding="utf-8")
            record["plan"] = source
        if policies and not any(e["kind"] == "generation_error" for e in events):
            # Validation and dependency outcomes are recorded independently of goal success.
            record["generated"] = True
        record["code_valid"] = any(e["kind"] == "code_validation" and e["program"] == "policy" for e in events)
        record["dependency_resolution_succeeded"] = any(e["kind"] == "validated" and e["program"] == "policy" for e in events)
        self.num_tasks_parsed += int(record["dependency_resolution_succeeded"])
        # Fenced responses were unwrapped before validation (see strip_code_fence).
        fenced = sum(bool(e.get("fence_stripped")) for e in events if e["kind"] == "generation")
        record.update(fenced_generations=fenced, fence_stripped=fenced > 0, raw_format_compliant=fenced == 0)
        sources = [e for e in events if e["kind"] == "helper_source"]
        (directory / "helpers.py").write_text("\n\n".join(h["source"] for h in sources), encoding="utf-8")
        write_json(directory / "dependencies.json", {"resolved_helpers": helpers, "sources": sources,
                   "requests": [e for e in events if e["kind"] == "helper_requested"],
                   "edges": [e for e in events if e["kind"] == "dependency_edge"]})
        write_json(directory / "generation.json", generations)
        write_json(directory / "execution.json", execution)

    def eval(self):
        statuses = {task: self.task_record(task)["status"] for task in self.plans}
        super().eval()
        for task, status in statuses.items():
            if status != "executed":
                self.task_record(task)["status"] = status

    def export_results(self, run_status="running", error=None):
        super().export_results(run_status, error)
        write_json(self.output / "task-accounting.json", {task: self.task_record(task) for task in self.plans})
        path = self.output / "results.json"
        result = json.loads(path.read_text(encoding="utf-8"))
        result["method"] = self.method
        result["evaluation_protocol"]["object_resolution"] = "episode_scoped_explicit_id_or_legacy_class"
        write_json(path, result)
