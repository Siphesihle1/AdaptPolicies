from typing import Callable, Dict, Any, List, Tuple

Predicate = Callable[[Dict[str, Any]], bool]


class NodeQuery:
    def __init__(self, graph: Dict[str, Any]):
        self.predicates: List[Predicate] = []
        self.nodes = graph["nodes"]

    def id(self, node_id: int):
        self.predicates.append(lambda n: n["id"] == node_id)
        return self

    def id_not(self, node_id: int):
        self.predicates.append(lambda n: n["id"] != node_id)
        return self

    def id_in(self, *node_ids: int):
        self.predicates.append(lambda n: n["id"] in node_ids)
        return self

    def category(self, category: str):
        self.predicates.append(lambda n: n["category"] == category)
        return self

    def category_not(self, category: str):
        self.predicates.append(lambda n: n["category"] != category)
        return self

    def category_in(self, *categories: str):
        self.predicates.append(lambda n: n["category"] in categories)
        return self

    def class_name(self, class_name: str):
        self.predicates.append(lambda n: n["class_name"] == class_name)
        return self

    def class_name_not(self, class_name: str):
        self.predicates.append(lambda n: n["class_name"] != class_name)
        return self

    def class_name_in(self, *class_names: str):
        self.predicates.append(lambda n: n["class_name"] in class_names)
        return self

    def state(self, *state: str):
        state_set = set(state)
        self.predicates.append(
            lambda n: len(state_set.intersection(set(n["states"]))) > 0
        )
        return self

    def select(self, *fields: str) -> List[Tuple[Any, ...]] | List[Any]:
        selected_fields = [
            [n[field] for n in self.nodes if all(pred(n) for pred in self.predicates)]
            for field in fields
        ]

        if len(fields) > 1:
            return list(zip(*(field for field in selected_fields)))

        return selected_fields[0]

    def get_all(self):
        return [n for n in self.nodes if all(pred(n) for pred in self.predicates)]

    def get_first(self):
        result = [n for n in self.nodes if all(pred(n) for pred in self.predicates)]
        return result[0] if len(result) > 0 else None

    def exists(self) -> bool:
        return any(all(pred(n) for pred in self.predicates) for n in self.nodes)


def N(graph: Dict[str, Any]):
    return NodeQuery(graph)


class RelationQuery:
    def __init__(self, graph: Dict[str, Any]):
        self.graph = graph
        self.edges = graph["edges"]
        self.predicates: List[Predicate] = []
        self.nodes = graph["nodes"]

    def from_(self, node_id: int):
        self.predicates.append(lambda e: e["from_id"] == node_id)
        return self

    def from_in(self, *node_ids: int):
        self.predicates.append(lambda e: e["from_id"] in node_ids)
        return self

    def to_(self, node_id: int):
        self.predicates.append(lambda e: e["to_id"] == node_id)
        return self

    def to_in(self, *node_ids: int):
        self.predicates.append(lambda e: e["to_id"] in node_ids)
        return self

    def from_node(self, fn: Callable[[Dict[str, Any]], bool]):
        self.predicates.append(
            lambda e, f=fn: f(N(self.graph).id(e["from_id"]).get_first())  # type: ignore
        )
        return self

    def to_node(self, fn: Callable[[Dict[str, Any]], bool]):
        self.predicates.append(
            lambda e, f=fn: f(N(self.graph).id(e["to_id"]).get_first())  # type: ignore
        )
        return self

    def relation(self, rel):
        self.predicates.append(lambda e: e["relation_type"] == rel)
        return self

    def relation_not(self, rel):
        self.predicates.append(lambda e: e["relation_type"] != rel)
        return self

    def relation_in(self, *rels: str):
        self.predicates.append(lambda e: e["relation_type"] in rels)
        return self

    def relation_not_in(self, *rels: str):
        self.predicates.append(lambda e: e["relation_type"] not in rels)
        return self

    def select(self, *fields: str) -> List[Tuple[Any, ...]] | List[Any]:
        selected_fields = [
            e[field]
            for e in self.edges
            if all(pred(e) for pred in self.predicates)
            for field in fields
        ]

        if len(fields) > 1:
            return list(zip(selected_fields))

        return selected_fields

    def get_all(self):
        return [e for e in self.edges if all(pred(e) for pred in self.predicates)]

    def get_first(self):
        return [n for n in self.edges if all(pred(n) for pred in self.predicates)][0]

    def exists(self) -> bool:
        return any(all(pred(e) for pred in self.predicates) for e in self.edges)


def E(graph: Dict[str, Any]):
    return RelationQuery(graph)


def has(prop: str, value=None):
    if value is None:
        return lambda n: prop in n
    return lambda n: n.get(prop) == value
