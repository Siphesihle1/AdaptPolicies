"""Room observations with access checks along every containment ancestor."""

from typing import Any

from .graph_query import E, N


def get_visible_graph(graph: dict[str, Any], agent_id: int) -> dict[str, Any]:
    nodes = {node["id"]: node for node in N(graph).get_all()}
    rooms: set[int] = {node["id"] for node in N(graph).category("Rooms").get_all()}
    current: list[int] = [
        edge["to_id"]
        for edge in E(graph).from_(agent_id).relation("INSIDE").to_in(*rooms).get_all()
    ]
    if len(current) != 1:
        raise ValueError("Visibility requires one character room")

    parents: dict[int, list[int]] = {}
    children: dict[int, list[int]] = {}
    for edge in E(graph).relation("INSIDE").get_all():
        parents.setdefault(edge["from_id"], []).append(edge["to_id"])
        children.setdefault(edge["to_id"], []).append(edge["from_id"])
    held: set[int] = {
        edge["to_id"]
        for edge in E(graph)
        .from_(agent_id)
        .relation_in("HOLDS_LH", "HOLDS_RH")
        .get_all()
    }
    candidates = set(current) | held
    pending = list(candidates)
    while pending:
        for child in children.get(pending.pop(), []):
            if child not in candidates:
                candidates.add(child)
                pending.append(child)

    def hidden(identifier: int) -> bool:
        pending = list(parents.get(identifier, []))
        visited = set()
        while pending:
            ancestor = pending.pop()
            if ancestor in rooms or ancestor in visited:
                continue
            visited.add(ancestor)
            container = nodes[ancestor]
            if "CAN_OPEN" in container.get(
                "properties", []
            ) and "OPEN" not in container.get("states", []):
                return True
            pending.extend(parents.get(ancestor, []))
        return False

    visible = (
        rooms
        | held
        | {identifier for identifier in candidates if not hidden(identifier)}
    )
    return {
        "nodes": N(graph).id_in(*visible).get_all(),
        "edges": E(graph).from_in(*visible).to_in(*visible).get_all(),
    }
