from math import dist
from typing import Dict, Any, List, Tuple

from .graph_query import E, N

GraphNodeData = Dict[str, Any]
Point3D = Tuple[float, float, float]


# Adapted from https://github.com/NVlabs/progprompt-vh/blob/main/scripts/utils_aug_env.py#L12
def get_obj_ids_for_adding_states(graph: Dict[str, Any]) -> Tuple[List[int]]:
    obj_for_adding_states = [
        "wallphone",
        "microwave",
        "stove",
        "fryingpan",
        "washingmachine",
        "sink",
        "faucet",
        # "toaster",  ## toaster condition - TODO ##
    ]

    return tuple(
        N(graph).class_name(obj).select("id") for obj in obj_for_adding_states
    )  # type: ignore


def add_wallphone_states(
    state: Dict[str, Any],
    wallphone_ids: List[int],
    nodes_with_additional_states: Dict[int, Any],
):
    wallphone_cond = N(state).id_in(*wallphone_ids).state("ON").get_all()

    for n in wallphone_cond:
        n["states"].append("USED")
        nodes_with_additional_states[n["id"]] = n


def add_microwave_states(
    state: Dict[str, Any],
    microwave_ids: List[int],
    nodes_with_additional_states: Dict[int, Any],
):
    microwave_cond: List[int] = (
        N(state).id_in(*microwave_ids).state("ON").select("id")
    )  # type: ignore

    if len(microwave_cond) > 0:
        food_in_microwave: List[int] = (
            E(state).to_in(*microwave_cond).relation("INSIDE").select("from_id")
        )  # type: ignore
        food_in_microwave_cond = (
            N(state).id_in(*food_in_microwave).category("Food").get_all()
        )

        for n in food_in_microwave_cond:
            n["states"].append("HEATED")
            nodes_with_additional_states[n["id"]] = n


def add_stove_states(
    state: Dict[str, Any],
    stove_ids: List[int],
    fryingpan_ids: List[int],
    nodes_with_additional_states: Dict[int, Any],
):
    stove_cond: List[int] = (
        N(state).id_in(*stove_ids).state("ON").select("id")
    )  # type: ignore
    if len(stove_cond) > 0:
        # print("stove on")
        fryingpan_on_stove: List[int] = (
            E(state)
            .to_in(*stove_cond)
            .from_in(*fryingpan_ids)
            .relation("ON")
            .select("from_id")
        )  # type: ignore

        if len(fryingpan_on_stove) > 0:
            # print("pan on stove")
            food_in_fryingpan: List[int] = (
                E(state).to_in(*fryingpan_on_stove).relation("ON").select("from_id")
            )  # type: ignore
            food_in_fryingpan_cond = (
                N(state).id_in(*food_in_fryingpan).category("Food").get_all()
            )

            for n in food_in_fryingpan_cond:
                # print("food in pan")
                n["states"].append("HEATED")
                nodes_with_additional_states[n["id"]] = n


def add_washingmachine_states(
    state: Dict[str, Any],
    washingmachine_ids: List[int],
    nodes_with_additional_states: Dict[int, Any],
):
    washingmachine_cond: List[int] = (
        N(state).id_in(*washingmachine_ids).state("ON").select("id")
    )  # type: ignore

    if len(washingmachine_cond) > 0:
        cloth_in_washingmachine: List[int] = (
            E(state).to_in(*washingmachine_cond).relation("INSIDE").select("from_id")
        )  # type: ignore
        cloth_in_washingmachine_cond = (
            N(state).id_in(*cloth_in_washingmachine).get_all()
        )

        for n in cloth_in_washingmachine_cond:
            n["states"].append("WASHED")
            nodes_with_additional_states[n["id"]] = n


def _node_center(node: GraphNodeData) -> Point3D | None:
    bounding_box: Dict[str, Any] | None = node.get("bounding_box")
    if bounding_box is None:
        return None
    center: List[float] | Point3D | None = bounding_box.get("center")
    if center is None or len(center) != 3:
        return None
    return float(center[0]), float(center[1]), float(center[2])


def _matching_sink_faucet(
    state: Dict[str, Any], sink: GraphNodeData, faucet_ids: List[int]
) -> GraphNodeData | None:
    room_ids = [room["id"] for room in N(state).category("Rooms").get_all()]
    sink_room_ids = [
        edge["to_id"]
        for edge in E(state)
        .from_(sink["id"])
        .relation("INSIDE")
        .to_in(*room_ids)
        .get_all()
    ]
    same_room_faucet_ids = [
        edge["from_id"]
        for edge in E(state)
        .from_in(*faucet_ids)
        .relation("INSIDE")
        .to_in(*sink_room_ids)
        .get_all()
    ]
    candidates = N(state).id_in(*same_room_faucet_ids).get_all()
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    sink_center = _node_center(sink)
    if sink_center is None:
        return None
    distances: Dict[int, float] = {}
    for faucet in candidates:
        faucet_center = _node_center(faucet)
        if faucet_center is None:
            continue
        distances[faucet["id"]] = dist(sink_center, faucet_center)
    return min(
        (faucet for faucet in candidates if faucet["id"] in distances),
        key=lambda faucet: distances[faucet["id"]],
        default=None,
    )


def add_sink_states(
    state: Dict[str, Any],
    faucet_ids: List[int],
    sink_ids: List[int],
    nodes_with_additional_states: Dict[int, Any],
) -> None:
    sinks = N(state).id_in(*sink_ids).get_all()
    for sink in sinks:
        faucet = _matching_sink_faucet(state, sink, faucet_ids)
        if faucet is None or "ON" not in faucet["states"]:
            continue

        object_ids = [
            edge["from_id"]
            for edge in E(state).to_(sink["id"]).relation_in("INSIDE", "ON").get_all()
        ]
        objects = N(state).id_in(*object_ids).get_all()
        for node in objects:
            if "WASHED" not in node["states"]:
                node["states"].append("WASHED")
            nodes_with_additional_states[node["id"]] = node


# Adapated from https://github.com/NVlabs/progprompt-vh/blob/main/scripts/utils_aug_env.py#L24
def add_additional_obj_states(
    state: Dict[str, Any],
    ids: Tuple[List[int], ...],
    nodes_with_additional_states: Dict[int, Any],
) -> Dict[int, Any]:
    ## TODO fix faucet, stove, washingmachine
    (
        wallphone_ids,
        microwave_ids,
        stove_ids,
        fryingpan_ids,
        washingmachine_ids,
        sink_ids,
        faucet_ids,
    ) = ids

    add_wallphone_states(state, wallphone_ids, nodes_with_additional_states)
    add_microwave_states(state, microwave_ids, nodes_with_additional_states)
    add_stove_states(state, stove_ids, fryingpan_ids, nodes_with_additional_states)
    add_washingmachine_states(state, washingmachine_ids, nodes_with_additional_states)
    add_sink_states(state, faucet_ids, sink_ids, nodes_with_additional_states)

    return nodes_with_additional_states
