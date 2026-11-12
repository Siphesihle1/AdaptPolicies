"""Adaptive Policies prompts, derived from CaP's scheme (D11).

The section structure, builder, environment rendering and output-format suffix
follow CaP. The text is AP's: CaP wording that leads to CaP-style policies
(status checks, early returns, boolean helper contracts, final self-checks) is
replaced, and `checkpoint` is described only when explicit checkpoints are on.
"""

from pathlib import Path

from methods.shared.lmp_environment import ACTION_CLASSES
from methods.shared.lmp_prompt import (environment_section, read_examples, render_request_examples,
                                       section, select_policy_examples)
from .settings import PLACEMENTS

ROOT = Path(__file__).parent
SUFFIX = " Return Python code only, without Markdown fences or explanations."

POLICY_INSTRUCTIONS = {
    True: ("Write a Python policy to complete the task in VirtualHome. The policy runs with checkpoints: "
           "each checkpoint checks an expected state, and if it does not hold, a recovery is written from "
           "the current state and the policy continues after the checkpoint."),
    False: ("Write a Python policy to complete the task in VirtualHome. Failed actions are recovered "
            "automatically: a recovery is written from the current state and the policy continues."),
}
INSTRUCTIONS = {
    "ap_function": "Implement the requested helper for its call site and originating program.",
    "ap_regenerate": "Rewrite the failing helper so that it handles the failure below. Keep its name and parameters.",
    "ap_objects": "Write Python code selecting currently visible objects matching the description.",
    "ap_question": "Write Python code computing the answer from current observations.",
    "ap_recover": ("Write a Python recovery that, from the current state, makes the failed checkpoint or "
                   "action succeed so the program can continue."),
    "ap_replan": "Write a Python policy that completes the rest of the task from the current state.",
}
OUTPUT_FORMATS = {
    "ap_policy": "Define policy() with no arguments. Additional helper definitions are allowed. "
                 "Only function definitions are allowed at module scope.",
    "ap_function": "Return exactly one definition of the requested helper function.",
    "ap_regenerate": "Return exactly one definition of the helper with the same name and parameters, "
                     "replacing the failing version.",
    "ap_objects": "Return Python statements assigning the resulting list of live ObjectRef values to ret_val.",
    "ap_question": "Return Python statements assigning the computed answer to ret_val.",
    "ap_recover": "Define recover() with no arguments. Additional helper definitions are allowed. "
                  "Only function definitions are allowed at module scope.",
    "ap_replan": "Define policy() with no arguments that completes the remaining task from the current "
                 "state. Additional helper definitions are allowed. Only function definitions are allowed "
                 "at module scope.",
}

# (text, explicit-only, implicit-only). Numbering follows the design note.
PROGRAM_RULES = [
    ("Use the available APIs for actions and observations; do not redefine them.", None),
    ("Write the steps that achieve the task in order, as if each step succeeds. Do not write fallback "
     "branches or return early when a step fails; failures are recovered.", None),
    ("After a step whose effect later steps rely on, call checkpoint(description, check). The description "
     "states the expected state in a few words. check is a zero-argument lambda that uses queries only and "
     "returns a truthy value when the state holds.", "explicit"),
    ("Checkpoint only states the agent can observe: visibility, holding, open or closed, on a surface, inside "
     "an open container. The contents of a closed container cannot be observed.", "explicit"),
    ("checkpoint returns the value of check. Select objects after a checkpoint, or take them from its return "
     "value; do not reuse a selection made before it.", "explicit"),
    ("A failed action is recovered before your code continues, so you do not need to check result.status.",
     "implicit"),
    ("Obtain object references through queries; never construct them or copy observation data into code.", None),
    ("Query current states and relations when needed. None means unknown, not empty or false.", None),
    ("Visibility does not establish proximity or action applicability.", None),
    ("Use loops and conditionals for the task's structure, such as handling several objects or choosing "
     "between containers, not for handling failures.", None),
    ("Put reusable steps in helpers. Undefined helper calls trigger helper generation; avoid dependency "
     "cycles. Keep each helper focused on one responsibility and compose complex helpers from smaller ones.",
     None),
    ("A helper that achieves a state ends with a checkpoint on that state.", "explicit"),
    ("Order actions by their preconditions. Acquire objects before travelling somewhere they are needed. "
     "After movement, select unheld objects again from the current observation.", None),
    ("Use parse_objects for object selection and parse_question for questions about the observation.", None),
    ("Do not call parse_objects or parse_question inside checkpoint checks; use queries there.", "explicit"),
    ("Do not import modules, access private attributes, or perform external I/O.", None),
]
RECOVERY_RULES = {
    "start": ("Start from the current state in <observation>. Do not repeat steps that <progress> shows as "
              "completed."),
    "repeat": "Do not repeat a recovery that <progress> shows has already failed.",
    "helpers": "Helpers defined in <program> remain available and may be called.",
    "bindings": "Names in <bindings> are available; do not reassign them. Do not call checkpoint inside recover.",
    "action": ("For a failed action, return True if its effect already holds and it should not be retried. "
               "Otherwise make its preconditions hold; the action is then retried."),
    "escalate": ("If the failure cannot be fixed from here, write the most direct attempt; the runtime "
                 "escalates when the check still fails."),
}
QUERY_RULES = [
    "Obtain object references through queries; never construct them or copy observation data into code.",
    "Query current states and relations when needed. None means unknown, not empty or false.",
    "Visibility does not establish proximity or action applicability.",
    "Do not import modules, access private attributes, or perform external I/O.",
    "Use queries only; do not perform actions.",
]

ACTION_API = """Actions accept ObjectRef values or class-name strings and return ActionResult with status ('succeeded', 'failed' or 'skipped'), error and message. A recovered action reports 'succeeded'.
{actions}
grab(item): pick up the specified item.
open(container), close(container): change the container's open state; they do not pick it up.
putin(item, container): place a held item inside a different, accessible container. Open an openable container first.
putback(item, surface): place a held item onto the destination surface.
find(target), walk(destination), run(destination): navigate to a target; run is faster movement.
switchon(device), switchoff(device): activate or deactivate a compatible device.
apply(item, target): supports held toothpaste applied to a held toothbrush; the toothpaste cap must be open."""
QUERY_API = """ObjectRef exposes id and name; a reference identifies an instance, not its current visibility, accessibility or state. Held objects remain available after movement.
Environment objects lists known class names; observation describes the current room, visible states and relations.
get_visible_objects() -> list[ObjectRef], excluding rooms and the character
get_object_states(ref) -> frozenset[str] or None
get_objects_in(ref), get_objects_on(ref) -> direct observed list[ObjectRef] or None when inaccessible
is_holding(ref) -> bool
get_current_room() -> room ObjectRef or None"""
CHECKPOINT_API = ("checkpoint(description, check) -> value of check(); if it is falsy, a recovery runs and "
                  "check() is evaluated again")
LMP_API = """parse_objects(description) -> list[ObjectRef], computed by generated query code
parse_question(question) -> answer, computed by generated query code"""
BUILTINS_API = """Allowed builtins: abs all any bool dict enumerate float frozenset int len list max min
range reversed round set sorted str sum tuple zip isinstance ValueError TypeError."""
PARAMETERS = {"putin": "item, container", "putback": "item, surface", "apply": "item, target",
              "grab": "item", "open": "container", "close": "container",
              "walk": "destination", "run": "destination", "find": "target", "standup": ""}

EXAMPLE_FILES = {"ap_function": "function_gen", "ap_objects": "parse_objects", "ap_question": "parse_question",
                 "ap_recover": "recover", "ap_regenerate": "regenerate_helper", "ap_replan": "replan"}
IMPLICIT_FILES = {"policy": "policy_implicit", "function_gen": "function_gen_implicit"}


def example_file(name, placement):
    if not PLACEMENTS[placement]["explicit"]:
        name = IMPLICIT_FILES.get(name, name)
    return ROOT / "examples" / f"{name}.json"


def load_examples(name, placement="both", exclude_tasks=()):
    rows = read_examples(example_file(name, placement), exclude_tasks)
    if isinstance(rows, list) and not PLACEMENTS[placement]["explicit"]:
        from .validate_examples import strip_checkpoints
        # Without explicit checkpoints the model never sees a checkpoint failure,
        # and recovery examples show their code without checkpoint calls.
        rows = [{**row, "code": strip_checkpoints(row["code"])} if "trigger" in row else row
                for row in rows if row.get("trigger") != "checkpoint"]
    return rows


def rules_for(kind, placement):
    explicit, implicit = PLACEMENTS[placement]["explicit"], PLACEMENTS[placement]["implicit"]
    if kind in {"ap_objects", "ap_question"}:
        rules = list(QUERY_RULES)
        if kind == "ap_question":
            rules.append("Return None for an answer that cannot currently be observed.")
        return rules
    if kind == "ap_recover":
        # Recovery code runs without checkpoints or nested recovery; the runtime
        # evaluates the failed check (or retries the action) after it returns.
        explicit = implicit = False
    rules = [text for text, condition in PROGRAM_RULES
             if (condition is None and not (kind == "ap_recover" and text.startswith("Write the steps")))
             or (condition == "explicit" and explicit) or (condition == "implicit" and implicit)]
    if kind == "ap_recover":
        rules.insert(1, "Write the steps that fix the failure from the current state. Failures inside recover are "
                        "not recovered again.")
    if kind in {"ap_recover", "ap_regenerate", "ap_replan"}:
        rules += [RECOVERY_RULES["start"], RECOVERY_RULES["repeat"]]
    if kind in {"ap_recover", "ap_replan"}:
        rules.append(RECOVERY_RULES["helpers"])
    if kind == "ap_recover":
        rules += [RECOVERY_RULES["bindings"], RECOVERY_RULES["action"]]
    if kind in {"ap_recover", "ap_regenerate"}:
        rules.append(RECOVERY_RULES["escalate"])
    return rules


def api_for(kind, placement):
    parts = []
    if kind not in {"ap_objects", "ap_question"}:
        actions = ", ".join(f"{name}({PARAMETERS.get(name, 'target')})" for name in ACTION_CLASSES)
        parts.append(ACTION_API.format(actions=actions))
    parts.append(QUERY_API)
    if kind not in {"ap_objects", "ap_question"}:
        if PLACEMENTS[placement]["explicit"] and kind != "ap_recover":
            parts.append(CHECKPOINT_API)
        parts.append(LMP_API)
    parts.append(BUILTINS_API)
    return "\n".join(parts)


def render_recovery_examples(rows):
    blocks = []
    for row in rows:
        header = [f"# task: {row['task']}", f"# failure ({row['trigger']}): {row['failure']}"]
        if row.get("helper"):
            header.append("# failing helper:")
            header += [f"#   {line}" for line in row["helper"].splitlines()]
        header += [f"# progress: {row['progress']}"]
        if row.get("bindings"):
            header.append(f"# bindings: {row['bindings']}")
        header.append(f"# observation: {row['observation']}")
        blocks.append("\n".join(header) + "\n" + row["code"])
    return "\n\n".join(blocks)


def build_prompt(episode_id, purpose, query, context=None, examples="", inventory=(), exclude_tasks=(), *,
                 placement="both", failure=None):
    """`failure` holds the program, failure, progress and (for recover) bindings sections."""
    # Helper regeneration is an ap_function request with a failure context.
    kind = "ap_regenerate" if purpose == "ap_function" and failure is not None else purpose
    if kind == "ap_policy":
        instruction = POLICY_INSTRUCTIONS[PLACEMENTS[placement]["explicit"]]
    else:
        instruction = INSTRUCTIONS[kind]
    rules = "\n".join(f"- {rule}" for rule in rules_for(kind, placement))
    parts = [section("instructions", instruction), section("rules", rules),
             section("api", api_for(kind, placement)), environment_section(episode_id, inventory, context)]
    if kind in {"ap_recover", "ap_regenerate", "ap_replan"}:
        examples = render_recovery_examples(load_examples(EXAMPLE_FILES[kind], placement, exclude_tasks))
    elif kind != "ap_policy":
        examples = render_request_examples(load_examples(EXAMPLE_FILES[kind], placement, exclude_tasks))
    parts.append(section("examples", examples))
    parts.append(section("task" if kind in {"ap_policy", "ap_replan"} else "request", query))
    if failure is not None:
        for name in ("program", "failure", "progress", "bindings"):
            if name in failure:
                parts.append(section(name, failure[name]))
    parts.append(section("output-format", OUTPUT_FORMATS[kind] + SUFFIX))
    return "\n\n".join(parts)


def select_examples(example_type="default", number=3, seed=42, *, task_names=None, exclude_tasks=(),
                    placement="both"):
    """Select AP policy examples with CaP's identities and seed policy."""
    examples = load_examples("policy", placement, exclude_tasks)
    return select_policy_examples(examples, example_type, number, seed, task_names=task_names,
                                  exclude_tasks=exclude_tasks, label="AP")
