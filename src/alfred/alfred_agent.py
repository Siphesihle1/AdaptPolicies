# %
from alfred.alfred_thor_env import AlfredThorEnv
from pprint import pprint

# %%
env = AlfredThorEnv(headless=False)
task = env.load_next_task_scene()
env.stop()

# %%
if env.initial_event is not None:
    metadata = env.initial_event.metadata
    objects = metadata["objects"]
    detected_objects = env.initial_event.instance_detections2D

    pprint(task)

    pprint([obj["objectId"] for obj in objects if obj["visible"]])
    pprint(f"Number of object in the scene: {len(objects)}")

    if detected_objects:
        pprint([*detected_objects.keys()])
        pprint(f"Number of detected objects: {len(detected_objects.keys())}")
# %%
