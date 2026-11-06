import unittest

from virtual_home.utils import add_washingmachine_states


class WasherStateTests(unittest.TestCase):
    def graph(self, states, relation="INSIDE"):
        return {
            "nodes": [
                {"id": 1, "class_name": "washingmachine", "states": states},
                {"id": 2, "class_name": "clothespile", "states": ["CLOSED"]},
            ],
            "edges": [{"from_id": 2, "relation_type": relation, "to_id": 1}],
        }

    def test_repeated_updates_mark_contained_clothes_once(self):
        graph = self.graph(["CLOSED", "ON"])
        derived = {}
        for _ in range(3):
            add_washingmachine_states(graph, [1], derived)
        self.assertEqual(graph["nodes"][1]["states"], ["CLOSED", "WASHED"])
        self.assertEqual(derived[2]["states"], ["CLOSED", "WASHED"])

    def test_open_or_unpowered_washer_does_not_wash(self):
        for states in (["OPEN", "ON"], ["CLOSED", "OFF"], ["ON"], []):
            with self.subTest(states=states):
                graph = self.graph(states)
                derived = {}
                add_washingmachine_states(graph, [1], derived)
                self.assertEqual(derived, {})
                self.assertEqual(graph["nodes"][1]["states"], ["CLOSED"])

    def test_surface_contact_or_another_washer_does_not_wash(self):
        for relation, washer_ids in (("ON", [1]), ("INSIDE", [99])):
            with self.subTest(relation=relation, washer_ids=washer_ids):
                graph = self.graph(["CLOSED", "ON"], relation)
                derived = {}
                add_washingmachine_states(graph, washer_ids, derived)
                self.assertEqual(derived, {})
