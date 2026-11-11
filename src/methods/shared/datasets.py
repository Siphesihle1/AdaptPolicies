from typing import Literal, get_args

Dataset = Literal[
    "train", "test_unseen", "test_seen", "test_unseen_ambiguous_goals", "env1", "env2"
]


def validate_dataset(env_id: int, test_set: Dataset):
    if env_id not in (0, 1, 2):
        raise ValueError(f"Unsupported environment {env_id}; expected 0, 1, or 2")
    if test_set not in get_args(Dataset):
        raise ValueError(f"Unknown test set {test_set!r}")
    expected_env = int(test_set[-1]) if test_set in ("env1", "env2") else 0
    if env_id != expected_env:
        raise ValueError(f"Test set {test_set!r} requires --env-id {expected_env}")

import os
import re
import json
from typing import List
from pathlib import Path

def load_tasks_from_file(file_path: str) -> List[str]:
    with open(file_path, "r") as f:
        return [next(iter(task)) for task in json.load(f)]


def load_tasks_from_dir(dir_path: str) -> List[str]:
    tasks: List[str] = []

    def sort_key(filename: str) -> int:
        match = re.search(r"\d+", filename)
        return int(match.group()) if match else -1

    for file in sorted(os.listdir(dir_path), key=sort_key):
        tasks.extend(load_tasks_from_file(os.path.join(dir_path, file)))
    return tasks


def dataset_root():
    return Path(os.environ.get("ADAPT_DATASET_DIR") or os.environ["PROGPROMPT_DATASET_DIR"])

def load_tasks(env_id, dataset, num_tasks=None):
    validate_dataset(env_id, dataset)
    root = dataset_root()
    tasks = (load_tasks_from_dir(str(root / dataset)) if env_id == 0 else
             load_tasks_from_file(str(root / "new_env" / f"env{env_id}_annotated.json")))
    return tasks[:num_tasks] if num_tasks else tasks
