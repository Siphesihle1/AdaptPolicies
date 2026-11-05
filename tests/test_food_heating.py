import unittest

from virtual_home.utils import add_stove_states, add_toaster_states


class FoodHeatingTests(unittest.TestCase):
    def graph(self, appliance="toaster", active=True, relation="ON"):
        return {
            "nodes": [
                {
                    "id": 1,
                    "class_name": appliance,
                    "category": "Appliances",
                    "states": ["ON" if active else "OFF"],
                    "properties": [],
                },
                {
                    "id": 2,
                    "class_name": "breadslice",
                    "category": "Props",
                    "states": [],
                    "properties": ["EATABLE"],
                },
                {
                    "id": 3,
                    "class_name": "plate",
                    "category": "Props",
                    "states": [],
                    "properties": [],
                },
                {
                    "id": 4,
                    "class_name": "fryingpan",
                    "category": "Props",
                    "states": [],
                    "properties": [],
                },
            ],
            "edges": [
                {"from_id": 2, "relation_type": relation, "to_id": 1},
                {"from_id": 3, "relation_type": relation, "to_id": 1},
            ],
        }

    def test_toaster_heats_edible_props_only_once(self):
        for relation in ("ON", "INSIDE"):
            with self.subTest(relation=relation):
                graph = self.graph(relation=relation)
                derived = {}
                add_toaster_states(graph, derived)
                add_toaster_states(graph, derived)
                self.assertEqual(derived[2]["states"], ["HEATED"])
                self.assertNotIn(3, derived)

    def test_off_or_unrelated_appliance_does_not_heat(self):
        for graph in (self.graph(active=False), self.graph(appliance="coffeemaker")):
            derived = {}
            add_toaster_states(graph, derived)
            self.assertEqual(derived, {})

    def test_only_supplied_graph_and_appliance_placement_are_used(self):
        for graph in ({"nodes": [], "edges": []}, self.graph(relation="CLOSE")):
            derived = {}
            add_toaster_states(graph, derived)
            self.assertEqual(derived, {})

    def test_stove_heats_edible_props_on_its_pan(self):
        graph = self.graph(appliance="stove")
        graph["edges"] = [
            {"from_id": 4, "relation_type": "ON", "to_id": 1},
            {"from_id": 2, "relation_type": "ON", "to_id": 4},
        ]
        derived = {}
        add_stove_states(graph, [1], [4], derived)
        add_stove_states(graph, [1], [4], derived)
        self.assertEqual(derived[2]["states"], ["HEATED"])

    def test_stove_does_not_heat_when_off_or_pan_is_elsewhere(self):
        for active in (False, True):
            graph = self.graph(appliance="stove", active=active)
            derived = {}
            add_stove_states(graph, [1], [4], derived)
            self.assertEqual(derived, {})
