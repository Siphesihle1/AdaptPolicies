import json
import os
from pathlib import Path
from typing import Any, Iterable


def normalize_task_name(task: str) -> str:
    return "_".join(task.split(" "))


def _mapping_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    mapping = {}
    for task, index in pairs:
        if task in mapping:
            raise ValueError(f"Duplicate ground_truth_graph mapping for task '{task}'")
        mapping[task] = index
    return mapping


def load_ground_truth_graphs(
    dataset: str,
    task_names: Iterable[str],
    dataset_dir: Path | None = None,
) -> dict[str, dict[str, Any]]:
    root = (
        dataset_dir
        if dataset_dir is not None
        else Path(os.environ["PROGPROMPT_DATASET_DIR"])
    )
    tasks = [normalize_task_name(task) for task in task_names]
    if len(tasks) != len(set(tasks)):
        raise ValueError(f"Duplicate task names in dataset '{dataset}'")

    mapping_path = root / "ground_truth_graph_mappings" / f"{dataset}.json"
    if not mapping_path.is_file():
        raise ValueError(
            f"Missing ground_truth_graph mapping for dataset '{dataset}': {mapping_path}. "
            "An audited task-to-graph mapping is required before evaluation."
        )
    with mapping_path.open() as stream:
        mapping = json.load(stream, object_pairs_hook=_mapping_without_duplicates)
    if not isinstance(mapping, dict):
        raise ValueError(
            f"ground_truth_graph mapping must be a JSON object: {mapping_path}"
        )
    missing = set(tasks) - set(mapping)
    unexpected = set(mapping) - set(tasks)
    if missing or unexpected:
        raise ValueError(
            f"ground_truth_graph mapping does not match dataset '{dataset}': "
            f"missing tasks={sorted(missing)}, unexpected tasks={sorted(unexpected)}"
        )

    graph_path = root / "final_states" / f"final_states_{dataset}.json"
    with graph_path.open() as stream:
        ground_truth_graphs = json.load(stream)

    result = {}
    for task, index in mapping.items():
        if type(index) is not int or not 0 <= index < len(ground_truth_graphs):
            raise ValueError(
                f"Invalid ground_truth_graph index {index!r} for task '{task}' "
                f"in {mapping_path}; expected an integer from 0 to {len(ground_truth_graphs) - 1}"
            )
        ground_truth_graph = ground_truth_graphs[index]
        if (
            not isinstance(ground_truth_graph, dict)
            or not isinstance(ground_truth_graph.get("nodes"), list)
            or not isinstance(ground_truth_graph.get("edges"), list)
        ):
            raise ValueError(
                f"Invalid ground_truth_graph {index} for task '{task}' in {graph_path}"
            )
        result[task] = ground_truth_graph
    return result
