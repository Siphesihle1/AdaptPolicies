"""Trusted observation and action adapter shared by the LMP methods. The worker never receives this object."""

from functools import partial
from collections import Counter
from virtual_home import actions
from virtual_home.virtualhome_types import ObjectRef, ActionResult, validate_object_ref


ACTION_CLASSES = {
    "putin": "PutIn", "putback": "PutBack", "apply": "Apply", "find": "Find",
    "walk": "Walk", "open": "Open", "run": "Run", "close": "Close",
    "drink": "Drink", "grab": "Grab", "lookat": "LookAt", "touch": "Touch",
    "talk": "Talk", "read": "Read", "fold": "Fold", "unfold": "Unfold",
    "use": "Use", "switchoff": "SwitchOff", "switchon": "SwitchOn", "sit": "Sit",
    "turnto": "TurnTo", "pointat": "PointAt", "watch": "Watch", "standup": "StandUp",
}
QUERY_NAMES = ("get_visible_objects", "get_object_states", "get_objects_in",
               "get_objects_on", "is_holding", "get_current_room")


class LMPEnvironment:
    def __init__(self, env, task):
        self.env, self.task = env, task
        self.episode_id = env.episode_id
        self.registry = {name: getattr(self, name) for name in QUERY_NAMES}
        self.registry.update({name: partial(self.action, name) for name in ACTION_CLASSES})

    @property
    def revision(self):
        return self.env.observation_revision

    def ref(self, node):
        return ObjectRef(self.episode_id, node["id"], node["class_name"])

    def observed(self, ref):
        if not isinstance(ref, ObjectRef):
            raise TypeError("Queries require an ObjectRef from this episode")
        validate_object_ref(ref, self.env)
        return next((n for n in self.env.partial_graph["nodes"] if n["id"] == ref.id), None)

    def get_visible_objects(self):
        return [self.ref(n) for n in sorted(self.env.partial_graph["nodes"], key=lambda n: n["id"])
                if n.get("category") != "Rooms" and n["class_name"] != "character"]

    def get_object_states(self, obj):
        node = self.observed(obj)
        if node is None or "states" not in node:
            return None
        # Derived effects persist across native graph refreshes, like scoring.
        # Expose them only after this instance is actually visible again.
        cached = self.env.nodes_with_additonal_states.get(obj.id, {}).get("states", [])
        derived = set(cached) & {"WASHED", "HEATED", "USED"}
        return frozenset(node["states"]) | derived

    def relations(self, obj, relation):
        node = self.observed(obj)
        if node is None:
            return None
        # Absence of observed contents cannot establish that a shut container is empty.
        if "CAN_OPEN" in node.get("properties", []) and "OPEN" not in node.get("states", []):
            return None
        identifiers = {e["from_id"] for e in self.env.partial_graph["edges"]
                       if e["to_id"] == obj.id and e["relation_type"] == relation}
        return [ref for ref in self.get_visible_objects() if ref.id in identifiers]

    def get_objects_in(self, container):
        return self.relations(container, "INSIDE")

    def get_objects_on(self, surface):
        return self.relations(surface, "ON")

    def is_holding(self, obj):
        self.observed(obj)
        return obj.id in self.env.obj_ids_in_hand

    def get_current_room(self):
        node = next((n for n in self.env.partial_graph["nodes"]
                     if n["id"] == self.env.agent_in_roomid), None)
        return self.ref(node) if node else None

    def action(self, name, *args):
        for arg in args:
            if isinstance(arg, ObjectRef):
                if self.observed(arg) is None and arg.id not in self.env.obj_ids_in_hand:
                    raise ValueError("object_not_currently_observed")
            elif not isinstance(arg, str):
                raise TypeError("Actions accept object references or class names")
        outcome = getattr(actions, ACTION_CLASSES[name])(self.env, self.task)(*args)
        if self.env.native_state_uncertain:
            raise RuntimeError("uncertain_native_state")
        return ActionResult("succeeded" if outcome is True else "failed" if outcome is False else "skipped",
                            self.revision, None if outcome is True else "action_rejected" if outcome is False else "execution_skipped")

    def context(self):
        visible = self.get_visible_objects()
        nodes = {node["id"]: node for node in self.env.partial_graph["nodes"]}
        room = self.get_current_room()
        counts = Counter((obj.name, tuple(sorted(self.get_object_states(obj) or []))) for obj in visible)
        descriptions = []
        for (name, states), count in sorted(counts.items()):
            description = name + (" is " + " and ".join(states) if states else "")
            descriptions.append(description + (f" ({count})" if count > 1 else ""))
        # The partial graph has already removed inaccessible objects. Its room
        # metadata includes every room; expose relations only to the current one.
        allowed = {obj.id for obj in visible} | {self.env.agent}
        if room is not None:
            allowed.add(room.id)
        relations = sorted({
            f"{nodes[edge['from_id']]['class_name']} {edge['relation_type']} {nodes[edge['to_id']]['class_name']}"
            for edge in self.env.partial_graph["edges"]
            if edge["from_id"] in allowed and edge["to_id"] in allowed
            and edge["relation_type"] not in {"CLOSE", "FACING"}
        })
        observation = {"current_room": room.name if room else None,
                       "visible_objects": descriptions, "relations": relations,
                       "held_objects": sorted(obj.name for obj in visible if obj.id in self.env.obj_ids_in_hand)}
        return {"episode_id": self.episode_id, "observation_revision": self.revision,
                "visible_objects": visible, "observation": observation}
