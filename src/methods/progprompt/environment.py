from io import TextIOWrapper
from typing import Dict, List, Tuple
from virtual_home.task import VHTask
from typing_extensions import override
from virtual_home.graph_query import E, N
from virtual_home.environment import VHEnvironment


class ProgPromptEnvironment(VHEnvironment):
    def __init__(
        self, env_id: int, initial_room: str, task: VHTask, log_file: TextIOWrapper
    ):
        self.objs = ""
        self.actions_to_omit = [("grab", "wallphone")]
        super().__init__(env_id, initial_room, task, log_file)

    @override
    def get_current_state(self):
        # Adapated from https://github.com/NVlabs/progprompt-vh/blob/main/scripts/utils_execute.py
        super().get_current_state()

        if self.time_step > 1:
            obj_ids: Dict[int, str] = dict(
                N(self.graph)
                .id_in(*self.obj_ids_close)
                .class_name_not(self.agent_in_room)
                .select("id", "class_name")
            )
            relations_to_exclude = ["CLOSE", "FACING", "INSIDE"]
        else:
            obj_ids: Dict[int, str] = dict(
                N(self.graph)
                .id_in(*self.obj_ids_close)
                .class_name_in(*self.obj_close)
                .select("id", "class_name")
            )
            relations_to_exclude = ["CLOSE", "FACING"]

        relations = list(
            set(
                [
                    " ".join(
                        [obj_ids[e["from_id"]], e["relation_type"], obj_ids[e["to_id"]]]
                    )
                    for e in E(self.graph)
                    .from_in(*obj_ids.keys())
                    .to_in(*obj_ids.keys())
                    .relation_not_in(*relations_to_exclude)
                    .get_all()
                ]
            )
        )
        obj_states: List[Tuple[str, List[str]]] = (
            N(self.graph).class_name_in(*self.obj_close).select("class_name", "states")
        )

        objs = ""

        for class_name, states in obj_states:
            if len(states) > 0:
                objs = objs + class_name + " is " + " and ".join(states) + ", "
            else:
                objs = objs + class_name + ", "

        objs = list(set(objs.split(", ")))
        objs = [ob for ob in objs if len(ob) > 0]
        objs = (
            ", ".join(objs)
            + (", " if len(objs) > 0 and len(relations) > 0 else "")
            + ", ".join(relations)
            + (". " if len(relations) > 0 else "")
        )

        if len(self.objs_in_hand) > 0:
            objs += f"You have {', '.join(self.objs_in_hand)}{'.' if len(self.objs_in_hand) > 0 else ''}"

        self.objs = objs

        self.log_file.write(
            f"\n----\n Current state (step: {self.task.step}, subtask: {self.task.current_subtask}): {self.objs} \n----\n"
        )
        self.log_file.write(f"Agent in room: {self.agent_in_room}\n")
