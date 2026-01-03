import os
from PIL import Image
from alfred_thor_env import AlfredThorEnv

env = AlfredThorEnv(headless=True)
task = env.load_next_task_scene()
env.stop()

if env.initial_event is not None:
    cv2img = env.initial_event.cv2img
    pil_img = Image.fromarray(cv2img)
    pil_img.save(f"{os.getenv('JOB_OUTPUT_DIR')}/initial_scene.png")
