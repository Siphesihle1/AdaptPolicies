import argparse
from dataclasses import dataclass
import os
from typing import Optional, get_args

from methods.progprompt.agent import ProgPromptAgent
from methods.progprompt.datasets import Dataset, validate_dataset
from methods.progprompt.prompt import ExamplesType

from methods.config import get_config


@dataclass
class ProgramArgs:
    env_id: int
    test_set: Dataset
    examples_type: ExamplesType
    examples_num: int
    expt_name: str
    num_tasks: Optional[int]


def execute_progprompt_agent(args: ProgramArgs):
    validate_dataset(args.env_id, args.test_set)
    get_config()  # Validate before connecting to the simulator.
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
def parse_num_tasks(value):
    if value == "all":
        return None
    try:
        count = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            "expected a positive integer or 'all'"
        ) from None
    if count < 1:
        raise argparse.ArgumentTypeError("expected a positive integer or 'all'")
    return count


def parse_args(argv=None) -> ProgramArgs:
    parser = argparse.ArgumentParser()

    parser.add_argument("--expt-name", type=str, required=True)
    parser.add_argument("--env-id", type=int, required=True, choices=(0, 1, 2))
    parser.add_argument(
        "--test-set",
        type=str,
        choices=get_args(Dataset),
        help="Required for scene 0; omit for env1/env2 in their matching scenes",
    )
    parser.add_argument(
        "--num-tasks",
        type=parse_num_tasks,
        required=True,
        help="Positive task count or 'all' for the complete dataset",
    )
    parser.add_argument(
        "--examples-type",
        type=str,
        required=True,
        choices=["default", "random"],
    )
    parser.add_argument("--examples-num", type=int, required=True, choices=range(1, 7))

    args = parser.parse_args(argv)
    if args.test_set is None:
        if args.env_id == 0:
            parser.error("--test-set is required for --env-id 0")
        args.test_set = f"env{args.env_id}"
    try:
        validate_dataset(args.env_id, args.test_set)
    except ValueError as error:
        parser.error(str(error))
    return ProgramArgs(**vars(args))


def main(argv=None):
    args = parse_args(argv)
    os.environ["EXPERIMENT_NAME"] = args.expt_name

    execute_progprompt_agent(args)


if __name__ == "__main__":
    main()
