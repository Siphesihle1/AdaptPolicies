"""Task lifecycle and failure-inclusive Adaptive Policies experiments."""

from collections import Counter
import ast
from copy import deepcopy
import json

from methods.shared.datasets import load_tasks
from methods.shared.ground_truth import load_ground_truth_graphs
from methods.shared.lmp_agent import LMPAgent, write_json
from methods.shared.lmp_runtime import PolicyRuntime
from methods.shared.evaluation import get_object_relations, get_object_states
from .environment import AdaptiveEnvironment
from .prompt import select_examples
from .session import AdaptiveSession
from .settings import AdaptiveLimits

RECOVERY_EVENTS = {"checkpoint_failed", "recovery_generated", "recovery_result", "helper_regenerated",
                   "replan", "terminated_no_progress"}


class AdaptivePolicyRuntime(PolicyRuntime):
    session_class = AdaptiveSession
    observation_label = "AP observation"
    action_span, query_span = "ap_action", "ap_query"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.failure_states = {}

    def on_event(self, event):
        if event["kind"] != "checkpoint_failed":
            return
        names = ["first_failure"]
        if event["trigger"] == "exception":
            names.append("first_exception")
        for name in names:
            if name in self.failure_states:
                continue
            env = self.adapter.env
            if env.native_state_uncertain:
                continue
            graph = deepcopy(env.graph)
            # Match VHTask.finish's derived physical-effect augmentation.
            effects = getattr(env, "nodes_with_additonal_states", {})
            for node in graph["nodes"]:
                for state in effects.get(node["id"], {}).get("states", []):
                    if state in {"WASHED", "HEATED", "USED"} and state not in node["states"]:
                        node["states"].append(state)
            self.failure_states[name] = graph


class AdaptiveAgent(LMPAgent):
    method = "adaptive"
    adapter_class = AdaptiveEnvironment
    runtime_class = AdaptivePolicyRuntime

    def load_tasks(self, env_id, test_set):
        return load_tasks(env_id, test_set)

    def load_ground_truth_graphs(self, test_set, tasks):
        return load_ground_truth_graphs(test_set, tasks)

    def limits_from_config(self, config):
        return AdaptiveLimits(**config.get(self.method, {}))

    def select_examples(self, examples_type, examples_num, task_names, exclude_tasks):
        return select_examples(examples_type, examples_num, task_names=task_names,
                               exclude_tasks=exclude_tasks, placement=self.limits.placement)

    def configure_environment(self, env):
        # A rejected script did not run, so AP recovers from it (D7).
        env.stop_after_unity_rejection = False

    def save_execution(self, directory, runtime, execution, record):
        super().save_execution(directory, runtime, execution, record)
        events = runtime.events
        for event in (e for e in events if e["kind"] == "replan"):
            (directory / f"policy.replan-{event['number']}.py").write_text(event["source"], encoding="utf-8")
        write_json(directory / "recoveries.json", [e for e in events if e["kind"] in RECOVERY_EVENTS])
        for name in ("first_failure", "first_exception"):
            path = directory / f"{name}_state.json"
            if name in runtime.failure_states:
                write_json(path, runtime.failure_states[name])
            else:
                # Reusing an output directory must not score a previous episode's failure.
                path.unlink(missing_ok=True)
        record.update(adaptive_summary(events, execution))

    def eval(self):
        super().eval()
        for task in self.plans:
            directory = self.output / "tasks" / task
            initial_path, final_path = directory / "initial_state.json", directory / "final_state.json"
            if not initial_path.exists():
                continue
            initial = json.loads(initial_path.read_text(encoding="utf-8"))
            for name in ("first_failure", "first_exception"):
                path = directory / f"{name}_state.json"
                # No corresponding failure: the counterfactual is the actual final state.
                state_path = path if path.exists() else final_path
                if not state_path.exists():
                    continue
                graph = json.loads(state_path.read_text(encoding="utf-8"))
                self.task_record(task)[f"without_{'recovery' if name == 'first_failure' else 'exception_recovery'}"] = (
                    goal_scores(initial, graph, self.ground_truth_graphs[task]))


def goal_scores(initial, state, target):
    """Use the shared evaluator's class-based changed-condition PSR/SR definition."""
    relations_in, states_in = get_object_relations(initial), get_object_states(initial)
    wanted_relations = get_object_relations(target) - relations_in
    wanted_states = get_object_states(target) - states_in
    unsatisfied = (len(wanted_relations - (get_object_relations(state) - relations_in))
                   + len(wanted_states - (get_object_states(state) - states_in)))
    total = len(wanted_relations) + len(wanted_states)
    psr = 1 - unsatisfied / total if total else 0
    return {"PSR": psr, "SR": int(psr == 1)}


def adaptive_summary(events, execution):
    """Per-task checkpoint and recovery counts for the task record."""
    failed = [e for e in events if e["kind"] == "checkpoint_failed"]
    results = [e for e in events if e["kind"] == "recovery_result"]
    placed = 0
    for event in events:
        if event["kind"] != "generation":
            continue
        try:
            tree = ast.parse(event["source"])
        except SyntaxError:
            continue
        placed += sum(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                      and node.func.id == "checkpoint" for node in ast.walk(tree))
    error = execution.get("error") or ""
    if execution.get("status") == "executed":
        termination = "returned"
    elif "NoProgress" in error:
        termination = "no_progress"
    elif "deadline" in error:
        termination = "deadline"
    elif "_limit" in error:
        termination = "budget"
    elif not execution.get("final_state_available", True):
        termination = "uncertain_native_state"
    else:
        termination = "error"
    return {
        "placement": execution.get("limits", {}).get("placement"),
        "checkpoints_placed": placed,
        "checkpoints_reached": sum(e["kind"] == "checkpoint_reached" for e in events),
        "checkpoints_passed": sum(e["kind"] == "checkpoint_passed" for e in events),
        "checkpoints_recovered": sum(r["trigger"] == "checkpoint" and r["scope"] == "local" and r["succeeded"]
                                     for r in results),
        "model_calls_by_purpose": dict(Counter(e["purpose"] for e in events if e["kind"] == "generation_request")),
        "failures_by_trigger": dict(Counter(e["trigger"] for e in failed)),
        "recoveries_by_scope": {scope: {"attempted": sum(r["scope"] == scope for r in results),
                                        "succeeded": sum(r["scope"] == scope and r["succeeded"] for r in results)}
                                for scope in ("local", "helper")},
        "replans": sum(e["kind"] == "replan" for e in events),
        "helper_regenerations": sum(e["kind"] == "helper_regenerated" for e in events),
        "first_failure_trigger": failed[0]["trigger"] if failed else None,
        "termination": termination,
    }
