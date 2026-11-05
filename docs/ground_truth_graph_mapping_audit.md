Task-to-graph manifests are stored in `src/methods/progprompt/data/ground_truth_graph_mappings/`. Each JSON object maps a task function name to a zero-based index in the corresponding `final_states/final_states_<dataset>.json` array. Task names retain the existing normalization of replacing spaces with underscores.

| Dataset | Tasks mapped | Stored graphs | Unassigned indices |
| --- | ---: | ---: | --- |
| train | 24 | 34 | 2, 15–19, 26–29 |
| test_seen | 10 | 11 | 5 |
| test_unseen | 10 | 10 | None |
| test_unseen_ambiguous_goals | 5 | 5 | None |
| env1 | 10 | 10 | None |
| env2 | 10 | 10 | None |

The assignments were checked against annotated object IDs, terminal object states, placements, held objects, and task-specific character proximity. Graph positions alone were not used to establish identity. Training keeps its original indices after task deduplication; graphs for removed tasks remain unassigned. The book graph at test_seen index 5 remains unassigned.

Some assignments need more than final-state equality to distinguish them. Ambiguous-goal dinner and breakfast graphs are identified by the annotated salmon versus bread movement and proximity to plates 285 versus 278. Env2 toast and coffee share several unchanged appliance conditions; toast uses graph 4, while coffee uses graph 8, where the character holds coffeepot 170. The audit establishes the association with an existing annotation, not that every historical graph fully captures the natural-language goal.

Cutlery repair: test_seen graph 1 retains the original graph from commit `69ad21bb021419feb32ab0dc5ab9366971b7719c` with only knife 280 and fork 272's relations to sink 247 changed from INSIDE to ON. All original node metadata, edge order, and unrelated relations are preserved. Both Unity and the symbolic executor passed the unchanged eight-action annotation; the complete runtime graph remains in the replay evidence, rather than replacing the reference graph. The other ten current graph entries, including wash_mug at index 10, are unchanged. No annotation was edited and no state was manually inserted.

The narrow correction excludes seven unrelated FACING edges from the runtime capture and retains the original 416 class-level preservation conditions (the complete capture had 420). Offline scoring of the same correctly paired replay changes PSR/SR from 0.75/0 to 1/1, with Precision 1 in both cases. This measures reference-version sensitivity, not improved LLM performance. Report the dataset revision and rescore or rerun compared systems consistently. The original datasets are archived in [`data_original`](../src/methods/progprompt/data_original/README.md).

Known issues requiring separate review:

- Train `wash_the_frying_pan` graph 13 and test_unseen `wash_the_plate` graph 7 still contain the old INSIDE-sink placements. Replaying their corrected annotations revealed that this Unity build rejects putting fryingpan 269 and plate 193 ON sink 247. The same placement works for the mug and cutlery. These two graphs were not replaced with a claimed successful result; their current annotations and graphs require a placement investigation before reliable evaluation.
- The plate-washing annotation switches bathroom faucet 50 while placing objects at kitchen sink 247. Its intended washing condition is therefore inconsistent independently of the placement failure.
- Some ambiguous-goal references lack annotated food-to-plate or fruit-to-bowl relations. For example, dinner graph 0 does not contain salmon 327 INSIDE plate 285, and breakfast graph 1 does not contain bread 310 INSIDE plate 278. These pre-existing goal-content issues remain explicit follow-ups; mappings do not imply they have been repaired.
- The candle task's annotated shelf 43 is in the bathroom, despite its task name saying living room. The mapping follows the current annotation.

Evidence is under `outputs/local/ground_truth_graph_mapping_audit/` and `outputs/local/ground_truth_graph_candidates/sink_goal_repair_20261103T011347Z/`. Only cutlery was successfully replayed in that repair batch; no full replay claim is made for all mapped tasks.

The agent validates complete dataset mappings before simulator construction and selects ground-truth graphs by task name. All CLI options are mandatory except that scenes 1 and 2 may omit `--test-set` to select env1 and env2. Explicit `--test-set env1` / `env2` selections require `--env-id 1` / `2`, respectively; scene 0 requires an explicit train/test split. See [dataset selection](dataset_selection.md) for supported commands.
