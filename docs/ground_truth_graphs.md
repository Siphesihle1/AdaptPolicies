# Task-to-ground_truth_graph mapping

Evaluation selects a ground_truth_graph by task name. Names use the same
space-to-underscore conversion as generated task functions. This conversion
does not lowercase names or collapse repeated whitespace; split deduplication
uses its own broader name matching.

## Dataset format and mapping coverage

The active dataset is `src/methods/progprompt/data/`. Task annotations, plan
collections, and world-graph collections are formatted JSON arrays. Load each
file with `json.load()`. The action vocabulary is an array of strings, while
mapping manifests are JSON objects.

Each dataset requires a manifest at
`data/ground_truth_graph_mappings/<dataset>.json`. For example:

```json
{
  "listen_to_radio": 6,
  "wash_mug": 10
}
```

This is an excerpt, not a complete manifest. Each value is a zero-based index
in the array `data/final_states/final_states_<dataset>.json`. Keep existing
indices stable when appending graphs. Reordering graph records requires
updating their mappings.

All six current datasets have audited mappings: train (24 tasks), test_seen
(10), test_unseen (10), test_unseen_ambiguous_goals (5), env1 (10), and env2 (10).
The 69 assignments identify references using annotated IDs, states, placements,
held objects, and proximity. They do not establish that every reference fully
captures its task or that every annotation can execute in Unity.

Training retains 34 graphs after task deduplication; ten are unassigned.
Test_seen contains 11 graphs for ten tasks; the unrelated book graph at index 5
is unassigned. See the [mapping audit](ground_truth_graph_mapping_audit.md)
for the complete index coverage, evidence, and unresolved issues, and the
[dataset README](../src/methods/progprompt/data/README.md) for split counts.

## Validation and evaluation

The agent loads task names and validates the complete selected dataset mapping
before constructing PromptBuilder, which connects to the simulator. A run that
selects only a few tasks still requires coverage of the complete dataset.
Validation rejects:

- Duplicate normalized task names or duplicate JSON mapping keys.
- Missing mappings, missing tasks, or unknown mapping tasks.
- Non-integer or out-of-range graph indices, including booleans.
- Selected graph entries without node and edge lists.

There is no positional fallback. Task order, mapping order, a selected subset,
or an earlier failed task cannot assign another task a different reference.
Evaluation uses the task's named graph; PSR, strict SR, and Precision formulas
are unchanged. The evaluator compares class-name relation/state sets rather
than object IDs, bounding boxes, or node properties. Mapping validation is
structural and does not prove goal completeness or simulator feasibility.

All CLI options are mandatory except that scenes 1 and 2 may omit `--test-set`
to select env1 and env2, respectively. Explicit `--test-set env1 --env-id 1`
and `--test-set env2 --env-id 2` are also supported. Scene 0 requires an explicit
train/test split. The ambiguous-goal
choice is `test_unseen_ambiguous_goals`, matching its directory.
See [dataset selection](dataset_selection.md) for supported commands and cluster
launcher behavior. The scene ID is always required.

## Validated repairs and reference versions

Test_seen wash_mug uses graph 10 from the successful replay of the current
11-step annotation, preserving all 22 action positions, duplicate finds, and
empty steps. All 22 actions passed Unity and the symbolic executor. Mug 447,
liquid 267, and sponge 266 end ON sink 247, neither faucet is ON, and the mug
is not held. WASHED is derived by the runtime sink rule using the supplied
partial graph; it was not manually inserted and is not a native Unity state.
The rule can also mark eligible liquid/sponge nodes WASHED.

Replay evidence is in
`outputs/local/ground_truth_graph_candidates/wash_mug_current_review_20261102T235812Z/`.
The accepted graph's SHA-256 is
`397f529c50170e0badb3354db3f887be6a85df77ad40b64629f410d04c398962`.

Test_seen cutlery graph 1 preserves the original graph from commit
`69ad21bb021419feb32ab0dc5ab9366971b7719c`, changing only knife 280 and fork 272's
relations to sink 247 from INSIDE to ON. The unchanged eight-action annotation
passed Unity and the symbolic executor. The complete runtime graph remains in
`outputs/local/ground_truth_graph_candidates/sink_goal_repair_20261103T011347Z/`
as evidence. Its seven unrelated FACING edges and metadata differences were
excluded from the reference; all other current test_seen graphs are preserved.

The [original dataset archive](../src/methods/progprompt/data_original/README.md)
contains all 35 original JSON files from that commit outside active dataset
scans. Formatting and documented collection-representation conversions preserve
original contents and order. It includes the original split overlaps, Python
example pool, sink annotations, and graph records.

Corrected sink goals revise the benchmark's formal success conditions. Offline
rescoring of the same correctly paired cutlery replay gives PSR 0.75 and SR 0
against the original reference, and PSR 1 and SR 1 against the narrow correction;
Precision is 1 in both cases. This is reference-version sensitivity, not improved
LLM performance. Identify dataset versions and rescore or rerun compared systems
consistently. The original-data archive alone does not restore historical code.

Frying-pan/plate placement failures, incomplete ambiguous-goal references, and
the candle annotation's bathroom shelf remain unresolved. Their mappings do not
repair those goals. Details and evidence are in the mapping audit.

Regression checks cover all six manifests, order independence, single-task
evaluation, earlier failures, and validation before simulator construction.
Run the suite in the existing configured environment with
`python -m unittest discover -s tests -v`; no simulator is needed for these checks.
