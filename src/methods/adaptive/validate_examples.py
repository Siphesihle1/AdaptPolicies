"""Static checks and simulator replays of the Adaptive Policies few-shot examples.

Offline (V1): every example file parses, passes the AP validator for its purpose
and placement condition, uses training identities only, contains no failure
handling CaP-style, and each implicit example equals its explicit version with
the checkpoint calls removed.

In the simulator (V2-V5, `python -m methods.adaptive.validate_examples`): each
policy example is replayed literally through the real AP runtime with a
deterministic generator. A converted example must execute without rejected
actions, pass every checkpoint it reaches on the first evaluation and score at
least its CaP version. Recovery examples are replayed from a captured failure.
"""

import ast
import json
from pathlib import Path

ROOT = Path(__file__).parent / "examples"


def strip_checkpoints(source):
    """The implicit variant: remove checkpoint statements and unwrap checkpoint values.

    `checkpoint(...)` and `return checkpoint(...)` statements are removed; an
    assignment from `checkpoint(description, lambda: EXPR)` keeps EXPR.
    """
    tree = ast.parse(source)
    lines = source.splitlines()
    edits = []  # (start line, start col, end line, end col, replacement), applied bottom-up

    def is_checkpoint(node):
        return (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "checkpoint")

    for node in ast.walk(tree):
        if isinstance(node, (ast.Expr, ast.Return)) and node.value is not None and is_checkpoint(node.value):
            edits.append((node.lineno, None, node.end_lineno, None, None))
        elif isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            for call in ast.walk(node.value):
                if is_checkpoint(call):
                    check = call.args[1]
                    if not isinstance(check, ast.Lambda):
                        raise ValueError("A checkpoint value must come from a lambda")
                    body = ast.get_source_segment(source, check.body)
                    if not isinstance(check.body, (ast.List, ast.ListComp, ast.Call, ast.Name,
                                                   ast.Subscript, ast.Attribute)):
                        body = f"({body})"
                    edits.append((call.lineno, call.col_offset, call.end_lineno, call.end_col_offset, body))
    for start, start_col, end, end_col, text in sorted(edits, key=lambda e: (e[0], e[1] or 0), reverse=True):
        if start_col is None:
            del lines[start - 1:end]
        else:
            prefix, suffix = lines[start - 1][:start_col], lines[end - 1][end_col:]
            lines[start - 1:end] = [prefix + text + suffix]
    result = "\n".join(lines)
    ast.parse(result)  # an emptied block would be a syntax error
    return result


def load(name):
    return json.loads((ROOT / f"{name}.json").read_text(encoding="utf-8"))


def load_rows(name):
    path = ROOT / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


# Shared-scorer results of CaP's validated literal replays (scene 0), from
# "Validated training examples and grounded observations". A converted AP
# example must not score below its CaP version.
CAP_SCORES = {
    "refrigerate_the_salmon": (1.0, 1), "bring_me_some_fruit": (1.0, 1), "wash_clothes": (1.0, 1),
    "put_apple_in_fridge": (1.0, 1), "read_book_under_table_lamp": (1.0, 1), "put_clothes_in_closet": (1.0, 1),
    "put_papers_in_the_folder": (0.6364, 0), "call_a_friend": (1.0, 1), "heat_some_pie": (1.0, 1),
    "sit_on_the_bench": (0.5, 0), "work_on_computer": (0.1667, 0), "put_my_slippers_near_the_bed": (1.0, 1),
    "take_out_the_trash": (0.6, 0), "open_the_curtains": (0.75, 0), "wash_the_frying_pan": (0.3077, 0),
    "bring_my_book_to_the_sofa": (1.0, 1), "get_my_pants_and_shirt_and_place_on_the_bed": (0.8667, 0),
    "take_off_pictureframe": (1.0, 1), "bring_an_apple_to_the_sofa": (1.0, 1),
    "bring_my_cellphone_to_the_bed": (1.0, 1), "put_book_back_in_the_bookshelf": (1.0, 1),
    "turn_off_the_table_lamp": (1.0, 1),
    "get_some_coffee_from_the_coffee_maker_to_the_coffeetable": (1.0, 1),
    "put_the_soap_in_the_bathroomcabinet": (1.0, 1),
}

# parse_objects descriptions used by the examples, answered by fixed query programs.
OBJECT_CLASSES = {"salmon": "salmon", "fridges": "fridge", "bananas": "bananas", "piles of clothes": "clothespile",
                  "washing machines": "washingmachine", "pie": "pie", "microwaves": "microwave",
                  "apples": "apple"}


# Recovery scenarios (V5). Each runs a training task whose program fails in a
# known way. The listed recover/regenerate/replan responses are returned in
# order; the last one of the scenario's kind is the example shown to the model.
# Its header (failure, progress, bindings, observation) is captured from the run.
SCENARIOS = [
    {"id": "R1", "file": "recover", "task": "put_clothes_in_closet", "trigger": "action",
     "program": '''def policy():
    walk("bedroom")
    find("clothespile")
    grab("clothespile")
    find("closet")
    target = [obj for obj in get_visible_objects() if obj.name == "closet"][0]
    open(target)
    putin("clothespile", target)''',
     "recover": ['''def recover():
    return "OPEN" in (get_object_states(target) or ())''']},
    {"id": "R2", "file": "recover", "task": "refrigerate_the_salmon", "trigger": "action",
     "program": '''def policy():
    find("salmon")
    grab("salmon")
    find("fridge")
    fridge = [obj for obj in get_visible_objects() if obj.name == "fridge"][0]
    putin("salmon", fridge)
    close(fridge)''',
     "recover": ['''def recover():
    walk(fridge)
    open(fridge)''']},
    {"id": "R3", "file": "recover", "task": "put_apple_in_fridge", "trigger": "checkpoint",
     "program": '''def policy():
    checkpoint("an apple is visible", lambda: any(obj.name == "apple" for obj in get_visible_objects()))
    find("apple")
    grab("apple")
    apple = checkpoint("holding an apple",
                       lambda: [obj for obj in get_visible_objects() if obj.name == "apple" and is_holding(obj)])[0]
    find("fridge")
    fridge = checkpoint("a fridge is visible",
                        lambda: [obj for obj in get_visible_objects() if obj.name == "fridge"])[0]
    place_held_in_container(apple, fridge)
    close(fridge)''',
     "recover": ['''def recover():
    find("apple")''']},
    {"id": "H1", "file": "regenerate_helper", "task": "wash_clothes", "trigger": "action",
     "program": '''def policy():
    find("clothespile")
    clothes = [obj for obj in get_visible_objects() if obj.name == "clothespile"][0]
    acquire_object(clothes)
    find("washingmachine")
    machine = [obj for obj in get_visible_objects() if obj.name == "washingmachine"][0]
    load_washing_machine(clothes, machine)
    run_wash_cycle(machine)
    unload_washing_machine(clothes, machine)''',
     "helpers": {"unload_washing_machine": '''def unload_washing_machine(clothes, machine):
    """Take the clothes out of the washing machine and close it."""
    ensure_open(machine)
    walk(clothes)
    grab(clothes)
    close(machine)'''},
     "failing_helper": "unload_washing_machine",
     "recover": ['''def recover():
    walk(clothes)''', '''def recover():
    find(clothes)'''],
     "regenerate": ['''def unload_washing_machine(clothes, machine):
    """Take the clothes out of the washing machine and close it."""
    ensure_open(machine)
    grab(clothes)
    checkpoint("holding the clothes", lambda: is_holding(clothes))
    close(machine)
    return checkpoint("the washing machine is closed", lambda: "CLOSED" in (get_object_states(machine) or ()))''']},
    {"id": "H2", "file": "regenerate_helper", "task": "put_my_slippers_near_the_bed", "trigger": "action",
     "program": '''def policy():
    walk("bedroom")
    move_onto("slippers", "bed")''',
     "helpers": {"move_onto": '''def move_onto(item, surface):
    """Put the item onto the surface."""
    walk(item)
    grab(item)
    walk(surface)
    putback(item, surface)'''},
     "failing_helper": "move_onto",
     "recover": ['''def recover():
    find(item)''', '''def recover():
    walk(item)'''],
     "regenerate": ['''def move_onto(item, surface):
    """Put the item onto the surface; approach the surface first, since the item may lie on the floor."""
    find(surface)
    grab(item)
    checkpoint("holding the item", lambda: any(obj.name == item and is_holding(obj) for obj in get_visible_objects()))
    putback(item, surface)
    return checkpoint("the item is on the surface",
                      lambda: any(obj.name == item for place in get_visible_objects() if place.name == surface
                                  for obj in (get_objects_on(place) or [])))''']},
    {"id": "P1", "file": "replan", "task": "put_apple_in_fridge", "trigger": "exception",
     "program": '''def policy():
    apple = [obj for obj in get_visible_objects() if obj.name == "apple"][0]
    acquire_object(apple)
    find("fridge")
    fridge = [obj for obj in get_visible_objects() if obj.name == "fridge"][0]
    place_held_in_container(apple, fridge)
    close(fridge)''',
     "replan": ['''def policy():
    find("apple")
    grab("apple")
    apple = checkpoint("holding an apple",
                       lambda: [obj for obj in get_visible_objects() if obj.name == "apple" and is_holding(obj)])[0]
    find("fridge")
    fridge = checkpoint("a fridge is visible",
                        lambda: [obj for obj in get_visible_objects() if obj.name == "fridge"])[0]
    place_held_in_container(apple, fridge)
    close(fridge)
    checkpoint("the fridge is closed", lambda: "CLOSED" in (get_object_states(fridge) or ()))''']},
    {"id": "P2", "file": "replan", "task": "wash_the_frying_pan", "trigger": "action",
     "program": '''def policy():
    walk("kitchen")
    find("fryingpan")
    grab("fryingpan")
    find("sink")
    putin("fryingpan", "sink")
    find("faucet")
    switchon("faucet")
    switchoff("faucet")''',
     "recover": ['''def recover():
    find("sink")''', '''def recover():
    walk("sink")'''],
     "replan": ['''def policy():
    find("sink")
    putback("fryingpan", "sink")
    checkpoint("the frying pan is on the sink",
               lambda: any(obj.name == "fryingpan" for place in get_visible_objects() if place.name == "sink"
                           for obj in (get_objects_on(place) or [])))
    find("faucet")
    switchon("faucet")
    checkpoint("the faucet is on",
               lambda: any(obj.name == "faucet" and "ON" in (get_object_states(obj) or ())
                           for obj in get_visible_objects()))
    switchoff("faucet")''']},
]


def section_text(prompt, name):
    import re
    from xml.sax.saxutils import unescape
    match = re.search(rf"<{name}>\n(.*?)\n</{name}>", prompt, re.S)
    return unescape(match[1]) if match else None


class ExampleGenerator:
    """Deterministic stand-in for the model: returns example code for each request."""

    def __init__(self, placement="both", scenario=None):
        from .prompt import load_examples
        self.policies = load_examples("policy", placement)
        self.helpers = {row["request"].split("(")[0]: row["code"] for row in load_examples("function_gen", placement)}
        self.scenario = scenario or {}
        self.helpers.update(self.scenario.get("helpers", {}))
        self.queues = {kind: list(self.scenario.get(kind, [])) for kind in ("recover", "regenerate", "replan")}

    def next(self, kind):
        queue = self.queues[kind]
        if not queue:
            raise RuntimeError(f"unexpected_{kind}_request")
        return queue.pop(0) if len(queue) > 1 else queue[0]

    def __call__(self, prompt, purpose):
        request = section_text(prompt, "task") or section_text(prompt, "request") or ""
        if purpose == "ap_policy":
            identity = "_".join(request.strip().split())
            return self.scenario.get("program") or self.policies[identity]
        if purpose == "ap_function" and section_text(prompt, "failure") is not None:
            return self.next("regenerate")
        if purpose == "ap_function":
            name = request.split("Implement helper ", 1)[1].split(" ", 1)[0]
            return self.helpers[name]
        if purpose == "ap_objects":
            name = OBJECT_CLASSES[request.strip().removeprefix("visible ")]
            return f'ret_val = [obj for obj in get_visible_objects() if obj.name == "{name}"]'
        if purpose == "ap_recover":
            return self.next("recover")
        if purpose == "ap_replan":
            return self.next("replan")
        raise RuntimeError(f"unexpected_{purpose}_request")


def run_agent(identities, generator, placement, output, task_seconds=600):
    """Run AdaptiveAgent on training tasks in scene 0 with a deterministic generator."""
    import os
    from .agent import AdaptiveAgent
    from .settings import AdaptiveLimits

    class ValidationAgent(AdaptiveAgent):
        def load_tasks(self, env_id, test_set):
            tasks = super().load_tasks(env_id, test_set)
            return [task for task in tasks if "_".join(task.split()) in identities]

    os.environ["JOB_OUTPUT_DIR"] = str(output)
    os.environ.setdefault("EXPERIMENT_NAME", "ap-example-validation")
    agent = ValidationAgent(0, "train", generator=generator,
                            limits=AdaptiveLimits(placement=placement, task_seconds=task_seconds))
    agent.execute_tasks()
    return agent


def task_report(agent, output, identity):
    record = agent.task_record(identity)
    directory = output / "tasks" / identity
    execution = json.loads((directory / "execution.json").read_text(encoding="utf-8"))
    events = execution.get("events", [])
    rejected = [e for e in events if e["kind"] == "action" and isinstance(e.get("result"), dict)
                and e["result"].get("status") == "failed"]
    metrics = agent.results.get(identity, {})
    return {"identity": identity, "status": record.get("status"), "error": record.get("error"),
            "termination": record.get("termination"), "PSR": metrics.get("PSR"), "SR": metrics.get("SR"),
            "checkpoints_passed": record.get("checkpoints_passed"),
            "failures_by_trigger": record.get("failures_by_trigger"),
            "rejected_actions": [f"{e['name']}{tuple(e['arguments'])}: {e['result'].get('message')}" for e in rejected],
            "events": events}


def validate_policies(placement, output):
    """V2-V4: literal replays of every policy example; all checkpoints pass first time."""
    identities = list(load_rows("policy" if PLACEMENTS_EXPLICIT[placement] else "policy_implicit"))
    agent = run_agent(set(identities), ExampleGenerator(placement), placement, output)
    source = load_rows("policy" if PLACEMENTS_EXPLICIT[placement] else "policy_implicit")
    rows = []
    for identity in identities:
        report = task_report(agent, output, identity)
        cap_psr, cap_sr = CAP_SCORES[identity]
        placed = source[identity].count("checkpoint(")
        problems = []
        if report["status"] != "evaluated":
            problems.append(f"status {report['status']}: {report['error']}")
        if report["rejected_actions"]:
            problems.append("rejected actions: " + "; ".join(report["rejected_actions"]))
        if report["failures_by_trigger"]:
            problems.append(f"checkpoint failures: {report['failures_by_trigger']}")
        if report["PSR"] is None or report["PSR"] + 1e-4 < cap_psr or (report["SR"] or 0) < cap_sr:
            problems.append(f"score {report['PSR']}/{report['SR']} below CaP {cap_psr}/{cap_sr}")
        rows.append({"identity": identity, "placement": placement, "PSR": report["PSR"], "SR": report["SR"],
                     "cap_PSR": cap_psr, "cap_SR": cap_sr, "checkpoints_placed": placed,
                     "checkpoints_passed": report["checkpoints_passed"], "passed": not problems,
                     "problems": problems})
    return rows


def validate_scenario(scenario, output):
    """V5: replay the failing program, capture the failure context and check the recovery."""
    generator = ExampleGenerator("both", scenario)
    agent = run_agent({scenario["task"]}, generator, "both", output)
    report = task_report(agent, output, scenario["task"])
    events = report["events"]
    purpose = {"recover": "ap_recover", "regenerate_helper": "ap_function", "replan": "ap_replan"}[scenario["file"]]
    generations = json.loads((output / "tasks" / scenario["task"] / "generation.json").read_text(encoding="utf-8"))
    requests = [g for g in generations if g["kind"] == "generation_request" and g["purpose"] == purpose
                and (purpose != "ap_function" or "<failure>" in g["prompt"])]
    problems = []
    if not requests:
        problems.append(f"no {purpose} request: the failure did not reach the expected scope")
        captured = None
    else:
        prompt = requests[-1]["prompt"]
        captured = {name: section_text(prompt, name) for name in ("failure", "progress", "bindings", "observation")}
    results = [e for e in events if e["kind"] == "recovery_result"]
    failures = [e for e in events if e["kind"] == "checkpoint_failed"]
    if not failures or failures[0]["trigger"] != scenario["trigger"]:
        problems.append(f"first failure {failures[0]['trigger'] if failures else None}, expected {scenario['trigger']}")
    if scenario["file"] == "recover" and not any(r["succeeded"] and r["scope"] == "local" for r in results):
        problems.append("the local recovery did not succeed")
    if scenario["file"] == "regenerate_helper" and not any(r["succeeded"] and r["scope"] == "helper" for r in results):
        problems.append("the helper regeneration did not succeed")
    if scenario["file"] == "replan" and not any(e["kind"] == "replan" for e in events):
        problems.append("no replan happened")
    if report["status"] != "evaluated" or report["termination"] != "returned":
        problems.append(f"episode ended {report['status']}/{report['termination']}: {report['error']}")
    example = None
    if captured:
        example = {"id": scenario["id"], "task": scenario["task"], "trigger": scenario["trigger"],
                   "failure": failures[0]["summary"] if failures else captured["failure"],
                   "progress": compact(captured["progress"]), "bindings": compact(captured["bindings"])
                   if scenario["file"] == "recover" else None,
                   "observation": compact(captured["observation"]),
                   "code": {"recover": scenario.get("recover", [""])[-1],
                            "regenerate_helper": scenario.get("regenerate", [""])[-1],
                            "replan": scenario.get("replan", [""])[-1]}[scenario["file"]]}
        if scenario["file"] == "regenerate_helper":
            example["helper"] = scenario["helpers"][scenario["failing_helper"]]
    return {"id": scenario["id"], "file": scenario["file"], "task": scenario["task"], "PSR": report["PSR"],
            "SR": report["SR"], "passed": not problems, "problems": problems,
            "rejected_actions": report["rejected_actions"], "example": example}


def compact(text):
    if text is None:
        return None
    lines = [line.strip().removeprefix("- ") for line in text.splitlines() if line.strip()]
    return "; ".join(line for line in lines if line not in {"Completed so far:"})


def observation_section(prompt):
    return section_text(prompt, "observation")


PLACEMENTS_EXPLICIT = {"both": True, "explicit": True, "implicit": False}


def main(argv=None):
    import argparse
    import os
    from datetime import datetime, timezone
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--policies", choices=["explicit", "implicit", "none"], nargs="*", default=["explicit", "implicit"])
    parser.add_argument("--scenarios", nargs="*", default=[s["id"] for s in SCENARIOS])
    parser.add_argument("--write-examples", action="store_true",
                        help="write captured recovery examples for scenarios that pass")
    args = parser.parse_args(argv)
    output = Path(args.output)
    report = {"started": datetime.now(timezone.utc).isoformat(), "policies": [], "scenarios": []}
    placements = {"explicit": "both", "implicit": "implicit"}
    for kind in args.policies:
        if kind == "none":
            continue
        report["policies"] += validate_policies(placements[kind], output / f"policies-{kind}")
    for scenario in SCENARIOS:
        if scenario["id"] in args.scenarios:
            report["scenarios"].append(validate_scenario(scenario, output / f"scenario-{scenario['id']}"))
    if args.write_examples:
        examples = {}
        for row in report["scenarios"]:
            if row["passed"] and row["example"]:
                examples.setdefault(row["file"], []).append(row["example"])
        for name, rows in examples.items():
            existing = {row["id"]: row for row in load_rows(name)}
            existing.update({row["id"]: row for row in rows})
            ordered = [existing[s["id"]] for s in SCENARIOS if s["id"] in existing]
            (ROOT / f"{name}.json").write_text(json.dumps(ordered, indent=2) + "\n", encoding="utf-8", newline="\n")
    report["finished"] = datetime.now(timezone.utc).isoformat()
    report["commit"] = os.getenv("GIT_COMMIT")
    (output / "validation-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    failed = [r for r in report["policies"] + report["scenarios"] if not r["passed"]]
    for row in report["policies"]:
        print(f"{'PASS' if row['passed'] else 'FAIL'} {row['placement']:8} {row['identity']}: "
              f"PSR {row['PSR']} SR {row['SR']} (CaP {row['cap_PSR']}/{row['cap_SR']}) "
              f"checkpoints {row['checkpoints_passed']}/{row['checkpoints_placed']} {'; '.join(row['problems'])}")
    for row in report["scenarios"]:
        print(f"{'PASS' if row['passed'] else 'FAIL'} {row['id']} {row['task']}: PSR {row['PSR']} SR {row['SR']} "
              f"{'; '.join(row['problems'])}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
