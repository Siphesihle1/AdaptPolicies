import unittest

from virtual_home.visibility import get_visible_graph


def node(identifier, name, properties=(), states=(), category="Objects"):
    return {
        "id": identifier,
        "class_name": name,
        "category": category,
        "properties": list(properties),
        "states": list(states),
    }


def inside(child, parent):
    return {"from_id": child, "to_id": parent, "relation_type": "INSIDE"}


class VisibilityTests(unittest.TestCase):
    def graph(self, container, contents):
        return {
            "nodes": [
                node(1, "character", category="Characters"),
                node(2, "bedroom", category="Rooms"),
                container,
                *contents,
            ],
            "edges": [
                inside(1, 2),
                inside(3, 2),
                *[inside(n["id"], 3) for n in contents],
            ],
        }

    def test_non_openable_bookshelf_contents_are_visible(self):
        graph = self.graph(
            node(3, "bookshelf", ("CONTAINERS",)),
            [node(4, "folder", ("CAN_OPEN",), ("CLOSED",))],
        )
        self.assertEqual(
            {n["id"] for n in get_visible_graph(graph, 1)["nodes"]}, {1, 2, 3, 4}
        )

    def test_closed_or_unknown_openable_container_hides_contents(self):
        for states in (("CLOSED",), ()):
            graph = self.graph(
                node(3, "cabinet", ("CAN_OPEN",), states), [node(4, "folder")]
            )
            visible = get_visible_graph(graph, 1)
            self.assertNotIn(4, {n["id"] for n in visible["nodes"]})
            self.assertFalse(
                any(e["from_id"] == 4 or e["to_id"] == 4 for e in visible["edges"])
            )

    def test_closed_ancestor_hides_contents_of_an_open_access_bowl(self):
        graph = self.graph(
            node(3, "fridge", ("CAN_OPEN",), ("CLOSED",)), [node(4, "dishbowl")]
        )
        graph["nodes"].append(node(5, "apple"))
        graph["edges"].extend([inside(5, 4), inside(5, 2)])
        self.assertNotIn(5, {n["id"] for n in get_visible_graph(graph, 1)["nodes"]})
        graph["nodes"][2]["states"] = ["OPEN"]
        self.assertIn(5, {n["id"] for n in get_visible_graph(graph, 1)["nodes"]})

    def test_held_object_is_visible_without_a_room_edge(self):
        graph = self.graph(node(3, "bookshelf"), [])
        graph["nodes"].append(node(4, "book"))
        graph["edges"].append({"from_id": 1, "to_id": 4, "relation_type": "HOLDS_RH"})
        self.assertIn(4, {n["id"] for n in get_visible_graph(graph, 1)["nodes"]})
