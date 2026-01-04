import os
from PIL import Image
from alfred_thor_env import AlfredThorEnv

x_display = os.getenv("DISPLAY") or ":0"
env = AlfredThorEnv(headless=False, x_display=x_display[1:])
task = env.load_next_task_scene()
env.stop()

if env.initial_event is not None:
    cv2img = env.initial_event.cv2img
    pil_img = Image.fromarray(cv2img)
    pil_img.save(f"{os.getenv('JOB_OUTPUT_DIR')}/initial_scene.png")
