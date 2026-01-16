from io import TextIOWrapper
from task import VHTask
from typing_extensions import override
from graph_query import E, N
from virtual_home.environment import VHEnvironment


class ProgPromptEnvironment(VHEnvironment):
    def __init__(
        self, env_id: int, initial_room: str, task: VHTask, log_file: TextIOWrapper
    ):
        super().__init__(env_id, initial_room, task, log_file)

        self.objs = ""
        self.actions_to_omit = [("grab", "wallphone")]

    @override
    def get_current_state(self):
        # Adapated from https://github.com/NVlabs/progprompt-vh/blob/main/scripts/utils_execute.py
        super().get_current_state()

        if self.time_step > 1:
            obj_ids = dict(
                N(self.graph)
                .id_in(*self.obj_ids_close)
                .class_name_not(self.agent_in_room)
                .select("id", "class_name")
            )
            relations_to_exclude = ["CLOSE", "FACING", "INSIDE"]
        else:
            obj_ids = dict(
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
        obj_states = (
            N(self.graph).class_name_in(*self.obj_close).select("class_name", "states")
        )

        for states in obj_states:
            if len(states[1]) > 0:
                objs = self.objs + states[0] + " is " + " and ".join(states[1]) + ", "
            else:
                objs = self.objs + states[0] + ", "

        objs = list(set(self.objs.split(", ")))
        objs = [ob for ob in objs if len(ob) > 0]
        self.objs = ", ".join(objs) + ", " + ", ".join(relations) + ". "

        if len(self.agent_has_obj) > 0:
            self.objs += f" You have {', '.join(self.agent_has_obj)}. "
