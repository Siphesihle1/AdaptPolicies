import json
import os

from ai2thor.server import Event
from env.thor_env import ThorEnv

from typing import Dict, List, Any, Optional

ALFRED_DATA_DIR = os.environ["ALFRED_DATA"]
ALFRED_DATASET = f"{ALFRED_DATA_DIR}/json_2.1.0"
SPLITS_FILE = f"{ALFRED_DATA_DIR}/splits/oct21.json"


class AlfredThorEnv(ThorEnv):
    def __init__(self, headless: bool, x_display: Optional[str] = None):
        super().__init__(
            player_screen_height=600,
            player_screen_width=600,
            headless=headless,
            x_display=x_display or "0",
        )

        self.task_counter = 0
        self.tasks: List[Dict[str, Any]] = []
        self.current_task: Optional[Dict[str, Any]] = None
        self.current_task_annon: Optional[Dict[str, Any]] = None
        self.initial_event: Optional[Event] = None

        self.load_tasks()

    def load_json_data(self, path: str) -> Dict[str, List[Dict[str, Any]]]:
        json_path = os.path.join(path)
        with open(json_path) as f:
            data = json.load(f)
        return data

    def load_tasks_json(
        self, split: str, tasks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        return [
            {
                **task,
                **self.load_json_data(
                    os.path.join(ALFRED_DATASET, split, task["task"], "traj_data.json")
                ),
            }
            for task in tasks
        ]

    def load_tasks(self):
        # Load splits
        splits = self.load_json_data(SPLITS_FILE)
        self.tasks = [
            *self.load_tasks_json("tests_seen", splits["tests_seen"]),
            *self.load_tasks_json("tests_unseen", splits["tests_unseen"]),
        ]
        print("Number of tasks: %s" % len(self.tasks))

    def load_scene_from_task(self, task: Dict[str, Any]):
        # scene setup
        scene_num = task["scene"]["scene_num"]
        object_poses = task["scene"]["object_poses"]
        dirty_and_empty = task["scene"]["dirty_and_empty"]
        object_toggles = task["scene"]["object_toggles"]
        r_idx = task["repeat_idx"]

        scene_name = "FloorPlan%d" % scene_num

        # initialize to start position
        self.reset(scene_name)
        self.restore_scene(object_poses, object_toggles, dirty_and_empty)
        self.initial_event = self.step(dict(task["scene"]["init_action"]))

        self.current_task = task
        self.current_task_annon = task["turk_annotations"]["anns"][r_idx]

        if self.current_task_annon:
            print("Task: %s" % self.current_task_annon["task_desc"])

    def load_next_task_scene(self):
        if self.task_counter == len(self.tasks) - 1:
            return None

        task = self.tasks[self.task_counter]
        self.load_scene_from_task(task)
        self.task_counter += 1

        return task
