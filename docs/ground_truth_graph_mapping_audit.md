# Task-to-graph mapping audit

Each manifest in `src/methods/progprompt/data/ground_truth_graph_mappings/` maps a
task function name to a stable zero-based reference graph index. Task-name
normalization replaces spaces with underscores.

| Dataset | Mapped tasks | Stored graphs | Unassigned indices |
| --- | ---: | ---: | --- |
| train | 24 | 34 | 2,15â€“19,26â€“29 |
| test_seen | 10 | 11 | 5 |
| test_unseen | 10 | 10 | None |
| test_unseen_ambiguous_goals | 5 | 5 | None |
| env1 | 10 | 10 | None |
| env2 | 10 | 10 | None |

Associations use annotated IDs, terminal states, placements, held objects and
task-specific proximity. Graph position alone is insufficient. Dinner and
breakfast references are distinguished by salmon versus cereal movement and
their plate instances. Env2 coffee uses the reference holding coffeepot170;
toast has a different food/appliance goal despite shared background conditions.

## Corrected reference semantics

- Sink tasks use supported ON placement. Cutlery graph 1 changes only knife280
  and fork272 INSIDEâ†’ON sink247 from the original graph. Wash_mug graph 10 retains
  its validated mug447, liquid267 and sponge266 sink goals.
- Plate washing selects feasible plate199 and kitchen faucet248 while restoring
  unused plate193. Frying-pan washing uses the original pan's supported release
  pose. Washing states come from runtime execution rules.
- Radio playback uses the stationary radio's native power action. Reading uses
  a held book with the lamp rather than an unsupported book Open. Phone use is
  native Talk on the held cellphone, followed by return to its original table.
- Salmon/toast goals use supported heating relations and runtime HEATED effects.
  Slippers use the accessible instance while preserving the bed destination.
- The living-room candle uses a living-room shelf. Four-fruit collection keeps
  all four fruits on a feasible stationary bowl. Breakfast stages its plate on
  the destination table before adding cereal, preserving the nested support.
- Closet placement uses native accessible interiors while retaining reported
  CLOSED states. Prompt examples follow the accepted action sequences.
- Trash completion is carrying the empty bin to the kitchen doorway. Door Close
  is an additional simulator control, outside that annotation's goal.
- Washer/rug and toothpaste/brush goals use the documented articulated assets,
  Fold/Unfold and generic Apply/Use actions.
- Moved-object room relations and selected incidental background orientation/
  proximity facts are corrected only where replay establishes the mismatch.
  Unrelated metadata, indices and reference records are preserved; FACING is not
  globally removed from evaluation.

The [original dataset archive](../src/methods/progprompt/data_original/README.md)
preserves the pre-edit records. These goal and affordance revisions define a
different benchmark version and require consistent comparison reruns/rescoring.
See [evaluation semantics](ground_truth_graphs.md),
[simulator changes](simulator.md) and [dataset validation](dataset_validation.md).
