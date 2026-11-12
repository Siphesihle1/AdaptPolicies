"""Task lifecycle and durable failure-inclusive CaP experiments."""

from methods.shared.datasets import load_tasks
from methods.shared.ground_truth import load_ground_truth_graphs
from methods.shared.lmp_agent import LMPAgent, write_json  # noqa: F401
from .environment import CaPEnvironment
from .prompt import select_examples
from .runtime import PolicyRuntime


class CaPAgent(LMPAgent):
    method = "cap"
    adapter_class = CaPEnvironment
    runtime_class = PolicyRuntime

    # Resolved through this module so callers can substitute task sources.
    def load_tasks(self, env_id, test_set):
        return load_tasks(env_id, test_set)

    def load_ground_truth_graphs(self, test_set, tasks):
        return load_ground_truth_graphs(test_set, tasks)

    def select_examples(self, examples_type, examples_num, task_names, exclude_tasks):
        return select_examples(examples_type, examples_num, task_names=task_names,
                               exclude_tasks=exclude_tasks)
