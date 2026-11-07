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
named references. The Python suite contains 99 passing tests.

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
