"""Episode-scoped request construction; query results are input only when supplied."""

import json
from collections import Counter
from pathlib import Path
from .environment import ACTION_CLASSES

PROMPTS = {"cap_policy": "policy", "cap_function": "function_gen",
           "cap_objects": "parse_objects", "cap_question": "parse_question"}
OUTPUT_FORMATS = {
    "cap_policy": "Start with the exact line def policy(): and indent all task statements "
                  "inside that function. Only function definitions are allowed at module scope.",
    "cap_function": "Return exactly one definition of the requested helper function.",
    "cap_objects": "Return Python statements assigning the resulting list of live ObjectRef values to ret_val.",
    "cap_question": "Return Python statements assigning the computed answer to ret_val.",
}

CONTRACT = """Use ordinary Python only, without imports, Markdown, external I/O or private attributes.
ObjectRef is immutable with episode_id, id, name. Obtain references from queries;
never construct them. References identify an instance, not remembered current state.
get_visible_objects() returns references excluding rooms and character.
get_object_states(ref) returns frozenset[str] or None (unknown); empty differs from unknown.
get_objects_in(ref), get_objects_on(ref) return observed direct relation lists or None
when inaccessible; None never establishes empty contents. is_holding(ref) returns bool.
get_current_room() returns room reference or None. Queries make no model requests.
Actions accept references (exact instance) or class-name strings (existing resolver).
Actions return ActionResult with status 'succeeded', 'failed', or 'skipped', error,
and observation_revision. Never test result truthiness; compare status explicitly.
Visibility does not establish proximity or admissibility. No new physical primitives.
parse_objects(description) generates and executes code returning list[ObjectRef].
parse_question(question) generates and executes code returning an accessible answer.
Nested LMP calls consume the same task and generation budgets. Unknown facts use None.
Unknown direct function calls request generated helpers. Do not invent simulator actions.
Observation context summarizes visible class counts; obtain actual ObjectRef values with
get_visible_objects(). Read states, containment and possession using query functions.
Do not copy observation data into code or infer unknown states from the summary.
Allowed builtins: abs all any bool dict enumerate float frozenset int len list max min
range reversed round set sorted str sum tuple zip isinstance ValueError TypeError.
"""


def build_prompt(episode_id, purpose, query, context=None, examples="", inventory=()):
    template = (Path(__file__).parent / "prompts" / f"{PROMPTS[purpose]}.txt").read_text(encoding="utf-8")
    classes = inventory.get("object_classes", []) if isinstance(inventory, dict) else list(inventory)
    rooms = inventory.get("room_names", []) if isinstance(inventory, dict) else []
    parts = [f"Active episode_id: {episode_id}", template, CONTRACT,
             "Actions: " + ", ".join(ACTION_CLASSES),
             "Class inventory (global class names only): " + json.dumps(classes),
             "Room navigation metadata (not observed household objects): " + json.dumps(rooms)]
    if examples:
        parts.append("Training examples (independent example episodes):\n" + examples)
    if context is not None:
        if context["episode_id"] != episode_id or "observation_revision" not in context:
            raise ValueError("Unscoped observation context")
        counts = Counter(obj.name for obj in context["visible_objects"])
        summary = {
            "episode_id": context["episode_id"],
            "observation_revision": context["observation_revision"],
            "visible_object_counts": dict(sorted(counts.items())),
        }
        parts.append("Permitted observation:\n" + json.dumps(summary))
    parts.append("Request:\n" + query)
    parts.append("Output raw Python only. " + OUTPUT_FORMATS[purpose] +
                 " No Markdown fences, explanations, or copied observation lists. "
                 "Use the registered query APIs for current facts.")
    return "\n\n".join(parts)


def select_examples(example_type="default", number=3, seed=42):
    """Use the established training identity/seed policy with CaP representations."""
    import random
    examples = {
        "refrigerate_the_salmon": '''def policy():
    walk("kitchen")
    find("salmon")
    if grab("salmon").status == "succeeded":
        find("fridge")
        if open("fridge").status == "succeeded":
            putin("salmon", "fridge")
            close("fridge")''',
        "bring_me_some_fruit": '''def policy():
    walk("kitchen")
    fruit = parse_objects("visible fruit")
    for obj in fruit:
        if walk(obj).status == "succeeded":
            if grab(obj).status == "succeeded":
                walk("livingroom")
                find("coffeetable")
                putback(obj, "coffeetable")''',
        "wash_clothes": '''def policy():
    walk("bedroom")
    find("clothespile")
    if grab("clothespile").status == "succeeded":
        walk("bathroom")
        find("washingmachine")
        open("washingmachine")
        putin("clothespile", "washingmachine")
        close("washingmachine")
        switchon("washingmachine")''',
        "put_apple_in_fridge": '''def policy():
    walk("kitchen")
    apples = [o for o in get_visible_objects() if o.name == "apple"]
    for apple in apples:
        if walk(apple).status == "succeeded" and grab(apple).status == "succeeded":
            find("fridge")
            open("fridge")
            putin(apple, "fridge")
            close("fridge")
            break''',
    }
    # Additional training identities retain their existing task/action vocabulary.
    # These examples are ordinary Python, never executed as notebook cells and
    # never sourced from held-out plans or ground-truth final states.
    training_actions = {
        "read_book_under_table_lamp": [('walk', 'tablelamp'), ('find', 'book'), ('grab', 'book'), ('find', 'tablelamp'), ('read', 'book')],
        "put_clothes_in_closet": [('walk', 'bedroom'), ('find', 'clothespile'), ('grab', 'clothespile'), ('find', 'closet'), ('open', 'closet'), ('putin', 'clothespile', 'closet')],
        "put_papers_in_the_folder": [('walk', 'livingroom'), ('find', 'paper'), ('grab', 'paper'), ('find', 'folder'), ('open', 'folder'), ('putin', 'paper', 'folder'), ('close', 'folder')],
        "call_a_friend": [('walk', 'bedroom'), ('find', 'cellphone'), ('grab', 'cellphone'), ('talk', 'cellphone'), ('find', 'coffeetable'), ('putback', 'cellphone', 'coffeetable')],
        "heat_some_pie": [('walk', 'kitchen'), ('find', 'pie'), ('grab', 'pie'), ('find', 'microwave'), ('open', 'microwave'), ('putin', 'pie', 'microwave'), ('close', 'microwave'), ('switchon', 'microwave'), ('switchoff', 'microwave'), ('open', 'microwave'), ('grab', 'pie'), ('close', 'microwave')],
        "sit_on_the_bench": [('find', 'bench'), ('sit', 'bench')],
        "work_on_computer": [('find', 'computer'), ('switchon', 'computer')],
        "put_my_slippers_near_the_bed": [('find', 'slippers'), ('grab', 'slippers'), ('find', 'bed'), ('putback', 'slippers', 'bed')],
        "take_out_the_trash": [('find', 'garbagecan'), ('grab', 'garbagecan'), ('walk', 'kitchen')],
        "open_the_curtains": [('find', 'curtains'), ('open', 'curtains')],
        "wash_the_frying_pan": [('walk', 'kitchen'), ('find', 'fryingpan'), ('grab', 'fryingpan'), ('find', 'sink'), ('putin', 'fryingpan', 'sink'), ('switchon', 'faucet'), ('switchoff', 'faucet')],
        "bring_my_book_to_the_sofa": [('find', 'book'), ('grab', 'book'), ('find', 'sofa'), ('putback', 'book', 'sofa')],
        "get_my_pants_and_shirt_and_place_on_the_bed": [('find', 'clothespants'), ('grab', 'clothespants'), ('find', 'bed'), ('putback', 'clothespants', 'bed'), ('find', 'clothesshirt'), ('grab', 'clothesshirt'), ('find', 'bed'), ('putback', 'clothesshirt', 'bed')],
        "take_off_pictureframe": [('find', 'photoframe'), ('grab', 'photoframe')],
        "bring_an_apple_to_the_sofa": [('find', 'apple'), ('grab', 'apple'), ('find', 'sofa'), ('putback', 'apple', 'sofa')],
        "bring_my_cellphone_to_the_bed": [('find', 'cellphone'), ('grab', 'cellphone'), ('find', 'bed'), ('putback', 'cellphone', 'bed')],
        "put_book_back_in_the_bookshelf": [('find', 'book'), ('grab', 'book'), ('find', 'bookshelf'), ('putback', 'book', 'bookshelf')],
        "turn_off_the_table_lamp": [('find', 'tablelamp'), ('switchoff', 'tablelamp')],
        "get_some_coffee_from_the_coffee_maker_to_the_coffeetable": [('walk', 'kitchen'), ('find', 'coffeemaker'), ('switchon', 'coffeemaker'), ('switchoff', 'coffeemaker'), ('find', 'coffeepot'), ('grab', 'coffeepot'), ('find', 'coffeetable'), ('putback', 'coffeepot', 'coffeetable')],
        "put_the_soap_in_the_bathroomcabinet": [('walk', 'bathroom'), ('find', 'barsoap'), ('grab', 'barsoap'), ('find', 'bathroomcabinet'), ('open', 'bathroomcabinet'), ('putin', 'barsoap', 'bathroomcabinet'), ('close', 'bathroomcabinet')],
    }
    for name, actions in training_actions.items():
        examples[name] = "def policy():\n" + "\n".join(
            "    " + action[0] + "(" + ", ".join(repr(arg) for arg in action[1:]) + ")"
            for action in actions)
    if not 1 <= number <= 6:
        raise ValueError("examples_num must be between 1 and 6")
    keys = list(examples)
    if example_type == "random":
        # Match ProgPrompt's exact training ordering and seeded sample.
        from methods.shared.datasets import dataset_root
        data = json.loads((dataset_root() / "pythonic_plans" / "train_complete_plan_set.json").read_text())
        keys = random.Random(seed).sample([name for entry in data for name in entry], number)
        if any(key not in examples for key in keys):
            raise ValueError("Selected training identity has no CaP representation")
    elif example_type != "default":
        raise ValueError("Unknown example selection")
    else:
        keys = keys[:4]  # Same DEFAULT_EXAMPLES limit as ProgPrompt.
    return "\n\n".join(f"# example episode_id: example-{i}; task: {key}\n{examples[key]}"
                          for i, key in enumerate(keys[:number]))
