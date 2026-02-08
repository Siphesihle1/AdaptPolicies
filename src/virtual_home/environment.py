from io import TextIOWrapper
import os
from typing import List, Optional, Tuple
import cv2
from cv2.typing import MatLike
import weave
from .graph_query import N, E
from .task import VHTask
from virtualhome.simulation.unity_simulator import UnityCommunication
from virtualhome.simulation.evolving_graph import utils
from virtualhome.simulation.evolving_graph.scripts import parse_script_line, Script
from virtualhome.simulation.evolving_graph.execution import ScriptExecutor
from virtualhome.simulation.evolving_graph.environment import (
    EnvironmentGraph,
    EnvironmentState,
)
from .utils import add_additional_obj_states, get_obj_ids_for_adding_states

from PIL import Image


class VHEnvironment:
    def __init__(
        self, env_id: int, initial_room: str, task: VHTask, log_file: TextIOWrapper
    ):
        self.env_id = env_id
        self.comm = UnityCommunication(
            file_name=None, port=os.getenv("SIM_PORT", "8082")
        )
        self.images: List[MatLike] = []
        self.time_step = 0
        self.nodes_with_additonal_states = {}
        self.task = task
        self.actions_to_omit: List[Tuple[str, ...]] = []
        self.log_file = log_file
        self.found_id: Optional[int] = None
        self.last_action: Tuple[str, ...] = tuple()

        self.comm.reset(self.env_id)
        self.comm.add_character("Chars/Male2", initial_room=initial_room)
        _, self.graph = self.comm.environment_graph()

        self.get_current_state()
        _, camera_count = self.comm.camera_count()
        _, im = self.comm.camera_image(
            [camera_count - 5], image_width=300, image_height=300
        )
        self.images.append(im[0])

        self.initial_state = self.graph

        self.obj_ids_for_adding_states = get_obj_ids_for_adding_states(self.graph)

        self.initilialize_executor()

    def initilialize_executor(self):
        env_graph = EnvironmentGraph(self.graph)
        name_equivalence = utils.load_name_equivalence()
        self.executor = ScriptExecutor(env_graph, name_equivalence)

    def get_current_state(self):
        agent = N(self.graph).class_name("character").get_first()

        if agent is None:
            return

        self.agent: str = agent["id"]

        self.obj_ids_in_hand: List[int] = (  # type: ignore
            E(self.graph)
            .from_(self.agent)
            .relation_in("HOLDS_LH", "HOLDS_RH")
            .select("to_id")
        )

        agent_in_roomid = E(self.graph).from_(self.agent).relation("INSIDE").get_first()

        if agent_in_roomid is not None:
            self.agent_in_roomid: int = agent_in_roomid["to_id"]

            agent_in_room = N(self.graph).id(self.agent_in_roomid).get_first()

            if agent_in_room is not None:
                self.agent_in_room: str = agent_in_room["class_name"]

        self.objs_in_hand: List[str] = (  # type: ignore
            N(self.graph).id_in(*self.obj_ids_in_hand).select("class_name")
        )
        self.obj_ids_close: List[int] = (  # type: ignore
            E(self.graph).from_(self.agent).relation("CLOSE").select("to_id")
        )

        self.partial_graph = utils.get_visible_nodes(self.graph, agent_id=self.agent)
        self.obj_close: List[str] = (  # type: ignore
            N(self.partial_graph).id_in(*self.obj_ids_close).select("class_name")
        )

    def find_obj(self, class_name: str) -> List[int]:
        return N(self.graph).class_name(class_name).select("id")  # type: ignore

    def update_executor(self, state: EnvironmentState):
        self.graph = state.to_dict()
        env_graph = EnvironmentGraph(self.graph)
        name_equivalence = utils.load_name_equivalence()
        self.executor = ScriptExecutor(env_graph, name_equivalence)

    @weave.op
    def get_observation(self):
        last_action_name = self.last_action[0]
        _, camera_count = self.comm.camera_count()

        if last_action_name in ["grab", "open", "close"]:
            _, im = self.comm.camera_image(
                [camera_count - 5], image_width=300, image_height=300
            )
        else:
            _, im = self.comm.camera_image(
                [camera_count - 6], image_width=300, image_height=300
            )

        self.images.append(im[0])

        images_dir = (
            f"{os.getenv('JOB_OUTPUT_DIR')}/task_images/{self.task.task_instruction}"
        )
        os.makedirs(images_dir, exist_ok=True)
        img_path = f"{images_dir}/step_{len(self.images) + 1}.png"
        cv2.imwrite(img_path, im[0])

        return Image.open(img_path)

    def execute(self, script_instruction: str):
        # Adapted from https://github.com/NVlabs/progprompt-vh/blob/main/scripts/utils_execute.py#L224
        self.log_file.write(f"{script_instruction}\n")
        self.comm.render_script(
            [script_instruction],
            recording=False,
            skip_animation=True,
            find_solution=True,
        )
        script = script_instruction[7:]
        self.task.step += 1

        try:
            script = parse_script_line(script, 0)
        except:
            self.log_file.write(
                f"act_success: False, message: Failed to parse script line {script}\n"
            )
            return False

        success, final_state, _ = self.executor.execute(Script([script]))

        if not success:
            self.log_file.write(
                f"act_success: False, message: {self.executor.info.get_error_string()}\n"
            )
            return False

        self.task.executable_steps += 1

        self.update_executor(final_state)

        with weave.thread(thread_id=self.task.thread_id):
            self.get_observation()

        self.get_current_state()

        self.nodes_with_additonal_states = add_additional_obj_states(
            self.partial_graph,
            self.obj_ids_for_adding_states,
            self.nodes_with_additonal_states,
        )

        return True
