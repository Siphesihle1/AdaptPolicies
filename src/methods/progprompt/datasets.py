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
