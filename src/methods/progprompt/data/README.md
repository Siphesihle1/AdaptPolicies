Dataset collections use a single JSON array of objects per file.

- Task annotations contain one object per task: `[{"wash mug": {"0: find mug": [...]}}]`.
- Plan collections contain one object per task: `[{"task_name": "plan text"}]`.
- Initial and final world graphs contain one graph per array entry: `[{"nodes": [...], "edges": [...]}]`. Array order defines graph indices and must be preserved.

Load these files with `json.load()`, rather than parsing each line. Task files are read in numeric filename order, preserving the order of tasks within each file. Prompt examples are assembled into a name-to-plan dictionary after loading their array.

The action vocabulary in `zero_shot_baseline_data` is already a valid JSON array of strings. Ground-truth mapping manifests, when present, are JSON objects mapping task names to graph indices.
