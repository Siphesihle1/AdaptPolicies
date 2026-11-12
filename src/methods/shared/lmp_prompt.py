"""Prompt building blocks shared by the LMP methods.

Each method keeps its own instruction, rule, API and output-format text and
assembles it with these helpers: XML sections with escaped content, the
environment section with an internally validated observation, external example
files and the ProgPrompt-compatible selection of policy examples.
"""

import json
from collections import Counter
from xml.sax.saxutils import escape


def section(name, content):
    return f"<{name}>\n{escape(content)}\n</{name}>"


def environment_section(episode_id, inventory=(), context=None):
    """Known object classes, room names and, when given, the current observation."""
    classes = inventory.get("object_classes", []) if isinstance(inventory, dict) else list(inventory)
    rooms = inventory.get("room_names", []) if isinstance(inventory, dict) else []
    environment = [section("objects", json.dumps(classes)), section("rooms", json.dumps(rooms))]
    if context is not None:
        if context["episode_id"] != episode_id or "observation_revision" not in context:
            raise ValueError("Unscoped observation context")
        environment.append(section("observation", observation_text(context)))
    return "<environment>\n" + "\n".join(environment) + "\n</environment>"


def observation_text(context):
    observation = context.get("observation")
    if observation is None:
        # Minimal contexts remain useful for embedding and offline sessions.
        counts = Counter(obj.name for obj in context["visible_objects"])
        observation = {"current_room": None,
                       "visible_objects": [name + (f" ({count})" if count > 1 else "")
                                           for name, count in sorted(counts.items())],
                       "relations": [], "held_objects": []}
    return (f"Current room: {observation['current_room'] or 'unknown'}\n"
            + "You see: " + ", ".join(observation["visible_objects"]) + "\n"
            + "Relations: " + ", ".join(observation["relations"]) + "\n"
            + "You hold: " + (", ".join(observation["held_objects"]) or "nothing"))


def read_examples(path, exclude_tasks=()):
    """A mapping of training identity to code, or a list of request rows."""
    examples = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(examples, dict):
        return {task: code for task, code in examples.items() if task not in exclude_tasks}
    return [row for row in examples if row.get("task") not in exclude_tasks]


def render_request_examples(rows):
    return "\n\n".join(f"# request: {row['request']}\n{row['code']}" for row in rows)


def select_policy_examples(examples, example_type="default", number=3, seed=42, *, task_names=None,
                           exclude_tasks=(), label="LMP"):
    """Select policy examples with ProgPrompt's identities and seed policy."""
    import random
    from methods.progprompt.constants import DEFAULT_EXAMPLES

    if not 1 <= number <= 6:
        raise ValueError("examples_num must be between 1 and 6")
    if task_names is not None:
        if example_type != "default" or len(set(task_names)) != len(task_names):
            raise ValueError("Explicit example identities require default selection and no duplicates")
        keys = [task for task in task_names if task not in exclude_tasks]
    elif example_type == "random":
        from methods.shared.datasets import dataset_root
        data = json.loads((dataset_root() / "pythonic_plans" / "train_complete_plan_set.json").read_text())
        keys = random.Random(seed).sample([name for entry in data for name in entry if name not in exclude_tasks], number)
    elif example_type == "default":
        keys = [task for task in DEFAULT_EXAMPLES if task not in exclude_tasks]
    else:
        raise ValueError("Unknown example selection")
    if any(key not in examples for key in keys):
        raise ValueError(f"Selected training identity has no {label} representation")
    if (exclude_tasks or task_names is not None) and len(keys) < number:
        raise ValueError("Not enough examples after task exclusions")
    keys = keys[:number]
    return "\n\n".join(f"# task: {key}\n{examples[key]}" for key in keys)
