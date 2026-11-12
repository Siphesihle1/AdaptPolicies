"""Small live AP placement diagnostic on training tasks, excluding target examples.

Run inside the configured Python environment with a supervised simulator. This
contacts the configured model; literal example replay uses validate_examples.py.
"""

import argparse
from dataclasses import replace
import json
import os
from pathlib import Path

from methods.adaptive.agent import AdaptiveAgent
from methods.adaptive.settings import AdaptiveLimits
from methods.config import get_config


class DevAgent(AdaptiveAgent):
    def load_tasks(self, env_id, test_set):
        self.all_tasks = super().load_tasks(env_id, test_set)
        selected = os.environ["AP_DEV_TASK"]
        tasks = [t for t in self.all_tasks if "_".join(t.split()) == selected]
        if not tasks:
            raise ValueError(f"Unknown training task: {selected}")
        return tasks

    def load_ground_truth_graphs(self, test_set, tasks):
        graphs = super().load_ground_truth_graphs(test_set, self.all_tasks)
        return {"_".join(t.split()): graphs["_".join(t.split())] for t in tasks}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--task", default="put_apple_in_fridge")
    parser.add_argument("--placements", nargs="+", choices=["both", "explicit", "implicit"],
                        default=["both", "explicit", "implicit"])
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=True)
    os.environ["AP_DEV_TASK"] = args.task
    base = AdaptiveLimits(**get_config().get("adaptive", {}))
    rows = []
    for placement in args.placements:
        output = args.output / placement
        os.environ["JOB_OUTPUT_DIR"] = str(output)
        os.environ["EXPERIMENT_NAME"] = f"ap-dev-{placement}"
        agent = DevAgent(0, "train", limits=replace(base, placement=placement),
                         exclude_example_tasks=(args.task,))
        agent.execute_tasks()
        record = agent.task_record(args.task)
        execution_path = output / "tasks" / args.task / "execution.json"
        execution = json.loads(execution_path.read_text(encoding="utf-8")) if execution_path.exists() else {}
        row = {"placement": placement, "task": args.task, "status": record["status"],
               "error": record.get("error"), "termination": record.get("termination"),
               "scores": agent.results.get(args.task),
               "failures_by_trigger": record.get("failures_by_trigger"),
               "replans": record.get("replans"),
               "generation_counts": execution.get("generation_counts"),
               "counts": execution.get("counts"),
               "without_recovery": record.get("without_recovery"),
               "without_exception_recovery": record.get("without_exception_recovery")}
        rows.append(row)
        (args.output / "dev-report.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(row), flush=True)
        if not record.get("final_state_available"):
            raise RuntimeError("Simulator state unavailable; restart before continuing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
