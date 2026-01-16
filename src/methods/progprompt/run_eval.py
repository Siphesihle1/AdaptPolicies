import json
import os
import cv2
import sys
import pkgutil
from pathlib import Path
from importlib import import_module, invalidate_caches
from types import ModuleType
from typing import Any, Dict, List, Tuple

from cv2.typing import MatLike

from methods.progprompt.task_scripts import prepare_task_scripts

plan = """
def put_salmon_in_microwave():
    # 1: grab salmon
    assert('close' to 'salmon')
        else: find('salmon')
    grab('salmon')
    # 2: put salmon in microwave
    assert('salmon' in 'hands' )
        else: find('salmon')
        else: grab('salmon')
    assert('close' to 'microwave' )
        else: find('microwave')
    assert('microwave' is 'opened')
        else: open('microwave')
    putin('salmon', 'microwave')
"""
env_id = 0
task_instruction = "put_salmon_in_microwave"
log_file_prefix = f"{os.getenv('JOB_OUTPUT_DIR')}/task_logs/{task_instruction}"
task_scripts_prefix = f"{os.getenv('JOB_OUTPUT_DIR')}/tasks"

# Create necessary directories and files
os.makedirs(log_file_prefix, exist_ok=True)
os.makedirs(task_scripts_prefix, exist_ok=True)

tasks_module_init_file = Path(f"{task_scripts_prefix}/__init__.py")
tasks_module_init_file.touch(exist_ok=True)

# Prepare task scripts
sucess, message = prepare_task_scripts(
    task_instruction, plan, env_id, log_file_prefix, task_scripts_prefix
)

if not sucess:
    raise RuntimeError(message)

print(message)

# Execute the generated task script
sys.path.insert(0, os.getenv("JOB_OUTPUT_DIR", ""))
invalidate_caches()


def run_exec_tasks(package: ModuleType):
    results: Dict[str, Tuple[Any, Any, float, List[MatLike]] | Exception] = {}

    for mod in pkgutil.iter_modules(package.__path__):
        module_name = f"{package.__name__}.{mod.name}.task"
        module = import_module(module_name)

        if hasattr(module, "exec_task"):
            try:
                results[module_name] = module.exec_task()
            except Exception as e:
                results[module_name] = e

    return results


with open(f"{log_file_prefix}/task_logs.txt", "w") as f:
    f.write(f"----Executing task: {task_instruction}----\n")

tasks_module = import_module("tasks")
results = run_exec_tasks(tasks_module)

# Retrieve and process results for the specific task
task_results = results.get(f"tasks.{task_instruction}.task", None)

if task_results is None:
    raise RuntimeError(f"No results found for task: {task_instruction}")

if isinstance(task_results, Exception):
    raise task_results

final_state, initial_state, success_rate, images = task_results

with open(f"{log_file_prefix}/task_logs.txt", "a") as f:
    f.write(f"\n----Task success rate: {success_rate}----\n")

with open(f"{log_file_prefix}/initial_state.json", "w") as f:
    json.dump(initial_state, f, indent=4)

with open(f"{log_file_prefix}/final_state.json", "w") as f:
    json.dump(final_state, f, indent=4)

# Store cv2 imges inside the output directory
images_dir = f"{os.getenv('JOB_OUTPUT_DIR')}/task_images/{task_instruction}"
os.makedirs(images_dir, exist_ok=True)

for idx, img in enumerate(images):
    img_path = f"{images_dir}/step_{idx + 1}.png"
    cv2.imwrite(img_path, img)
