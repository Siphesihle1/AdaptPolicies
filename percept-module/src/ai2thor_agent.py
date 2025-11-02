import json
import os
import sys

sys.path.append(os.environ['ALFRED_ROOT'])
sys.path.append(os.path.join(os.environ['ALFRED_ROOT'], 'gen'))
sys.path.append(os.path.join(os.environ['ALFRED_ROOT'], 'models'))

from env.thor_env import ThorEnv

ALFRED_DATA_DIR = os.environ['ALFRED_DATA']
ALFRED_DATASET = f"{ALFRED_DATA_DIR}/json_2.1.0"
SPLITS_FILE = f"{ALFRED_DATA_DIR}/splits/oct21.json"

def load_task_json(path):
    json_path = os.path.join(path)
    with open(json_path) as f:
        data = json.load(f)
    return data


def get_scene_metadata():
    
    # Load splits
    splits = load_task_json(SPLITS_FILE)
    seen_files, unseen_files = splits['tests_seen'], splits['tests_unseen']
    task = seen_files[0]

    traj_data = load_task_json(os.path.join(ALFRED_DATASET, 'tests_seen', task['task'], 'traj_data.json'))

    # scene setup
    scene_num = traj_data['scene']['scene_num']
    object_poses = traj_data['scene']['object_poses']
    dirty_and_empty = traj_data['scene']['dirty_and_empty']
    object_toggles = traj_data['scene']['object_toggles']
    r_idx = task['repeat_idx']

    scene_name = 'FloorPlan%d' % scene_num

    env = ThorEnv(player_screen_height=600, player_screen_width=600, headless=False)

    env.reset(scene_name)
    env.restore_scene(object_poses, object_toggles, dirty_and_empty)

    # initialize to start position
    print("Task: %s" % (traj_data['turk_annotations']['anns'][r_idx]['task_desc']))
    
    return (env, env.step(dict(traj_data['scene']['init_action'])))
