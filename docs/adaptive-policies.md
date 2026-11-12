# Adaptive Policies

Adaptive Policies (AP) generates Python language model programs using the shared
Code as Policies runtime. State checkpoints run ordinary Python queries. A failed
checkpoint invokes the model with the failure, current observation, running code,
local bindings and recent execution history. Recovery escalates from a local
`recover()` to helper regeneration, then a continuation `policy()` in the same
episode. A normal policy return ends execution; the shared evaluator determines
goal success independently.

```python
def policy():
    find("fridge")
    fridge = checkpoint("a fridge is visible",
                        lambda: [o for o in get_visible_objects() if o.name == "fridge"])[0]
    open(fridge)
    checkpoint("the fridge is open", lambda: "OPEN" in (get_object_states(fridge) or ()))
```

`checkpoint(description, check)` evaluates a callable and returns its truthy value.
After local recovery it evaluates the callable again, so assignments receive fresh
references. Passing query-only checks make no model requests. Failed actions and
exceptions raised by generated code can also trigger recovery.

The `adaptive.placement` setting selects the experimental condition:

| Value | Model-written checkpoints | Failed-action recovery | Generated-code exception recovery |
| --- | --- | --- | --- |
| `both` | yes | yes | yes |
| `explicit` | yes | no | yes |
| `implicit` | absent from API and examples | yes | yes |

Local recovery returns `True` when a failed action's effect already holds;
otherwise the action is retried once. Local recovery itself has no nested recovery.
Helper regeneration replaces the definition for the rest of the episode and
escalates through the generated call stack. An exception in the top-level policy
goes directly to continuation replanning. Repeated failures without successful
actions terminate as no progress. Deadline, budget, uncertain simulator state,
syntax and validation failures remain terminal.

AP receives detailed action errors and can continue after Unity rejects an action.
CaP and ProgPrompt retain their existing error feedback and terminal rejection
behavior. The shared-code extraction is checked by the recorded CaP regression
fixture. Report these feedback and recovery differences when comparing methods.

Use the project's Python environment and dataset hooks, as described in
[configuration.md](configuration.md). The local sample uses an externally managed
LM Studio server. Every configuration must supply all six profiles: `ap_policy`,
`ap_function`, `ap_objects`, `ap_question`, `ap_recover` and `ap_replan`.

```bash
export ADAPT_CONFIG="$PROJECT_ROOT/config/adaptive.yml"
export ADAPT_DATASET_DIR="$PROJECT_ROOT/src/methods/progprompt/data"
export JOB_OUTPUT_DIR="$PROJECT_ROOT/outputs/ap-example"
bash helper-scripts/run_with_sim_and_ollama.sh helper-scripts/run-adaptive.sh \
  --expt-name ap-example --env-id 0 --test-set train --num-tasks 1 \
  --examples-type default --examples-num 3
```

The shared launcher owns simulator startup and cleanup. To use a simulator already
under supervision, run `python -m methods.adaptive.run_eval` with the same arguments.
For CPU rendering under WSL set `LIBGL_ALWAYS_SOFTWARE=1`. The sample configuration
allows 64 model requests and 900 seconds per task; model profiles and runtime limits
are separate configuration sections. There are 72 derived sweep configurations
covering the existing CaP model settings and three placement conditions. Regenerate
them with `python helper-scripts/make_ap_configs.py`. The `ap_*` Slurm jobs select
model and placement and use the shared sweep launcher.

Few-shot examples come only from training tasks. All 24 policy examples and nine
helper examples have explicit and implicit variants. Specialized query examples
are inherited from CaP. Recovery examples contain simulator-captured failure
contexts for local recovery, helper regeneration and continuation replanning.
The implicit condition omits checkpoint-triggered examples and removes checkpoint
calls from the remaining recovery examples. Prompts encourage the policy to
execute its intended steps; they omit CaP's early failure returns and boolean
helper contracts.

The paper-folder training example also approaches the bedroom bookshelf before
selecting a folder, matching its training reference destination. The initial
living-room version fell below the recorded CaP score in one replay; its initial
proximity relations also changed the scorer's denominator. This example change
should be disclosed alongside the prompt differences when comparing methods.

Validate all literal examples without contacting a model:

```bash
bash helper-scripts/validate-ap-examples.sh /tmp/ap-validation --queries --write-examples
```

This replays 24 policies with checkpoints and 24 without them, then seven recovery
scenarios with checkpoints and six without. R3 specifically requires an explicit
checkpoint and has no implicit replay. The query replay checks all five specialized
examples against trusted live observation queries, and policy replay checks that
all nine helper examples are executed. Policies must have no rejected actions or
checkpoint failures and must match or exceed their recorded CaP scores. Recovery
scenarios must reach the intended trigger and recovery scope, return normally,
and meet the CaP score threshold. A passing replay does not imply SR = 1: several
reference tasks have partial scores. Results and problems are written to
`validation-report.json`. Use `--policy-tasks put_papers_in_the_folder`,
`--policies none`, `--scenarios R1 H1`, or `--scenario-placements implicit` to
narrow a run. The all-helper coverage requirement applies to full policy runs.
`--write-examples` updates
captured headers from passing `both` runs only.

Run artifacts retain the shared `configuration.json`, `task-accounting.json`,
`results.json` and per-task generation, execution, observations and state files.
AP additionally writes `recoveries.json`, continuation policies named
`policy.replan-N.py`, and helper versions in recovery and dependency events. Accounting includes placement,
checkpoints placed in generated source versions, reached, passed on first check and
recovered locally, failures by trigger, recovery attempts and successes by scope,
replan and helper-regeneration counts, and termination cause. Generation records
identify the model-request purpose. Final SR and PSR use the shared scorer;
returning normally establishes execution completion only.

The parent saves `first_failure_state.json` and `first_exception_state.json` when
those events occur, including the same derived physical-effect labels as final
evaluation. These trusted graphs never enter model prompts. Accounting reports
`without_recovery` and `without_exception_recovery` PSR/SR using the shared
changed-condition scoring definition. When the corresponding event never occurs,
the counterfactual uses the actual final state. Unavailable states have no score.
The static benchmark has no injected perturbations. Report budgets and feedback
differences alongside experimental results.

Offline checks use `python -m unittest discover -s tests` with the repository's
Python paths. They exercise spawned workers, checkpoint behavior, escalation,
placement-specific prompts and examples, configurations, and the unchanged CaP
regression fixture with deterministic providers.

For a small live training diagnostic, run this under the shared simulator launcher:

```bash
python helper-scripts/dev_ap.py --output "$JOB_OUTPUT_DIR/dev"
```

It contacts the configured model for `put_apple_in_fridge` under all three placement
settings, excluding that task's examples. `--task` and `--placements` can narrow or
change the diagnostic. Each condition retains the full task artifacts and a
`dev-report.json` summarizes scores, request counts, triggers and counterfactuals.
This is a smoke check, not a held-out benchmark or a cluster deployment.
