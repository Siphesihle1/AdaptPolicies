import argparse
from dataclasses import dataclass
import os
from typing import Optional, cast

from methods.progprompt.agent import ProgPromptAgent
from methods.progprompt.prompt import Env0TestSet, ExamplesType


@dataclass
class ProgramArgs:
    env_id: int
    test_set: Env0TestSet
    examples_type: ExamplesType
    examples_num: int
    expt_name: Optional[str] = None
    num_tasks: Optional[int] = None


def execute_progprompt_agent(args: ProgramArgs):
    progprompt_agent = ProgPromptAgent(
        env_id=args.env_id,
        test_set=args.test_set,
        examples_type=args.examples_type,
        examples_num=args.examples_num,
        num_tasks=args.num_tasks,
    )

    progprompt_agent.generate_task_plans()
    progprompt_agent.generate_tasks_scripts()
    progprompt_agent.exec_plans()
    progprompt_agent.eval()
    progprompt_agent.log_eval_results()


# Adapted from https://github.com/tan90cot0/progprompt-vh/blob/main/scripts/run_eval.py#L253
if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("--expt-name", type=str, required=False)
    parser.add_argument("--env-id", type=int, default=0)
    parser.add_argument(
        "--test-set",
        type=str,
        default="test_unseen",
        choices=["train", "test_unseen", "test_seen", "test_unseen_ambiguous"],
    )
    parser.add_argument("--num-tasks", type=int, required=False)
    parser.add_argument(
        "--examples-type",
        type=str,
        default="default",
        choices=["default", "random"],
    )
    parser.add_argument("--examples-num", type=int, default=3, choices=range(1, 7))

    args = cast(ProgramArgs, parser.parse_args())

    os.environ["EXPERIMENT_NAME"] = args.expt_name if args.expt_name else ""

    execute_progprompt_agent(args)
