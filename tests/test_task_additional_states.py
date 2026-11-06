import io
import unittest
from types import SimpleNamespace

from virtual_home.task import VHTask


class TaskAdditionalStateTests(unittest.TestCase):
    def finish(self, states, cached_states):
        graph = {
            "nodes": [
                {
                    "id": 2,
                    "class_name": "rug",
                    "states": states,
                    "bounding_box": {"center": [1, 0, 2]},
                }
            ],
            "edges": [],
        }
        env = SimpleNamespace(
            graph=graph,
            initial_state={"nodes": [], "edges": []},
            nodes_with_additonal_states={
                2: {
                    "id": 2,
                    "class_name": "rug",
                    "states": cached_states,
                    "bounding_box": {"center": [9, 9, 9]},
                }
            },
            log_file=io.StringIO(),
            images=[],
        )
        task = VHTask("wash_rug", "test", ["wash"])
        task.total_steps = task.executable_steps = 1
        return task.finish(env)[0], graph

    def test_washing_does_not_restore_folded_state_or_old_geometry(self):
        final, original = self.finish(["UNFOLDED"], ["FOLDED", "WASHED"])
        self.assertEqual(final["nodes"][0]["states"], ["UNFOLDED", "WASHED"])
        self.assertEqual(final["nodes"][0]["bounding_box"], {"center": [1, 0, 2]})
        self.assertEqual(original["nodes"][0]["states"], ["UNFOLDED"])

    def test_derived_effects_persist_once_without_reverting_current_switch_states(self):
        final, _ = self.finish(
            ["OFF", "OPEN", "HEATED"],
            ["ON", "CLOSED", "USED", "HEATED", "WASHED", "WASHED"],
        )
        self.assertEqual(
            final["nodes"][0]["states"], ["OFF", "OPEN", "HEATED", "USED", "WASHED"]
        )
