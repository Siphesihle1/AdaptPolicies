# Ground-truth graphs and evaluation

Evaluation selects a reference graph by task name. Names use the same
space-to-underscore conversion as generated task functions; this does not
lowercase names or collapse repeated whitespace. Split deduplication uses a
separate, broader name match.

## Dataset format and coverage

The active dataset is `src/methods/progprompt/data/`. Annotations, plans and world
graphs are JSON arrays read with `json.load()`. The action vocabulary is an array
of strings. A required manifest at
`ground_truth_graph_mappings/<dataset>.json` maps task names to zero-based indices
in `final_states/final_states_<dataset>.json`.

All six datasets have mappings: train 24, test_seen 10, test_unseen 10,
test_unseen_ambiguous_goals 5, env1 10 and env2 10. Graph array indices remain
stable when tasks are removed. Training retains 34 graphs with ten unassigned;
test_seen retains 11 graphs with the unrelated book graph at index 5 unassigned.
See the [mapping audit](ground_truth_graph_mapping_audit.md) for associations and
[dataset validation](dataset_validation.md) for execution results.

## Validation and scoring

The complete selected dataset is validated before simulator construction, even
when a run selects only a subset of tasks. Validation rejects duplicate task
names or mapping keys, missing/unknown tasks, non-integer or out-of-range indices
(including booleans), and graph entries without node and edge lists.

There is no positional fallback. Task order, mapping order and earlier failures
cannot select another task's reference. PSR, strict SR and Precision compare
class-name relation/state sets; IDs, bounding boxes and node properties are not
scored. Mapping validity alone does not prove goal completeness or executability.

Symbolic preconditions are checked before contacting Unity. Only confirmed
native success, including per-character execution messages, commits the candidate
symbolic state and increments executable steps. A native rejection or communication
exception blocks subsequent actions in that environment. Start a fresh task after
failure: Unity may have partially moved before rejecting an action, while the
symbolic state retains only confirmed actions.

## Initial-state provenance

Prompt construction and task execution capture runtime graphs separately.
Prompt initialization resets the explicit scene and reads its objects. Each task
creates a new `VHEnvironment`, resets that scene, adds Male2 in the kitchen and
retains a fresh graph as its evaluation baseline. Task completion returns copies
of that task's initial and final graphs.

`initial_states_env1.json` and `initial_states_env2.json` are historical snapshots,
not initialization inputs. Comparing them with runtime graphs requires the same
scene, character, room and capture stage; array position alone does not identify
a matching task. No saved initial graph is loaded into Unity during evaluation.

## Runtime effects and reference meaning

WASHED, HEATED and selected USED states are derived from confirmed actions and
observed object relations. Heating includes edible Props as well as Food: food
ON a pan on an active stove, or ON/INSIDE an active toaster, can acquire HEATED.
Off appliances, unrelated surfaces and inedible objects do not qualify. Repeated
observations retain a single state. Native and derived effects are distinguished
in the [simulator documentation](simulator.md).

Closets without a native opening control report OPEN, reflecting their accessible
interiors. Active final-state references use OPEN for the four verified static
closet prefabs. Historical initial snapshots and the original archive are retained
as captured. Closed fridges, cabinets and washers keep their access
checks. Talk requires a held phone and derives USED only after native success;
it neither powers nor releases the phone. Read also selects a held instance.

Reference corrections preserve graph indices and unrelated records. Cutlery
test_seen graph 1 retains the original graph except for knife280 and fork272
INSIDEâ†’ON sink247. Wash_mug graph 10 reflects the validated mug/liquid/sponge sink
placements and runtime-derived washing state. Complete runtime captures are
evidence and do not automatically replace references.

Train graph 21 (take_off_pictureframe) omits an invalid character CLOSE itself
edge. Train graph 9 (work_on_computer) omits character ON bedroom chair110:
the validated native trajectory ends standing at the keyboard, while the old
symbolic final graph retained that seated relation after standing and moving.
The remaining pickup, room, computer-power and desk/keyboard proximity goals
are preserved. These are isolated reference corrections, not scoring filters.

Some repaired task goals use feasible native ON relations, selected alternative
instances, or corrected moved-object room relations. Task-specific stale
background orientation/proximity goals were corrected without globally filtering
FACING or changing scoring formulas. Formal goal changes are dataset-version
changes, not evidence of improved model performance. Compared systems must use
matching versions or be rescored/rerun consistently.

The [original archive](../src/methods/progprompt/data_original/README.md) preserves
the pre-edit datasets separately from active scans. See
[dataset selection](dataset_selection.md) for required CLI arguments and matching
scene/split choices.
