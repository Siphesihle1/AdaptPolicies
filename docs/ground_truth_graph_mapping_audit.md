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

Plate repair: test_unseen `wash_the_plate` uses the existing smaller plate 199 and kitchen faucet 248, retaining all 18 action positions, duplicate finds, empty subtasks, and ordering. The full unchanged-scene candidate passed all Unity and symbolic actions; native final graphs confirm plate 199 and liquid 267 ON sink 247 and both faucets OFF. The existing runtime rule derives WASHED for both objects from the supplied partial graph.

Reference graph 7 retains its original node metadata, property ordering, edge ordering, and unrelated relations. Nine task-related edge substitutions restore unselected plate 193 ON desk 108, move plate 199 and the liquid onto the kitchen sink, and update the character's room and proximity for the kitchen faucet. WASHED on 199/267 is copied from the successful runtime result; no state was injected into execution. No full runtime graph replacement or unrelated FACING edits are included. The mapping index and all other stored graph/annotation records are unchanged. Evidence, exact annotation diff and minimal-reference changes are under `outputs/local/change12_orientation_trials_20261105T120632Z/plate199_candidate/test_unseen/wash_the_plate/`. This changes the target instance and formal goal conditions: report the dataset revision and rescore or rerun compared systems consistently.

Known issues requiring separate review:

- Train `wash_the_frying_pan` graph 13 still contains its old INSIDE-sink placements. The Unity build rejects the original pan 269 ON sink 247. Placement becomes possible after a temporary object resize, which changes the environment and is not an accepted benchmark repair. The pan annotation/reference are unchanged; no validated unmodified-scene washing repair is claimed.
- Some ambiguous-goal references lack annotated food-to-plate or fruit-to-bowl relations. For example, dinner graph 0 does not contain salmon 327 INSIDE plate 285, and breakfast graph 1 does not contain bread 310 INSIDE plate 278. These pre-existing goal-content issues remain explicit follow-ups; mappings do not imply they have been repaired.
- The candle task's annotated shelf 43 is in the bathroom, despite its task name saying living room. The mapping follows the current annotation.

Evidence is under `outputs/local/ground_truth_graph_mapping_audit/` and `outputs/local/ground_truth_graph_candidates/sink_goal_repair_20261103T011347Z/`. Only cutlery was successfully replayed in that repair batch; no full replay claim is made for all mapped tasks.

The agent validates complete dataset mappings before simulator construction and selects ground-truth graphs by task name. All CLI options are mandatory except that scenes 1 and 2 may omit `--test-set` to select env1 and env2. Explicit `--test-set env1` / `env2` selections require `--env-id 1` / `2`, respectively; scene 0 requires an explicit train/test split. See [dataset selection](dataset_selection.md) for supported commands.

### Native repair: listen_to_radio

Radio playback uses switchon on the stationary radio176; the rejected grab is removed. Reference6 removes only the unsupported character HOLDS_RH radio176 edge. Its ON goal, all node metadata, and every other relation/record are preserved. Three actions passed both engines in the unchanged scene.

Evidence: `outputs/local/candidate_native_repairs_20261105T132712Z/radio_stationary/test_seen/listen_to_radio/`. This revises the benchmark reference; rescore compared systems consistently. The original-data archive and all mapping indices are unchanged.

### Native repair: read_book_under_table_lamp

Reading uses native read on held book434 without the unsupported open action. Reference25 keeps that book CLOSED and corrects its carried room from livingroom335 to bedroom73, where tablelamp103 is located. All other metadata/relations/records are preserved. Five actions, including native read under the lamp, passed both engines in the unchanged scene.

Evidence: `outputs/local/candidate_native_repairs_20261105T132712Z/read_book_directly/train/read_book_under_table_lamp/`. This revises the benchmark reference; rescore compared systems consistently. The original-data archive and all mapping indices are unchanged.

### Completed-trajectory reference corrections (change16)

- `train/refrigerate_the_salmon` (index30): Only newly introduced kitchen-prop FACING clock265 edges absent from both task initialization and replay are removed. These tasks move salmon/chips, not the unrelated book/table settings; reference-only orientation artifacts are not intended outcomes. Other FACING edges and all other records remain intact. Removed 7 edges; added 0.
- `test_seen/cut_apple` (index9): Knife271 remains held while walking from livingroom to kitchen to cut apple438. Its livingroom containment was stale; the corrected kitchen relation agrees with both native and symbolic final graphs. Removed 1 edges; added 1.
- `test_unseen/eat_chips_on_the_sofa` (index5): Only newly introduced kitchen-prop FACING clock265 edges absent from both task initialization and replay are removed. These tasks move salmon/chips, not the unrelated book/table settings; reference-only orientation artifacts are not intended outcomes. Other FACING edges and all other records remain intact. Removed 5 edges; added 0.
- `test_unseen/microwave_salmon` (index9): Only newly introduced actor CLOSE edges absent from symbolic replay are removed. Proximity to neighboring props is an incidental historical capture detail, not heating salmon or operating the coffeemaker. Intended appliance proximity, appliance/food states, placements, initial proximity conditions and every other relation remain unchanged. Native proximity may be broader than symbolic Find; evaluator formulas are unchanged. Removed 62 edges; added 0.
- `env2/make_coffee_in_coffeemaker` (index8): Only newly introduced actor CLOSE edges absent from symbolic replay are removed. Proximity to neighboring props is an incidental historical capture detail, not heating salmon or operating the coffeemaker. Intended appliance proximity, appliance/food states, placements, initial proximity conditions and every other relation remain unchanged. Native proximity may be broader than symbolic Find; evaluator formulas are unchanged. Removed 28 edges; added 0.

Evidence and exact edge audit: `outputs/local/reference16_minimal_corrections/changes.json`, using complete native/symbolic trajectories from `outputs/local/full_unity_replay_20261105T094658Z/`. Node metadata/states, unaffected edge order, all other graphs, mappings, annotations, wash-mug10, cutlery1 and the original archive are preserved. These are reference-version corrections, not evidence of better LLM performance; rescore compared systems consistently.

### Native food repair: cooking

Dinner and breakfast stage the pan on the stove before loading food and stage the plate on the kitchen table before serving. This avoids held-container placement rejection and native detachment when grabbing loaded plates. Both full trajectories pass; native final food ON plate ON table and derived HEATED are verified. References0/1 gain the missing salmon327 ON plate285 / bread310 ON plate278 and each food's replay-derived HEATED. Breakfast bread's stale bathroom11 room is corrected to kitchen205. No other node metadata or relations change.

Evidence and exact reference changes: `outputs/local/promoted_cooking_candidates/changes.json`; successful replay paths are recorded there. No mapping indices or original-archive files changed. Revised goal conditions and augmentation require consistent benchmark-version reporting and rescoring.
