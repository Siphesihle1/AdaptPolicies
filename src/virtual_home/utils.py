from .graph_query import E, N

from typing import Dict, Any, List, Tuple


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
            E(state).to_in(*microwave_cond).relation("INSIDE").select("id")
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


def add_sink_states(
    state: Dict[str, Any],
    faucet_ids: List[int],
    sink_ids: List[int],
    nodes_with_additional_states: Dict[int, Any],
):
    faucet_near_sink: List[int] = (
        E(state).from_in(*faucet_ids).select("from_id")
    )  # type: ignore
    # and n["relation_type"] == "CLOSE"]

    faucet_cond: List[str] = (
        N(state).id_in(*faucet_near_sink).state("ON").select("id")
    )  # type: ignore
    # print(sink_ids, faucet_ids, faucet_near_sink, faucet_cond)

    if len(faucet_cond) > 0:
        # print("faucet on")
        utensil_in_sink: List[int] = (
            E(state).to_in(*sink_ids).relation("INSIDE").select("from_id")
        )  # type: ignore
        utensil_in_sink_cond = N(state).id_in(*utensil_in_sink).get_all()

        for n in utensil_in_sink_cond:
            # print("utensit in sink")
            n["states"].append("WASHED")
            nodes_with_additional_states[n["id"]] = n


# Adapated from https://github.com/NVlabs/progprompt-vh/blob/main/scripts/utils_aug_env.py#L24
def add_additional_obj_states(
    state: Dict[str, Any],
    ids: Tuple[List[int], ...],
    nodes_with_additional_states: Dict[int, Any],
):
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
