"""XML prompts with external examples and internally validated observation context."""

import json
from collections import Counter
from pathlib import Path
from xml.sax.saxutils import escape
from .environment import ACTION_CLASSES

ROOT = Path(__file__).parent
PROMPTS = {"cap_policy": "policy", "cap_function": "function_gen",
           "cap_objects": "parse_objects", "cap_question": "parse_question"}
OUTPUT_FORMATS = {
    "cap_policy": "Define policy() with no arguments. Additional helper definitions are allowed. "
                  "Only function definitions are allowed at module scope.",
    "cap_function": "Return exactly one definition of the requested helper function.",
    "cap_objects": "Return Python statements assigning the resulting list of live ObjectRef values to ret_val.",
    "cap_question": "Return Python statements assigning the computed answer to ret_val.",
}

RULES = """- Use the available APIs for actions and observations; do not redefine them.
- Check action outcomes through result.status: 'succeeded', 'failed', or 'skipped'; never test result truthiness.
- Obtain object references through queries; never construct them or copy observation data into code.
- Query current states and relations when needed. None means unknown, not empty or false.
- Visibility does not establish proximity or action applicability.
- Use Python control flow and helpers where useful. Undefined helper calls trigger helper generation; avoid dependency cycles.
- Keep each helper focused on one responsibility. Decompose complex helpers into smaller helpers and compose them through nested calls.
- Sequence actions according to their preconditions and dependencies. Before leaving a location, acquire any objects needed elsewhere and complete prerequisites that require access to that location. Recheck visibility and state after moving.
- Use parse_objects for object selection and parse_question for observation-based questions.
- Do not import modules, access private attributes, or perform external I/O."""

API = """Actions accept ObjectRef values or class-name strings and return ActionResult with status and error.
{actions}
ObjectRef exposes id and name; a reference identifies an instance, not its current state.
Environment objects lists known class names; observation lists visible class counts.
get_visible_objects() -> list[ObjectRef], excluding rooms and the character
get_object_states(ref) -> frozenset[str] or None
get_objects_in(ref), get_objects_on(ref) -> direct observed list[ObjectRef] or None when inaccessible
is_holding(ref) -> bool
get_current_room() -> room ObjectRef or None
parse_objects(description) -> list[ObjectRef], computed by generated query code
parse_question(question) -> answer, computed by generated query code
Allowed builtins: abs all any bool dict enumerate float frozenset int len list max min
range reversed round set sorted str sum tuple zip isinstance ValueError TypeError."""


def load_examples(purpose):
    return json.loads((ROOT / "examples" / f"{PROMPTS[purpose]}.json").read_text(encoding="utf-8"))


def section(name, content):
    return f"<{name}>\n{escape(content)}\n</{name}>"


def build_prompt(episode_id, purpose, query, context=None, examples="", inventory=()):
    template = (ROOT / "prompts" / f"{PROMPTS[purpose]}.txt").read_text(encoding="utf-8").strip()
    classes = inventory.get("object_classes", []) if isinstance(inventory, dict) else list(inventory)
    rooms = inventory.get("room_names", []) if isinstance(inventory, dict) else []
    rules = RULES
    if purpose in {"cap_objects", "cap_question"}:
        rules += "\n- Use queries only; do not perform actions."
    if purpose == "cap_question":
        rules += "\n- Return None for an answer that cannot currently be observed."
    actions = ", ".join(f"{name}(obj, target)" if name in {"putin", "putback", "apply"}
                        else f"{name}()" if name == "standup" else f"{name}(obj)"
                        for name in ACTION_CLASSES)
    parts = [section("instructions", template), section("rules", rules),
             section("api", API.format(actions=actions))]
    environment = [section("objects", json.dumps(classes)), section("rooms", json.dumps(rooms))]
    if context is not None:
        if context["episode_id"] != episode_id or "observation_revision" not in context:
            raise ValueError("Unscoped observation context")
        counts = Counter(obj.name for obj in context["visible_objects"])
        environment.append(section("observation", json.dumps(dict(sorted(counts.items())))))
    parts.append("<environment>\n" + "\n".join(environment) + "\n</environment>")
    if purpose != "cap_policy":
        examples = "\n\n".join(f"# request: {row['request']}\n{row['code']}" for row in load_examples(purpose))
    parts.append(section("examples", examples))
    parts.append(section("task" if purpose == "cap_policy" else "request", query))
    parts.append(section("output-format", OUTPUT_FORMATS[purpose] +
                         " Return Python code only, without Markdown fences or explanations."))
    return "\n\n".join(parts)


def select_examples(example_type="default", number=3, seed=42):
    """Select external CaP examples with ProgPrompt's identities and seed policy."""
    import random
    from methods.progprompt.constants import DEFAULT_EXAMPLES

    examples = load_examples("cap_policy")
    if not 1 <= number <= 6:
        raise ValueError("examples_num must be between 1 and 6")
    if example_type == "random":
        from methods.shared.datasets import dataset_root
        data = json.loads((dataset_root() / "pythonic_plans" / "train_complete_plan_set.json").read_text())
        keys = random.Random(seed).sample([name for entry in data for name in entry], number)
    elif example_type == "default":
        keys = DEFAULT_EXAMPLES[:number]
    else:
        raise ValueError("Unknown example selection")
    if any(key not in examples for key in keys):
        raise ValueError("Selected training identity has no CaP representation")
    return "\n\n".join(f"# task: {key}\n{examples[key]}" for key in keys)
