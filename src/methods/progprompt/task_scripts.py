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

from typing import List, Tuple


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
            f.write(f"    '{subtask}',\n")
        f.write("]\n")


def create_task_script_file(
    task_instruction: str, parsed_code: str, actions: List[str], task_script_path: str
):
    with open(task_script_path, "w") as f:
        for action in actions + ["env", "task"]:
            f.write(f"from task_imports import {action}\n")
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
    plan: str,
    env_id: int,
    log_file_prefix: str,
    task_scripts_prefix: str,
):
    task_imports_code = "".join(
        [
            IMPORTS,
            TASK_INIT(task_instruction, MAX_STEPS),
            ENVIRONMENT_INIT(env_id, INITIAL_ROOM, task_instruction, log_file_prefix),
            ACTION_INIT,
            EXPORTS,
        ]
    ).strip()

    try:
        plan_artifacts = extract_plan_artifacts(plan)
    except ValueError as e:
        return (False, f"Error processing plan for task '{task_instruction}': {e}")

    create_script_files(
        task_instruction,
        task_imports_code,
        plan_artifacts,
        task_scripts_prefix,
    )

    return (True, f"Task scripts for '{task_instruction}' created successfully.")
