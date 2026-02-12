import os
from pathlib import Path
from methods.parser import (
    Parser,
    CommentTaskParser,
    FunctionParser,
    IndentationParser,
    StatementParser,
    AssertParser,
)
from .constants import (
    EXEC_TASK_FUNCTION,
    ACTION_INIT,
    ENVIRONMENT_INIT,
    EXPORTS,
    IMPORTS,
    INITIAL_ROOM,
    MAX_STEPS,
    TASK_INIT,
)

from typing import Dict, List, Tuple, Any
from pathlib import Path
from importlib import import_module

from cv2.typing import MatLike


def extract_plan_artifacts(plan: str):
    parser = Parser(
        [
            FunctionParser(
                IndentationParser(
                    [CommentTaskParser(), AssertParser(), StatementParser()]
                )
            )
        ]
    )

    if any(token in plan for token in ["__", "import"]):
        raise ValueError("Invalid plan: contains forbidden substrings.")

    parser.parse(plan)

    parsed_code, function_artifacts = parser.emit()
    subtasks, actions = function_artifacts[0]

    return parsed_code, subtasks, actions


def create_subtasks_file(subtasks: List[str], subtasks_path: str):
    with open(subtasks_path, "w") as f:
        f.write("SUBTASKS = [\n")
        for subtask in subtasks:
            f.write(f'    "{subtask}",\n')
        f.write("]\n")


def create_task_script_file(
    task_instruction: str, parsed_code: str, actions: List[str], task_script_path: str
):
    with open(task_script_path, "w") as f:
        for action in actions + ["env", "task"]:
            f.write(f"from .task_imports import {action}\n")
        f.write("\n\n")

        f.write(f"{parsed_code}\n\n")

        f.write(f"{EXEC_TASK_FUNCTION(task_instruction)}")


def create_script_files(
    task_instruction: str,
    task_import_code: str,
    plan_artifacts: Tuple[str, List[str], List[str]],
    prefix: str,
):
    task_dir = f"{prefix}/{task_instruction}"
    task_script_path = f"{task_dir}/task.py"
    subtasks_path = f"{task_dir}/subtasks.py"
    task_imports_path = f"{task_dir}/task_imports.py"

    os.makedirs(task_dir, exist_ok=True)
    tasks_module_init_file = Path(f"{task_dir}/__init__.py")
    tasks_module_init_file.touch(exist_ok=True)

    parsed_code, subtasks, actions = plan_artifacts

    create_subtasks_file(subtasks, subtasks_path)

    with open(task_imports_path, "w") as f:
        f.write(task_import_code)

    create_task_script_file(task_instruction, parsed_code, actions, task_script_path)


def prepare_task_scripts(
    task_instruction: str,
    thread_id: str,
    plan: str,
    env_id: int,
    log_file_prefix: str,
    task_scripts_prefix: str,
):
    task_imports_code = "".join(
        [
            IMPORTS,
            TASK_INIT(task_instruction, thread_id, MAX_STEPS),
            ENVIRONMENT_INIT(env_id, INITIAL_ROOM, log_file_prefix),
            ACTION_INIT,
            EXPORTS,
        ]
    ).strip()

    try:
        plan_artifacts = extract_plan_artifacts(plan)
    except Exception as e:
        return (False, f"Error parsing plan for task '{task_instruction}': {e}")

    create_script_files(
        task_instruction,
        task_imports_code,
        plan_artifacts,
        task_scripts_prefix,
    )

    return (True, f"Task scripts for '{task_instruction}' created successfully.")


def generate_task_scripts(
    log_file_prefix: str,
    task_scripts_prefix: str,
    task_instruction: str,
    thread_id: str,
    plan: str,
    env_id: int,
):
    # Create necessary directories and files
    os.makedirs(log_file_prefix, exist_ok=True)
    os.makedirs(task_scripts_prefix, exist_ok=True)

    tasks_module_init_file = Path(f"{task_scripts_prefix}/__init__.py")
    tasks_module_init_file.touch(exist_ok=True)

    # Prepare task scripts
    success, message = prepare_task_scripts(
        task_instruction, thread_id, plan, env_id, log_file_prefix, task_scripts_prefix
    )

    if not success:
        with open(f"{log_file_prefix}/task_logs.txt", "a") as f:
            f.write(f"{message}\n")

    return success


def exec_task(
    task_instruction: str, log_file_prefix: str
) -> Tuple[Dict[str, Any], Dict[str, Any], float, List[MatLike]] | None:
    # Assuming the system path contains the tasks module
    task_module = import_module(f"tasks.{task_instruction}.task")

    if hasattr(task_module, "exec_task"):
        with open(f"{log_file_prefix}/task_logs.txt", "a") as f:
            f.write(f"----Executing task: {task_instruction}----\n")

        try:
            return task_module.exec_task()
        except Exception as e:
            with open(f"{log_file_prefix}/task_logs.txt", "a") as f:
                f.write(f"----Error executing task {task_instruction}: {str(e)}\n")

    return None
