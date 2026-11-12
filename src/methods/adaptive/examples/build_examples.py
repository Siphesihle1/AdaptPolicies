"""Write the Adaptive Policies few-shot example files from the sources below.

The explicit policy and helper examples convert CaP's examples (same training
identities) to the AP style: no failure handling, checkpoints on the observable
effects later steps rely on. The implicit files are derived mechanically with
`strip_checkpoints`, so the two sets differ only in the checkpoints. The
specialized-LMP examples are CaP's, unchanged. Recovery examples are kept in
recovery_examples.json, whose failure headers were captured in the simulator.

Run from the repository with src on the import path:
    python -m methods.adaptive.examples.build_examples
"""

import json
from pathlib import Path

from methods.adaptive.validate_examples import strip_checkpoints

HERE = Path(__file__).parent
CAP = HERE.parents[1] / "cap" / "examples"


def holding(name):
    return f'lambda: any(obj.name == "{name}" and is_holding(obj) for obj in get_visible_objects())'


def state(name, value):
    return (f'lambda: any(obj.name == "{name}" and "{value}" in (get_object_states(obj) or ())'
            f' for obj in get_visible_objects())')


def related(item, place, query):
    return (f'lambda: any(obj.name == "{item}" for place in get_visible_objects() if place.name == "{place}"'
            f' for obj in ({query}(place) or []))')


def on(item, surface):
    return related(item, surface, "get_objects_on")


def inside(item, container):
    return related(item, container, "get_objects_in")


def visible(name):
    return f'lambda: any(obj.name == "{name}" for obj in get_visible_objects())'


def carry(item, surface, start=None):
    """Find, grab and put an item onto a surface, with holding and placement checkpoints."""
    lines = [f'    walk("{start}")'] if start else []
    lines += [f'    find("{item}")', f'    grab("{item}")',
              f'    checkpoint("holding the {item}", {holding(item)})',
              f'    find("{surface}")', f'    putback("{item}", "{surface}")',
              f'    checkpoint("the {item} is on the {surface}", {on(item, surface)})']
    return lines


def policy(*lines):
    return "def policy():\n" + "\n".join(lines)


POLICIES = {
    "refrigerate_the_salmon": policy(
        '    salmon = parse_objects("visible salmon")',
        '    if not salmon:',
        '        find("salmon")',
        f'        checkpoint("a salmon is visible", {visible("salmon")})',
        '        salmon = parse_objects("visible salmon")',
        '    salmon = salmon[0]',
        '    acquire_object(salmon)',
        '    checkpoint("holding the salmon", lambda: is_holding(salmon))',
        '    find("fridge")',
        f'    checkpoint("a fridge is visible", {visible("fridge")})',
        '    fridge = parse_objects("visible fridges")[0]',
        '    place_held_in_container(salmon, fridge)',
        '    checkpoint("the salmon is inside the fridge", lambda: salmon in (get_objects_in(fridge) or []))',
        '    close(fridge)',
        '    checkpoint("the fridge is closed", lambda: "CLOSED" in (get_object_states(fridge) or ()))'),
    "bring_me_some_fruit": policy(
        '    fruit = parse_objects("visible bananas")',
        '    if not fruit:',
        '        find("bananas")',
        f'        checkpoint("bananas are visible", {visible("bananas")})',
        '        fruit = parse_objects("visible bananas")',
        '    fruit = fruit[0]',
        '    acquire_object(fruit)',
        '    checkpoint("holding the bananas", lambda: is_holding(fruit))',
        '    walk("livingroom")',
        '    checkpoint("in the living room with the bananas",',
        '               lambda: get_current_room().name == "livingroom" and is_holding(fruit))'),
    "wash_clothes": policy(
        '    clothes = parse_objects("visible piles of clothes")',
        '    if not clothes:',
        '        find("clothespile")',
        f'        checkpoint("a pile of clothes is visible", {visible("clothespile")})',
        '        clothes = parse_objects("visible piles of clothes")',
        '    clothes = clothes[0]',
        '    acquire_object(clothes)',
        '    checkpoint("holding the clothes", lambda: is_holding(clothes))',
        '    find("washingmachine")',
        f'    checkpoint("a washing machine is visible", {visible("washingmachine")})',
        '    machine = parse_objects("visible washing machines")[0]',
        '    load_washing_machine(clothes, machine)',
        '    run_wash_cycle(machine)',
        '    unload_washing_machine(clothes, machine)',
        '    checkpoint("holding the washed clothes",',
        '               lambda: is_holding(clothes) and "WASHED" in (get_object_states(clothes) or ()))'),
    "put_apple_in_fridge": policy(
        '    find("apple")',
        '    grab("apple")',
        '    apple = checkpoint("holding an apple",',
        '                       lambda: [obj for obj in get_visible_objects() if obj.name == "apple" and is_holding(obj)])[0]',
        '    find("fridge")',
        '    fridge = checkpoint("a fridge is visible",',
        '                        lambda: [obj for obj in get_visible_objects() if obj.name == "fridge"])[0]',
        '    place_held_in_container(apple, fridge)',
        '    close(fridge)',
        '    checkpoint("the fridge is closed", lambda: "CLOSED" in (get_object_states(fridge) or ()))'),
    "read_book_under_table_lamp": policy(
        '    walk("tablelamp")',
        '    find("book")',
        '    grab("book")',
        f'    checkpoint("holding a book", {holding("book")})',
        '    find("tablelamp")',
        '    read("book")'),
    "put_clothes_in_closet": policy(
        '    walk("bedroom")',
        '    find("clothespile")',
        '    grab("clothespile")',
        f'    checkpoint("holding a pile of clothes", {holding("clothespile")})',
        '    find("closet")',
        '    closets = checkpoint("a closet is visible",',
        '                         lambda: [obj for obj in get_visible_objects() if obj.name == "closet"])',
        '    opened = [obj for obj in closets if "OPEN" in (get_object_states(obj) or frozenset())]',
        '    target = opened[0] if opened else closets[0]',
        '    ensure_open(target)',
        '    putin("clothespile", target)',
        '    checkpoint("the clothes are inside the closet",',
        '               lambda: any(obj.name == "clothespile" for obj in (get_objects_in(target) or [])))'),
    "put_papers_in_the_folder": policy(
        '    walk("livingroom")',
        '    find("paper")',
        '    grab("paper")',
        f'    checkpoint("holding the paper", {holding("paper")})',
        '    find("folder")',
        '    open("folder")',
        f'    checkpoint("the folder is open", {state("folder", "OPEN")})',
        '    putin("paper", "folder")',
        f'    checkpoint("the paper is inside the folder", {inside("paper", "folder")})',
        '    close("folder")'),
    "call_a_friend": policy(
        '    walk("bedroom")',
        '    find("cellphone")',
        '    grab("cellphone")',
        f'    checkpoint("holding the cellphone", {holding("cellphone")})',
        '    talk("cellphone")',
        '    find("coffeetable")',
        '    putback("cellphone", "coffeetable")',
        f'    checkpoint("the cellphone is on the coffee table", {on("cellphone", "coffeetable")})'),
    "sit_on_the_bench": policy(
        '    find("bench")',
        f'    checkpoint("a bench is visible", {visible("bench")})',
        '    sit("bench")'),
    "work_on_computer": policy(
        '    find("computer")',
        '    switchon("computer")',
        f'    checkpoint("the computer is on", {state("computer", "ON")})'),
    "put_my_slippers_near_the_bed": policy(
        '    walk("bedroom")',
        '    find("bed")',
        '    grab("slippers")',
        f'    checkpoint("holding the slippers", {holding("slippers")})',
        '    putback("slippers", "bed")',
        f'    checkpoint("the slippers are on the bed", {on("slippers", "bed")})'),
    "take_out_the_trash": policy(
        '    find("garbagecan")',
        '    grab("garbagecan")',
        f'    checkpoint("holding the garbage can", {holding("garbagecan")})',
        '    walk("kitchen")',
        '    checkpoint("in the kitchen", lambda: get_current_room().name == "kitchen")'),
    "open_the_curtains": policy(
        '    find("curtains")',
        '    open("curtains")',
        f'    checkpoint("the curtains are open", {state("curtains", "OPEN")})'),
    "wash_the_frying_pan": policy(
        '    walk("kitchen")',
        '    find("fryingpan")',
        '    grab("fryingpan")',
        f'    checkpoint("holding the frying pan", {holding("fryingpan")})',
        '    find("sink")',
        '    putback("fryingpan", "sink")',
        f'    checkpoint("the frying pan is on the sink", {on("fryingpan", "sink")})',
        '    find("faucet")',
        '    switchon("faucet")',
        f'    checkpoint("the faucet is on", {state("faucet", "ON")})',
        '    switchoff("faucet")'),
    "bring_my_book_to_the_sofa": policy(*carry("book", "sofa")),
    "get_my_pants_and_shirt_and_place_on_the_bed": policy(
        *carry("clothespants", "bed"), *carry("clothesshirt", "bed")),
    "take_off_pictureframe": policy(
        '    walk("livingroom")',
        '    find("wallpictureframe")',
        '    grab("wallpictureframe")',
        f'    checkpoint("holding the picture frame", {holding("wallpictureframe")})'),
    "bring_an_apple_to_the_sofa": policy(*carry("apple", "sofa")),
    "bring_my_cellphone_to_the_bed": policy(*carry("cellphone", "bed")),
    "put_book_back_in_the_bookshelf": policy(*carry("book", "bookshelf")),
    "turn_off_the_table_lamp": policy(
        '    find("tablelamp")',
        '    switchoff("tablelamp")',
        f'    checkpoint("the table lamp is off", {state("tablelamp", "OFF")})'),
    "get_some_coffee_from_the_coffee_maker_to_the_coffeetable": policy(
        '    walk("kitchen")',
        '    find("coffeemaker")',
        '    switchon("coffeemaker")',
        f'    checkpoint("the coffee maker is on", {state("coffeemaker", "ON")})',
        '    switchoff("coffeemaker")',
        '    find("coffeepot")',
        '    grab("coffeepot")',
        f'    checkpoint("holding the coffee pot", {holding("coffeepot")})',
        '    find("coffeetable")',
        '    putback("coffeepot", "coffeetable")',
        f'    checkpoint("the coffee pot is on the coffee table", {on("coffeepot", "coffeetable")})'),
    "put_the_soap_in_the_bathroomcabinet": policy(
        '    walk("bathroom")',
        '    find("barsoap")',
        '    grab("barsoap")',
        f'    checkpoint("holding the soap", {holding("barsoap")})',
        '    find("bathroomcabinet")',
        '    open("bathroomcabinet")',
        f'    checkpoint("the bathroom cabinet is open", {state("bathroomcabinet", "OPEN")})',
        '    putin("barsoap", "bathroomcabinet")',
        f'    checkpoint("the soap is inside the cabinet", {inside("barsoap", "bathroomcabinet")})',
        '    close("bathroomcabinet")'),
    "heat_some_pie": policy(
        '    pies = parse_objects("visible pie")',
        '    if not pies:',
        '        find("pie")',
        f'        checkpoint("a pie is visible", {visible("pie")})',
        '        pies = parse_objects("visible pie")',
        '    pie = pies[0]',
        '    acquire_object(pie)',
        '    checkpoint("holding the pie", lambda: is_holding(pie))',
        '    find("microwave")',
        f'    checkpoint("a microwave is visible", {visible("microwave")})',
        '    microwave = parse_objects("visible microwaves")[0]',
        '    load_microwave(pie, microwave)',
        '    run_heating_cycle(microwave)',
        '    retrieve_heated_food(pie, microwave)',
        '    checkpoint("holding the heated pie",',
        '               lambda: is_holding(pie) and "HEATED" in (get_object_states(pie) or ()))'),
}


HELPERS = [
    ("acquire_object(item)", '''def acquire_object(item):
    """Hold the item."""
    if is_holding(item):
        return True
    walk(item)
    grab(item)
    return checkpoint("holding the item", lambda: is_holding(item))'''),
    ("ensure_open(container)", '''def ensure_open(container):
    """Stand at the container and leave it open."""
    walk(container)
    if "OPEN" not in (get_object_states(container) or ()):
        open(container)
    return checkpoint("the container is open", lambda: "OPEN" in (get_object_states(container) or ()))'''),
    ("place_held_in_container(item, container)", '''def place_held_in_container(item, container):
    """Put the held item inside the container."""
    checkpoint("holding the item", lambda: is_holding(item))
    ensure_open(container)
    putin(item, container)
    return checkpoint("the item is inside the container", lambda: item in (get_objects_in(container) or []))'''),
    ("load_washing_machine(clothes, machine)", '''def load_washing_machine(clothes, machine):
    """Put the held clothes in the washing machine and close it."""
    place_held_in_container(clothes, machine)
    close(machine)
    return checkpoint("the washing machine is closed", lambda: "CLOSED" in (get_object_states(machine) or ()))'''),
    ("run_wash_cycle(machine)", '''def run_wash_cycle(machine):
    """Run the washing machine once; the washed state cannot be observed while it is closed."""
    switchon(machine)
    switchoff(machine)'''),
    ("unload_washing_machine(clothes, machine)", '''def unload_washing_machine(clothes, machine):
    """Take the clothes out of the washing machine and close it."""
    ensure_open(machine)
    grab(clothes)
    checkpoint("holding the clothes", lambda: is_holding(clothes))
    close(machine)
    return checkpoint("the washing machine is closed", lambda: "CLOSED" in (get_object_states(machine) or ()))'''),
    ("load_microwave(food, microwave)", '''def load_microwave(food, microwave):
    """Put the held food in the microwave and close it."""
    place_held_in_container(food, microwave)
    close(microwave)
    return checkpoint("the microwave is closed", lambda: "CLOSED" in (get_object_states(microwave) or ()))'''),
    ("run_heating_cycle(microwave)", '''def run_heating_cycle(microwave):
    """Run the microwave once; the heated state cannot be observed while it is closed."""
    switchon(microwave)
    switchoff(microwave)'''),
    ("retrieve_heated_food(food, microwave)", '''def retrieve_heated_food(food, microwave):
    """Take the food out of the microwave and close it."""
    ensure_open(microwave)
    grab(food)
    checkpoint("holding the food", lambda: is_holding(food))
    close(microwave)
    return checkpoint("the microwave is closed", lambda: "CLOSED" in (get_object_states(microwave) or ()))'''),
]


def write(name, value):
    (HERE / f"{name}.json").write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def main():
    cap = json.loads((CAP / "policy.json").read_text(encoding="utf-8"))
    if set(POLICIES) != set(cap):
        raise SystemExit("AP policy identities must match CaP's")
    policies = {task: POLICIES[task] for task in cap}  # CaP's order
    write("policy", policies)
    write("policy_implicit", {task: strip_checkpoints(code) for task, code in policies.items()})
    helpers = [{"request": request, "code": code} for request, code in HELPERS]
    write("function_gen", helpers)
    write("function_gen_implicit", [{"request": r, "code": strip_checkpoints(c)} for r, c in HELPERS])
    for name in ("parse_objects", "parse_question"):
        write(name, json.loads((CAP / f"{name}.json").read_text(encoding="utf-8")))


if __name__ == "__main__":
    main()
