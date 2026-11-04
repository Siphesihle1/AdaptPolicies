# Original dataset archive

Source commit: `69ad21bb021419feb32ab0dc5ab9366971b7719c`.
Source directory: `src/methods/progprompt/data/`.

These 35 JSON files preserve the datasets before the dataset edits, including
the original 34 training tasks, 34 Python training examples, 10 test_seen graphs,
split overlaps, original sink putin actions, and all action vocabulary strings.
No current repaired graphs, mapping manifests, or deduplication changes are included.

Representation changes only: JSONL records become a single JSON array in original
record order. Task/plan dictionaries (`all_plans_env0` and the Python training
example pool) become arrays of one-task objects in original key order. Existing
arrays, including the action vocabulary, retain their contents and order.
JSON uses two-space indentation and a final newline. Names, plan strings,
annotations, graph metadata, and relations retain their original values.

This sibling archive is outside active `data/` scans and is not selected by the
runner or copied with the active dataset directory. Pointing current loaders at
it does not recreate the historical evaluator or default Python examples.
Use the source commit for a full historical code-and-data experiment.
The active dataset has revised sink goals and deduplicated splits; comparisons
must identify their dataset version and rescore or rerun systems consistently.
