"""XML prompts with external examples and internally validated observation context."""

import json
from collections import Counter
from pathlib import Path
from xml.sax.saxutils import escape
from .environment import ACTION_CLASSES

ROOT = Path(__file__).parent
PROMPTS = {"cap_policy": "policy", "cap_function": "function_gen",
           "cap_objects": "parse_objects", "cap_question": "parse_question"}
INSTRUCTIONS = {
    "cap_policy": "Write a Python policy to complete the task in VirtualHome.",
    "cap_function": "Implement the requested helper for its call site and originating program.",
    "cap_objects": "Write Python code selecting currently visible objects matching the description.",
    "cap_question": "Write Python code computing the answer from current observations.",
}
OUTPUT_FORMATS = {
    "cap_policy": "Define policy() with no arguments. Additional helper definitions are allowed. "
                  "Only function definitions are allowed at module scope.",
    "cap_function": "Return exactly one definition of the requested helper function.",
    "cap_objects": "Return Python statements assigning the resulting list of live ObjectRef values to ret_val.",
    "cap_question": "Return Python statements assigning the computed answer to ret_val.",
}

RULES = """- Use the available APIs for actions and observations; do not redefine them.
- Actions return ActionResult: check result.status explicitly ('succeeded', 'failed', or 'skipped'), never result truthiness. Helpers may return booleans; check them according to their return contract.
- Obtain object references through queries; never construct them or copy observation data into code.
- Query current states and relations when needed. None means unknown, not empty or false.
- Visibility does not establish proximity or action applicability.
- Use Python control flow and helpers where useful. Undefined helper calls trigger helper generation; avoid dependency cycles.
- Keep each helper focused on one responsibility. Decompose complex helpers into smaller helpers and compose them through nested calls.
- Order actions by their preconditions. Acquire objects before travelling somewhere they are needed. After movement, query current visibility and state before using unheld objects.
- Use parse_objects for object selection and parse_question for observation-based questions.
- Do not import modules, access private attributes, or perform external I/O."""

API = """Actions accept ObjectRef values or class-name strings and return ActionResult with status and error.
{actions}
grab(item): pick up the specified item.
open(container), close(container): change the container's open state; they do not pick it up.
putin(item, container): place a held item inside a different, accessible container. Open an openable container first.
putback(item, surface): place a held item onto the destination surface.
find(target), walk(destination), run(destination): navigate to a target; run is faster movement.
switchon(device), switchoff(device): activate or deactivate a compatible device.
apply(item, target): supports held toothpaste applied to a held toothbrush; the toothpaste cap must be open.
ObjectRef exposes id and name; a reference identifies an instance, not its current visibility, accessibility or state. Held objects remain available after movement.
Environment objects lists known class names; observation describes the current room, visible states and relations.
get_visible_objects() -> list[ObjectRef], excluding rooms and the character
get_object_states(ref) -> frozenset[str] or None
get_objects_in(ref), get_objects_on(ref) -> direct observed list[ObjectRef] or None when inaccessible
is_holding(ref) -> bool
get_current_room() -> room ObjectRef or None
parse_objects(description) -> list[ObjectRef], computed by generated query code
parse_question(question) -> answer, computed by generated query code
Allowed builtins: abs all any bool dict enumerate float frozenset int len list max min
range reversed round set sorted str sum tuple zip isinstance ValueError TypeError."""


def load_examples(purpose, exclude_tasks=()):
    examples = json.loads((ROOT / "examples" / f"{PROMPTS[purpose]}.json").read_text(encoding="utf-8"))
    if isinstance(examples, dict):
        return {task: code for task, code in examples.items() if task not in exclude_tasks}
    return [row for row in examples if row.get("task") not in exclude_tasks]


def section(name, content):
    return f"<{name}>\n{escape(content)}\n</{name}>"


def build_prompt(episode_id, purpose, query, context=None, examples="", inventory=(), exclude_tasks=()):
    template = INSTRUCTIONS[purpose]
    classes = inventory.get("object_classes", []) if isinstance(inventory, dict) else list(inventory)
    rooms = inventory.get("room_names", []) if isinstance(inventory, dict) else []
    rules = RULES
    if purpose in {"cap_objects", "cap_question"}:
        rules += "\n- Use queries only; do not perform actions."
    if purpose == "cap_question":
        rules += "\n- Return None for an answer that cannot currently be observed."
    parameters = {"putin": "item, container", "putback": "item, surface", "apply": "item, target",
                  "grab": "item", "open": "container", "close": "container",
                  "walk": "destination", "run": "destination", "find": "target", "standup": ""}
    actions = ", ".join(f"{name}({parameters.get(name, 'target')})" for name in ACTION_CLASSES)
    parts = [section("instructions", template), section("rules", rules),
             section("api", API.format(actions=actions))]
    environment = [section("objects", json.dumps(classes)), section("rooms", json.dumps(rooms))]
    if context is not None:
        if context["episode_id"] != episode_id or "observation_revision" not in context:
            raise ValueError("Unscoped observation context")
        observation = context.get("observation")
        if observation is None:
            # Minimal contexts remain useful for embedding and offline sessions.
            counts = Counter(obj.name for obj in context["visible_objects"])
            observation = {"current_room": None,
                           "visible_objects": [name + (f" ({count})" if count > 1 else "")
                                               for name, count in sorted(counts.items())],
                           "relations": [], "held_objects": []}
        text = (f"Current room: {observation['current_room'] or 'unknown'}\n"
                + "You see: " + ", ".join(observation["visible_objects"]) + "\n"
                + "Relations: " + ", ".join(observation["relations"]) + "\n"
                + "You hold: " + (", ".join(observation["held_objects"]) or "nothing"))
        environment.append(section("observation", text))
    parts.append("<environment>\n" + "\n".join(environment) + "\n</environment>")
    if purpose != "cap_policy":
        examples = "\n\n".join(f"# request: {row['request']}\n{row['code']}"
                               for row in load_examples(purpose, exclude_tasks))
    parts.append(section("examples", examples))
    parts.append(section("task" if purpose == "cap_policy" else "request", query))
    parts.append(section("output-format", OUTPUT_FORMATS[purpose] +
                         " Return Python code only, without Markdown fences or explanations."))
    return "\n\n".join(parts)


def select_examples(example_type="default", number=3, seed=42, *, task_names=None, exclude_tasks=()):
    """Select external CaP examples with ProgPrompt's identities and seed policy."""
    import random
    from methods.progprompt.constants import DEFAULT_EXAMPLES

    examples = load_examples("cap_policy", exclude_tasks)
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
        raise ValueError("Selected training identity has no CaP representation")
    if (exclude_tasks or task_names is not None) and len(keys) < number:
        raise ValueError("Not enough examples after task exclusions")
    keys = keys[:number]
    return "\n\n".join(f"# task: {key}\n{examples[key]}" for key in keys)
