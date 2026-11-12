"""Task lifecycle and failure-inclusive Adaptive Policies experiments."""

from collections import Counter

from methods.shared.datasets import load_tasks
from methods.shared.ground_truth import load_ground_truth_graphs
from methods.shared.lmp_agent import LMPAgent, write_json
from methods.shared.lmp_runtime import PolicyRuntime
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
        record.update(adaptive_summary(events, execution))


def adaptive_summary(events, execution):
    """Per-task checkpoint and recovery counts for the task record."""
    failed = [e for e in events if e["kind"] == "checkpoint_failed"]
    results = [e for e in events if e["kind"] == "recovery_result"]
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
        "checkpoints_passed": sum(e["kind"] == "checkpoint_passed" for e in events),
        "failures_by_trigger": dict(Counter(e["trigger"] for e in failed)),
        "recoveries_by_scope": {scope: {"attempted": sum(r["scope"] == scope for r in results),
                                        "succeeded": sum(r["scope"] == scope and r["succeeded"] for r in results)}
                                for scope in ("local", "helper")},
        "replans": sum(e["kind"] == "replan" for e in events),
        "helper_regenerations": sum(e["kind"] == "helper_regenerated" for e in events),
        "first_failure_trigger": failed[0]["trigger"] if failed else None,
        "termination": termination,
    }
