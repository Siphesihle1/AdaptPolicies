import io
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from methods.progprompt.environment import ProgPromptEnvironment
from virtual_home.environment import VHEnvironment


class VisibleObjectStatesTests(unittest.TestCase):
    def test_hidden_same_named_object_does_not_contradict_visible_state(self):
        for visible, hidden in (("OPEN", "CLOSED"), ("CLOSED", "OPEN")):
            with self.subTest(visible=visible):
                target = {"id": 3, "class_name": "folder", "states": [visible]}
                other = {"id": 4, "class_name": "folder", "states": [hidden]}
                env = ProgPromptEnvironment.__new__(ProgPromptEnvironment)
                env.graph = {"nodes": [target, other], "edges": []}
                env.partial_graph = {"nodes": [target], "edges": []}
                env.obj_ids_close = [3, 4]
                env.agent = 1
                env.obj_close = ["folder"]
                env.objs_in_hand = []
                env.agent_in_room = "bedroom"
                env.time_step = 0
                env.log_file = io.StringIO()
                env.task = SimpleNamespace(
                    step=1, current_subtask="open folder", thread_id="visible-folder"
                )
                with patch.object(VHEnvironment, "get_current_state"):
                    env.get_current_state()
                self.assertIn(f"folder is {visible}", env.objs)
                self.assertNotIn(f"folder is {hidden}", env.objs)
