from methods.progprompt.constants import TASK_PROMPT_ACTION_IMPORTS
from methods.progprompt.prompt import PromptBuilder


# Execute the generated task script
# sys.path.insert(0, os.getenv("JOB_OUTPUT_DIR", ""))
# invalidate_caches()
#

builder = (
    PromptBuilder(env_id=0)
    .with_imports([TASK_PROMPT_ACTION_IMPORTS])
    .with_objects()
    .with_examples("default")
    .with_tasks("test_seen")
)

for prompt in builder:
    print("=== Env 0 ===")
    print("=== Task Instruction ===")
    print(prompt.task_instruction)
    print("=== Prompt ===")
    print(prompt.text)
    print("=" * 80 + "\n")

builder = (
    PromptBuilder(env_id=1)
    .with_imports([TASK_PROMPT_ACTION_IMPORTS])
    .with_objects()
    .with_examples("default")
    .with_tasks()
)

for prompt in builder:
    print("=== Env 1 ===")
    print("=== Task Instruction ===")
    print(prompt.task_instruction)
    print("=== Prompt ===")
    print(prompt.text)
    print("=" * 80 + "\n")

builder = (
    PromptBuilder(env_id=2)
    .with_imports([TASK_PROMPT_ACTION_IMPORTS])
    .with_objects()
    .with_examples("default")
    .with_tasks()
)

for prompt in builder:
    print("=== Env 2 ===")
    print("=== Task Instruction ===")
    print(prompt.task_instruction)
    print("=== Prompt ===")
    print(prompt.text)
    print("=" * 80 + "\n")
