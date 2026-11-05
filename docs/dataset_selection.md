# Selecting a dataset and simulator scene

All CLI options are mandatory with one exception: scenes 1 and 2 may omit
`--test-set`, which selects env1 and env2, respectively. Scene 0 always requires
an explicit split, and no other run setting has a CLI default:

- `--expt-name`: experiment name.
- `--env-id`: simulator scene 0, 1, or 2.
- `--test-set`: required scene-0 split, or optional explicit env1/env2 selection.
- `--num-tasks`: positive integer or `all` for the complete dataset.
- `--examples-type`: `default` or `random`, explicitly selected.
- `--examples-num`: example count from 1 to 6.

The dataset and scene must match. Train, test_seen, test_unseen, and
test_unseen_ambiguous_goals require scene 0. Env1 requires scene 1; env2 requires
scene 2. Missing required options, unknown names, or incompatible selections are rejected
before simulator construction. Programmatic runner/agent calls also require an
explicit dataset and reject mismatched scenes; they do not infer a dataset.

Env1 and env2 read `new_env/env1_annotated.json` and
`new_env/env2_annotated.json`, respectively. They use the matching
`final_states_env1.json` / `final_states_env2.json` references and mapping
manifests. Each dataset therefore identifies both its tasks and its references.
Use the full ambiguous-goal name `test_unseen_ambiguous_goals`; the former CLI
spelling `test_unseen_ambiguous` is rejected.

`--env-id` selects the Unity scene to reset for prompt construction and again
for each task execution. Task execution captures its own runtime initial graph
after adding the character; saved `initial_states_env1/2.json` files are not
loaded. See [initial-state provenance](ground_truth_graphs.md#initial-state-provenance)
for the evaluation baseline and how to compare historical snapshots.

## WSL examples

From the repository root in the existing configured environment, with the
simulator already started through its configured launcher:

```bash
export ADAPT_CONFIG=dev
export PROGPROMPT_DATASET_DIR="$PWD/src/methods/progprompt/data"
export JOB_OUTPUT_DIR="$PWD/outputs/local"

python -m methods.progprompt.run_eval \
  --expt-name local_test_seen --env-id 0 --test-set test_seen \
  --num-tasks 1 --examples-type default --examples-num 3

python -m methods.progprompt.run_eval \
  --expt-name local_ambiguous --env-id 0 --test-set test_unseen_ambiguous_goals \
  --num-tasks all --examples-type random --examples-num 3

python -m methods.progprompt.run_eval \
  --expt-name local_env1 --env-id 1 \
  --num-tasks all --examples-type default --examples-num 3

python -m methods.progprompt.run_eval \
  --expt-name local_env2 --env-id 2 \
  --num-tasks all --examples-type default --examples-num 3
```

These commands start planning/evaluation runs. They do not establish that every
stored goal is complete or that every generated plan succeeds. `--num-tasks`
limits planning tasks, while reference validation covers the complete selected
dataset. See [ground-truth evaluation](ground_truth_graphs.md) and the
[mapping audit](ground_truth_graph_mapping_audit.md) for known goal issues.

## Launchers

The cluster launcher `src/methods/progprompt/progprompt_run.sh` explicitly selects
scene 0, train, random examples, three examples, its experiment name, and
`--num-tasks all`. It copies active `data/` contents, including the six manifests,
to `PROGPROMPT_DATASET_DIR`; the sibling original-data archive is excluded.
The diagnostic `src/test-scripts/virtual_home_exec_test.sh` forwards its command
arguments to the runner; supply all six options when invoking it.

No cluster jobs or simulator runs were started to validate the selection change.
Tests check mandatory arguments, scene/dataset consistency, task counts, and
matching task/reference loading across all six datasets without a simulator.
