Dataset collections use a single JSON array of objects per file.

- Task annotations contain one object per task: `[{"wash mug": {"0: find mug": [...]}}]`.
- Plan collections contain one object per task: `[{"task_name": "plan text"}]`.
- Initial and final world graphs contain one graph per array entry: `[{"nodes": [...], "edges": [...]}]`. Array order defines graph indices and must be preserved.

Load these files with `json.load()`, rather than parsing each line. Task files are read in numeric filename order, preserving the order of tasks within each file. Prompt examples are assembled into a name-to-plan dictionary after loading their array.

The action vocabulary in `zero_shot_baseline_data` is already a valid JSON array of strings. Ground-truth mapping manifests, when present, are JSON objects mapping task names to graph indices.

Mapping manifests now cover train, test_seen, test_unseen, test_unseen_ambiguous_goals, env1, and env2. Their values refer to stable zero-based indices; unused graphs are retained. See [the mapping audit](../../../../docs/ground_truth_graph_mapping_audit.md) for assignment evidence and unresolved graph/annotation issues. The agent validates these mappings before simulator construction and selects ground-truth graphs by task name.

Task names are unique across the four train/test splits. Matching ignores case, underscores versus spaces, and repeated whitespace. Test assignments take precedence over training assignments. Training prompt examples and default examples contain training tasks only. The separate env1/env2 evaluations are excluded from this uniqueness rule.

| Category | Before deduplication | After deduplication |
| --- | ---: | ---: |
| train | 34 | 24 |
| test_seen | 10 | 10 |
| test_unseen | 10 | 10 |
| test_unseen_ambiguous_goals | 5 | 5 |
| Total task entries | 59 | 49 |

All ten test_seen tasks were removed from training, including wash mug. Their training prompt examples were also removed (34 → 24). Default examples now start with refrigerate_the_salmon, bring_me_some_fruit, and wash_clothes. Empty training shards remain valid empty JSON arrays. Unlabelled graph arrays retain their existing order and indices; their entries are not counts of the revised training split. The all_plans_env0 collection is a source-plan archive, not a train/test assignment or the prompt-example pool.

The [original dataset archive](../data_original/README.md) preserves all 35 JSON files from commit `69ad21bb021419feb32ab0dc5ab9366971b7719c` with formatting/representation changes only. It is outside active dataset scans. The active cutlery graph 1 preserves that original graph except for the two validated INSIDE-to-ON sink edges; the complete replay graph remains evidence.

See [ground-truth evaluation](../../../../docs/ground_truth_graphs.md) for mapping validation, task-name selection, replay provenance, and dataset-version reporting.
