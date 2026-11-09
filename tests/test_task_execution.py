from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from methods.progprompt import task_scripts
from methods.progprompt.constants import TASK_PROMPT_ACTION_IMPORTS, EXPORTS
from virtual_home.task import VHTask


class TaskExecutionTests(unittest.TestCase):
    def test_advertised_tool_actions_compile_with_their_runtime_signatures(self):
        advertised = TASK_PROMPT_ACTION_IMPORTS.removeprefix(
            "from actions import "
        ).split(", ")
        self.assertIn("apply <obj> <obj>", advertised)
        self.assertIn("use <obj>", advertised)
        exports = {}
        exec(EXPORTS, exports)
        self.assertIn("apply", exports["__all__"])
        self.assertIn("use", exports["__all__"])
        code, _, actions = task_scripts.extract_plan_artifacts(
            "def brush_teeth():\n"
            "    # 0 Prepare brush\n"
            "    apply('toothpaste', 'toothbrush')\n"
            "    # 1 Brush teeth\n"
            "    use('toothbrush')\n"
            "    # 2 Done\n"
        )
        compile(code, "<tool-plan>", "exec")
        self.assertIn("apply", actions)
        self.assertIn("use", actions)

    def test_zero_action_task_retains_final_state_with_zero_executability(self):
        task = VHTask("empty", "thread", ["done"])
        graph = {"nodes": [], "edges": []}
        with TemporaryDirectory() as directory:
            env = SimpleNamespace(
                graph=graph,
                initial_state=graph,
                nodes_with_additonal_states={},
                images=[],
                log_file=(Path(directory) / "task.log").open("w"),
            )
            final, initial, executable, _ = task.finish(env)
            self.assertEqual(final, graph)
            self.assertEqual(initial, graph)
            self.assertEqual(executable, 0)

    def test_invalid_action_import_does_not_prevent_next_task(self):
        result = ({"nodes": []}, {"nodes": []}, 1.0, [])
        with TemporaryDirectory() as directory, patch.object(
            task_scripts,
            "import_module",
            side_effect=[
                ImportError("cannot import name 'wash'"),
                SimpleNamespace(exec_task=lambda: result),
            ],
        ):
            self.assertIsNone(task_scripts.exec_task("invalid_plan", directory))
            self.assertEqual(task_scripts.exec_task("next_task", directory), result)
            log = (Path(directory) / "task_logs.txt").read_text()
            self.assertIn("Error executing task invalid_plan", log)
            self.assertIn("cannot import name 'wash'", log)


if __name__ == "__main__":
    unittest.main()
