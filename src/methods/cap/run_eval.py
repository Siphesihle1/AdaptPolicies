"""CaP command-line entry point; simulator ownership belongs to the shared launcher."""

import os
from methods import telemetry
from methods.progprompt.run_eval import parse_args
from .agent import CaPAgent


def main(argv=None):
    args = parse_args(argv)
    os.environ["EXPERIMENT_NAME"] = args.expt_name
    with telemetry.attributes({**telemetry.experiment_attributes(), "method": "cap",
                               "dataset": args.test_set, "environment_id": args.env_id}):
        agent = CaPAgent(args.env_id, args.test_set, args.examples_type,
                         args.examples_num, args.num_tasks)
        try:
            agent.execute_tasks()
        except Exception as error:
            agent.export_results("aborted", f"{type(error).__name__}: {error}")
            raise


if __name__ == "__main__":
    main()
