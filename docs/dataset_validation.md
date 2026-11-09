# Dataset validation

The current annotated datasets execute successfully with the custom simulator
and AdaptPolicies symbolic runtime. Validation covers all six datasets:

| Dataset | Tasks | Actions |
| --- | ---: | ---: |
| train | 24 | 173 |
| test_seen | 10 | 84 |
| test_unseen | 10 | 78 |
| test_unseen_ambiguous_goals | 5 | 88 |
| env1 | 10 | 60 |
| env2 | 10 | 51 |
| Total | 69 | 534 |

Every annotated action passes native Unity execution and symbolic checks.
Every task scores PSR, strict SR, Precision and Exec equal to 1 under the current
named references. The Python suite contains 137 passing tests.

## Protocol

Each task resets its matching scene, adds Male2 in the kitchen and captures its
own initial graph. Native responses, symbolic results, intermediate graphs and
final reference scores are checked action by action. The full replay uses fast
execution and reuses its players across tasks. Initial scene identity and
structural relations are compared with the original player; static FACING is
consistent within each scene.

Additional door controls check actual leaf rotation and stability, held-bin
attachment, individual and whole-script graph consistency, animated Close, repeated fast and animated Close/Open cycles, and
rejection of reopening with both hands full. These controls are separate from the 69 annotated
tasks; animated controls do not imply a fully animated or video-validated dataset.

## Scope

These results establish feasibility of the stored annotations in the specified
custom simulator/runtime setting. They do not measure an LLM or guarantee that a
generated plan, alternative object instance or stock VirtualHome build succeeds.
Use a matching simulator build and dataset revision for comparisons.

The [simulator documentation](simulator.md) describes included changes and
limitations. [Ground-truth evaluation](ground_truth_graphs.md) describes named
reference selection, derived states and scoring. The
[mapping audit](ground_truth_graph_mapping_audit.md) describes task/reference
associations. Original datasets are preserved in the separate
[archive](../src/methods/progprompt/data_original/README.md).

## Accessible closet state validation

The native metadata correction was verified across scenes 0, 1 and 2: all five
closets without an opening control report OPEN after reset and graph refresh.
Other objects retain their original states and properties. Twelve native
pickup/placement actions pass without opening closets 112, 127 and 374.
Metadata policy controls preserve closets with an Open control and non-closet
container states.

The full replay after aligning active reference metadata passes all 69 tasks and
534 actions, with PSR, SR, Precision and Exec equal to 1 for every task. Evidence
is retained in `outputs/local/closet_open_full_replay_001/` and
`outputs/local/closet_open_validation_001/`. The helper assembly SHA-256 is
`81af1cebdbeae70cf8a3b42b957bd9266adc58aed8bab1ef45b8d31064d79b30`.
Historical initial snapshots and the original dataset archive remain unchanged.

## Prompt example validation

All 24 active Python-like examples compile and pass live Unity execution with
local Qwen3.5-9B assertion checks. After repairs and targeted reruns, every current
example scores SR, PSR, Exec and Precision equal to 1. This validates stored
examples; it does not measure new plan generation or replace formal experiment
repeats. The consolidated report verifies each exact current plan against its
successful replay in `outputs/local/example_plan_restored_steps_validation_summary.json`.

Cleanup preserves every original numbered step, its wording and order, including
empty placeholders, and retains the detailed assertion/recovery structure.
Only duplicate actions and actions requiring validity corrections are changed.
Room context resolves the intended
items; the trash example carries the bin to the kitchen doorway. The computer
example uses the exposed native Touch action. Assertion prompts retain explicit
possession facts for every queried held item, including the second held object.
Visible state facts use the exact visible, nearby node IDs; hidden objects with
the same class name cannot inject contradictory states into an assertion.
Contents of bookshelves without an opening control remain visible. Closed
ancestors that have opening controls hide their contents, including nested items.
Two isolated stale reference edges are documented in
[ground-truth evaluation](ground_truth_graphs.md).

Washer controls verify loading piles 397, 407 and 286, and rejection with a closed
door or a non-clothing payload. Other clothes-pile prefabs use the existing mesh,
drum-fit and collision checks without changing their geometry. Control evidence
is in `outputs/local/washer_clothing_fit_controls_001/`; the installed helper
SHA-256 is `f173884989d654b944fc2017b7e125b7d1de3b3491c3f921f66b32bfcbf73b1f`.
