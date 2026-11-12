"""CaP behaviour must not change when its code is shared with other methods.

CaP's cluster results are kept without a rerun, so prompts, code validation and
the artifacts of complete episodes are compared with outputs recorded from the
code that produced those results. Set CAP_REGRESSION_RECORD=1 to re-record the
fixture; do that only for a deliberate, documented change to CaP behaviour.
"""

import ast
import json
import os
from pathlib import Path
import re
import unittest
from unittest.mock import patch

import test_cap_execution
import test_cap_runtime as runtime_tests
from cap_fakes import FakeEnvironment
from methods.cap.prompt import build_prompt, load_examples, select_examples
from methods.cap.runtime import validate
from virtual_home.virtualhome_types import ObjectRef

FIXTURE = Path(__file__).parent / "fixtures" / "cap_regression.json"
UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
# Timings also appear inside event text recorded in chat transcripts.
TIMING = re.compile(r"('(?:elapsed_seconds|duration_seconds)': )[-+0-9.e]+")
VOLATILE_KEYS = {"elapsed_seconds", "started_at", "finished_at", "timestamp", "created_at",
                 "updated_at", "duration_seconds", "traceback"}


class Normalizer:
    """Replace values that differ between identical runs with stable tokens."""

    def __init__(self, output):
        self.output = str(output)
        self.tokens = {}

    def text(self, value):
        value = value.replace(self.output, "<output>").replace(self.output.replace("\\", "/"), "<output>")
        value = TIMING.sub(r"\1<volatile>", value)
        return UUID.sub(lambda match: self.tokens.setdefault(match[0], f"<uuid-{len(self.tokens)}>"), value)

    def __call__(self, value, key=None):
        if key in VOLATILE_KEYS:
            return "<volatile>"
        if isinstance(value, dict):
            return {self.text(k): self(v, k) for k, v in value.items()}
        if isinstance(value, list):
            return [self(v) for v in value]
        if isinstance(value, str):
            if key is not None and key.endswith(("_file", "_path", "_dir")):
                # Recorded file locations use the platform's separator.
                value = value.replace("\\", "/")
            return self.text(value)
        return value


def run_artifacts(case, responses, tasks, factory=FakeEnvironment, exclude=()):
    agent, output = case.agent(responses, tasks=tasks, factory=factory, exclude_example_tasks=exclude)
    normalize = Normalizer(output)
    files = {}
    for path in sorted(output.rglob("*")):
        if not path.is_file():
            continue
        name = path.relative_to(output).as_posix()
        text = path.read_text(encoding="utf-8")
        if path.suffix == ".json":
            value = json.loads(text)
            if name == "results.json":
                value.pop("generated_at", None)
            files[name] = normalize(value)
        else:
            files[name] = normalize(text)
    return files


class UncertainEnvironment(FakeEnvironment):
    def execute(self, script):
        self.execution_failed = self.native_state_uncertain = True
        return False


class RejectingEnvironment(FakeEnvironment):
    def execute(self, script):
        self.execution_failed = True
        return False


def helper_examples():
    text = "\n\n".join(row["code"] for row in load_examples("cap_function"))
    return {node.name + "(": ast.unparse(node) for node in ast.parse(text).body}


EPISODES = {
    "composition": lambda: ({
        "cap_policy": '''def policy():
    mugs = parse_objects('visible mugs')
    fridges = parse_objects('visible fridge')
    if acquire_object(mugs[0]):
        load_washing_machine(mugs[0], fridges[0])
    return parse_question('am I holding a mug?')''',
        "cap_objects": {
            "visible mugs": "ret_val = [o for o in get_visible_objects() if o.name == 'mug']",
            "visible fridge": "ret_val = [o for o in get_visible_objects() if o.name == 'fridge']",
        },
        "cap_question": "ret_val = any(is_holding(o) for o in get_visible_objects() if o.name == 'mug')",
        "cap_function": helper_examples(),
    }, ("store mug",), FakeEnvironment, ("heat_some_pie",)),
    "scoring": lambda: ({"cap_policy": {
        "open fridge": "def policy():\n    return open('fridge').status",
        "bad program": "def policy():\n    return invalid syntax!"}},
        ("open fridge", "bad program"), FakeEnvironment, ()),
    "fenced": lambda: ({"cap_policy": "```python\ndef policy():\n    return open('fridge').status\n```"},
                       ("open fridge",), FakeEnvironment, ()),
    "rejection": lambda: ({"cap_policy": "def policy():\n    return open('fridge').status"},
                          ("open fridge", "bad program"), RejectingEnvironment, ()),
    "uncertain": lambda: ({"cap_policy": "def policy():\n    open('fridge')"},
                          ("open fridge", "bad program"), UncertainEnvironment, ()),
    "failed_helper": lambda: ({
        "cap_policy": "def policy():\n    return helper_a()",
        "cap_function": {"helper_a(": "def helper_a():\n    return helper_b()",
                         "helper_b(": "def helper_b(:\n    invalid syntax!"},
    }, ("open fridge",), FakeEnvironment, ()),
}

VALIDATION_SOURCES = [
    "def policy():\n    return [o for o in get_visible_objects() if o.name == 'mug']",
    "def policy():\n    check = lambda: is_holding(x)\n    return check",
    "import os", "ret_val = (1).__class__", "walk = 1", "def walk():\n    pass",
    "def f(walk):\n    pass", "def f():\n    global x", "class A:\n    pass",
    "def f(x: int):\n    pass", "@d\ndef f():\n    pass", "x = eval('1')", "x = _private",
    "x = obj.__dict__", "obj.name = 1", "with x:\n    pass", "def f():\n    yield 1",
    "del x", "x = obj.status.lower()", "try:\n    pass\nexcept ValueError as walk:\n    pass",
]


def prompt_cases():
    episode = "episode-1"
    mug, fridge = ObjectRef(episode, 20, "mug"), ObjectRef(episode, 10, "fridge")
    full = {"episode_id": episode, "observation_revision": 3, "visible_objects": [fridge, mug],
            "observation": {"current_room": "kitchen", "visible_objects": ["fridge is CLOSED", "mug"],
                            "relations": ["fridge INSIDE kitchen", "mug INSIDE kitchen"],
                            "held_objects": []}}
    minimal = {"episode_id": episode, "observation_revision": 0, "visible_objects": [mug, mug, fridge]}
    inventory = {"object_classes": ["fridge", "mug"], "room_names": ["bedroom", "kitchen"]}
    return {
        "policy_default": build_prompt(episode, "cap_policy", "open the fridge", full,
                                       select_examples("default", 3), inventory),
        "policy_random_seed42": build_prompt(episode, "cap_policy", "open the fridge", full,
                                             select_examples("random", 3), inventory),
        "policy_explicit_excluded": build_prompt(
            episode, "cap_policy", "wash clothes", None,
            select_examples("default", 2, task_names=["wash_clothes", "heat_some_pie", "call_a_friend"],
                            exclude_tasks=("heat_some_pie",)), ["fridge"], ("heat_some_pie",)),
        "function": build_prompt(episode, "cap_function", "Implement helper f for call: f(x)", None,
                                 "", inventory, ("heat_some_pie",)),
        "objects": build_prompt(episode, "cap_objects", "visible mugs", full, "", inventory),
        "question_minimal_context": build_prompt(episode, "cap_question", "is the fridge open?",
                                                 minimal, "", inventory),
    }


def validation_cases():
    outcomes = {}
    for source in VALIDATION_SOURCES:
        try:
            validate(source, {"walk"})
            outcomes[source] = "accepted"
        except (ValueError, SyntaxError) as error:
            outcomes[source] = f"{type(error).__name__}: {error}"
    return outcomes


class CaPRegressionTests(unittest.TestCase):
    setUp = runtime_tests.RuntimeTests.setUp
    agent = test_cap_execution.ExecutionTests.agent

    def capture(self):
        episodes = {}
        for name, build in EPISODES.items():
            responses, tasks, factory, exclude = build()
            with patch.dict(os.environ, {"PYTHONHASHSEED": "42"}):
                episodes[name] = run_artifacts(self, responses, tasks, factory, exclude)
            # Each episode writes into the same temporary output directory.
            for path in sorted((Path(self.directory.name) / "run").rglob("*"), reverse=True):
                path.unlink() if path.is_file() else path.rmdir()
        dataset = Path(__file__).parents[1] / "src" / "methods" / "progprompt" / "data"
        with patch.dict(os.environ, {"ADAPT_DATASET_DIR": str(dataset)}):
            prompts = prompt_cases()
        return {"prompts": prompts, "validation": validation_cases(), "episodes": episodes}

    def test_cap_outputs_match_recorded_behaviour(self):
        captured = json.loads(json.dumps(self.capture()))
        if os.getenv("CAP_REGRESSION_RECORD") == "1":
            FIXTURE.parent.mkdir(parents=True, exist_ok=True)
            FIXTURE.write_text(json.dumps(captured, indent=1, sort_keys=True) + "\n", encoding="utf-8",
                               newline="\n")
            self.skipTest("Recorded CaP regression fixture")
        expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.maxDiff = None
        for section in ("prompts", "validation"):
            self.assertEqual(captured[section], expected[section], section)
        self.assertEqual(sorted(captured["episodes"]), sorted(expected["episodes"]))
        for name, files in expected["episodes"].items():
            self.assertEqual(sorted(captured["episodes"][name]), sorted(files), name)
            for file, value in files.items():
                self.assertEqual(captured["episodes"][name][file], value, f"{name}: {file}")


if __name__ == "__main__":
    unittest.main()
