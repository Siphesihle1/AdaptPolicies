# Code as Policies

CaP generates and directly executes Python `policy()` functions. Policies can branch,
loop, define helpers and call `parse_objects` / `parse_question`, which generate and
execute specialized programs assigning `ret_val`. Unresolved direct function calls
trigger depth-first helper generation. Generated code is never run through the
ProgPrompt parser, and notebooks are not executed.

Task input is the natural-language goal, such as `Open the fridge.` API hints,
few-shot examples and observation context describe the available interface. The
task does not prescribe function names, helper definitions, action order or LMP
calls. The model chooses its decomposition; a direct action program is valid.
Specialized LMPs and recursive helper generation run only if the policy uses them.
Evaluate the resulting state independently of the policy's return value.
The three default example policies demonstrate `parse_objects`, `parse_question`,
and calls to reusable helpers. The function-generation prompt demonstrates acquisition,
opening, and a placement helper that composes the opening helper. These definitions
are few-shot examples, not functions preloaded into the live execution namespace;
the model must generate or define any helper used by a new policy.

All four LMPs use XML sections: `<instructions>`, `<rules>`, `<api>`,
`<environment>`, `<examples>`, `<task>` (or `<request>` for nested programs), and
`<output-format>`. Environment data has separate `<objects>`, `<rooms>`, and optional
`<observation>` sections. Rules describe API use and execution constraints; the task
contains only the requested goal. Dynamic content is escaped to preserve section boundaries.
Rules encourage focused helpers with nested composition for complex functions, and
action ordering that satisfies preconditions before leaving a location and rechecks
visibility and state after movement.
Examples are loaded from `src/methods/cap/examples/*.json`, independently of the short
instruction templates in `prompts/`. Policy examples retain ProgPrompt's configured
default identities, count, or seeded random selection; nested LMPs load their own examples.

Install the repository's Python 3.10 environment and activate its existing environment
hooks. Point `ADAPT_DATASET_DIR` (or the compatible `PROGPROMPT_DATASET_DIR`) at
`src/methods/progprompt/data`. Set `JOB_OUTPUT_DIR`, `EXPERIMENT_NAME` and `SIM_PORT`
as for ProgPrompt. Use an explicit configuration path:

```bash
export ADAPT_CONFIG="$PROJECT_ROOT/config/cap.yml"
export ADAPT_DATASET_DIR="$PROJECT_ROOT/src/methods/progprompt/data"
export JOB_OUTPUT_DIR="$PROJECT_ROOT/outputs/cap-example"
bash helper-scripts/run_with_sim_and_ollama.sh helper-scripts/run-cap.sh \
  --expt-name cap-example --env-id 0 --test-set test_seen --num-tasks all \
  --examples-type default --examples-num 3
```

The shared launcher retains simulator readiness, port ownership, process-group cleanup
and provider setup. With an already managed simulator, run `python -m methods.cap.run_eval`
with the same arguments. Configuration is validated before connecting. The sample
`config/cap.yml` is for externally managed LM Studio; configure your chosen provider
and its native options explicitly. All four `cap_policy`, `cap_function`, `cap_objects`,
and `cap_question` profiles are required. Existing ProgPrompt configurations still use
`plan` and `assertion`. `cap` contains runtime limits, never provider parameters.
The local-model sample allows 300 seconds per request and 600 seconds per task;
the live smoke policy required about 128 seconds for generation. Adjust both budgets
explicitly for the serving speed and number of nested requests in your experiment.

The parent owns the live simulator and supervises a fresh spawned worker per task.
Queries/actions use a validated RPC registry. The task deadline covers generation,
helper resolution, specialized calls and execution, including CPU-only loops and
blocked providers. Helper count/depth, nested call depth, model requests, queries,
actions and source/output sizes are bounded separately. Provider requests have no
SDK retries. There is no automatic code repair or regeneration after failure.
The worker restricts Python capabilities and is disposable; it is not an OS sandbox
for adversarial Python and does not impose a platform-specific memory quota.

Queries return immutable `ObjectRef(episode_id, id, name)` values. State is queried
fresh; `None` means unknown and differs from an observed empty collection. Closed
containment chains remain hidden. Visible household objects exclude room and
character metadata. Rooms remain navigation metadata. Action results require explicit
`.status` comparisons: `succeeded`, `failed`, `skipped`. A reference preserves the exact
instance; strings keep the existing class resolver. References from another episode
are rejected, even when IDs repeat. Successful state updates advance observation
revision. Uncertain or interrupted native execution stops the run, leaves the final
state unavailable and requires simulator restart. A native call already in progress
cannot be safely cancelled; the owned launcher cleans up the simulator on exit.

Episode IDs and observation revisions remain in internal validation and generation
records, and are omitted from model-facing prompts. Prompt observations group visible
objects by class with occurrence counts. Generated programs
fetch actual references, states and possession through the same query APIs; instance
selection and observation access remain available at execution time. Queries alone
never make model calls. Specialized programs receive a fresh class-count summary,
and their results are validated against the full permitted observation retained by
the runtime. Helper/session state resets for each task.
Training examples use CaP representations of training identities, the established
default identities and random seed 42. No held-out plans or target states enter prompts.

Both methods disclose the global class inventory, including room navigation names.
Neither supplies a hidden instance map. CaP additionally permits explicit instance
selection: report this experimental difference. Both methods use the same dataset,
ground-truth mappings, task augmentation, action checks and class-based scoring.
`PSR`, `SR`, `Precision` and `Exec` retain existing definitions. Returning normally is
execution completion; it is not goal success. Failed and zero-action tasks remain in
headline denominators, with conditional metrics reported separately. Failed workers
are scored only when the parent's final state remains trustworthy.

Run artifacts include `configuration.json`, `task-accounting.json`, `results.json`
and `tasks/<task-id>/{policy.py,helpers.py,dependencies.json,generation.json,execution.json,
initial_state.json,final_state.json,chat.json}`. Unavailable final states are recorded
in accounting rather than fabricated. Generation records retain original failed
source and request purposes; execution records carry query/action outcomes, revision,
budgets and termination. Shared local chat exports and Weave task threads include
generation, queries, actions and image observations. Token usage is provider-reported;
unavailable usage remains unknown. Code validity, dependency resolution, model calls,
latency, action execution and goal scores are separate outcomes.

Offline verification uses `python -m unittest discover -s tests` with the repository
Python paths and an `ADAPT_CONFIG` file containing `weave: {enabled: false}`. The CaP
tests use deterministic providers, fake environments and actual spawned processes;
they require no paid requests or live experimental simulator runs.

Method references: [Code as Policies](https://arxiv.org/abs/2209.07753),
[upstream LMP and recursive helper implementation](https://github.com/google-research/google-research/tree/master/code_as_policies).
