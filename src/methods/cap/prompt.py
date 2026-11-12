"""XML prompts with external examples and internally validated observation context."""

from pathlib import Path
from methods.shared.lmp_environment import ACTION_CLASSES
from methods.shared.lmp_prompt import (environment_section, read_examples, render_request_examples,
                                       section, select_policy_examples)

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
    return read_examples(ROOT / "examples" / f"{PROMPTS[purpose]}.json", exclude_tasks)


def build_prompt(episode_id, purpose, query, context=None, examples="", inventory=(), exclude_tasks=()):
    template = INSTRUCTIONS[purpose]
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
             section("api", API.format(actions=actions)),
             environment_section(episode_id, inventory, context)]
    if purpose != "cap_policy":
        examples = render_request_examples(load_examples(purpose, exclude_tasks))
    parts.append(section("examples", examples))
    parts.append(section("task" if purpose == "cap_policy" else "request", query))
    parts.append(section("output-format", OUTPUT_FORMATS[purpose] +
                         " Return Python code only, without Markdown fences or explanations."))
    return "\n\n".join(parts)


def select_examples(example_type="default", number=3, seed=42, *, task_names=None, exclude_tasks=()):
    """Select external CaP examples with ProgPrompt's identities and seed policy."""
    return select_policy_examples(load_examples("cap_policy", exclude_tasks), example_type, number, seed,
                                  task_names=task_names, exclude_tasks=exclude_tasks, label="CaP")
