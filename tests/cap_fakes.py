"""Deterministic collaborators; no inference endpoint or simulator is contacted."""
import copy
from dataclasses import dataclass
import re
import time
from virtual_home.environment import VHEnvironment


@dataclass
class FakeProvider:
    responses: dict

    def __call__(self, prompt, purpose):
        response = self.responses[purpose]
        if isinstance(response, dict):
            response = next(value for key, value in response.items() if key in prompt.split("Request:\n")[-1].splitlines()[0])
        if response == "BLOCK":
            time.sleep(30)
        return response


class FakeEnvironment:
    get_current_state = VHEnvironment.get_current_state

    def __init__(self, env_id=0, room="kitchen", task=None, log=None):
        from io import StringIO
        from uuid import uuid4
        self.episode_id = str(uuid4())
        self.observation_revision = 0
        self.task, self.log_file = task, log or StringIO()
        self.images, self.actions_to_omit = [], []
        self.execution_failed = False
        self.nodes_with_additonal_states, self.object_bindings = {}, {}
        self.object_distances, self.found_id = {}, None
        self.graph = {"nodes": [
            {"id": 1, "class_name": "kitchen", "category": "Rooms", "states": []},
            {"id": 2, "class_name": "bedroom", "category": "Rooms", "states": []},
            {"id": 3, "class_name": "character", "states": []},
            {"id": 10, "class_name": "fridge", "states": ["CLOSED"], "properties": ["CAN_OPEN"]},
            {"id": 20, "class_name": "mug", "states": []},
            {"id": 21, "class_name": "mug", "states": []},
            {"id": 30, "class_name": "apple", "states": []},
        ], "edges": [
            {"from_id": 3, "to_id": 1, "relation_type": "INSIDE"},
            {"from_id": 10, "to_id": 1, "relation_type": "INSIDE"},
            {"from_id": 20, "to_id": 1, "relation_type": "INSIDE"},
            {"from_id": 21, "to_id": 1, "relation_type": "INSIDE"},
            {"from_id": 30, "to_id": 10, "relation_type": "INSIDE"},
        ]}
        for node in self.graph["nodes"]:
            node.setdefault("category", "Objects")
            node.setdefault("properties", [])
        self.initial_state = copy.deepcopy(self.graph)
        self.calls = []
        self.get_current_state()

    def find_obj(self, name):
        return [n["id"] for n in self.graph["nodes"] if n["class_name"] == name]

    def execute(self, script):
        self.calls.append(script)
        self.task.step += 1
        action = re.search(r"\[(\w+)\]", script)[1]
        identifiers = [int(i) for i in re.findall(r"\((\d+)\)", script)]
        if action == "touch":
            return False
        if action in {"open", "close"}:
            node = next(n for n in self.graph["nodes"] if n["id"] == identifiers[0])
            node["states"] = ["OPEN" if action == "open" else "CLOSED"]
        if action == "grab":
            self.graph["edges"].append({"from_id": 3, "to_id": identifiers[0], "relation_type": "HOLDS_RH"})
        self.task.executable_steps += 1
        self.observation_revision += 1
        self.get_current_state()
        return True
