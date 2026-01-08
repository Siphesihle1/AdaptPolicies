# %%

import os
import IPython.display
import glob
from sys import platform
import sys
from PIL import Image
import matplotlib.pyplot as plt
from tqdm import tqdm
from typing import Optional

import virtualhome
from unity_simulator.comm_unity import UnityCommunication
from unity_simulator import utils_viz

from demo.utils_demo import (
    get_scene_cameras,
    display_grid_img,
)

# %%

comm: Optional[UnityCommunication] = None

# if platform == "darwin":
#     exec_file = f"{os.getenv('VIRTUALHOME_ROOT')}/simulation/macos_exec.*{os.getenv('SIM_VERSION_NUMBER')}*"
# else:
#     exec_file = f"{os.getenv('VIRTUALHOME_ROOT')}/simulation/linux_exec*{os.getenv('SIM_VERSION_NUMBER')}.x86_64"
#
# file_names = glob.glob(exec_file)
# if len(file_names) > 0:
#     file_name = file_names[0]
comm = UnityCommunication(port="8082")
# else:
#     print("Error: executable path not found.")

# %%

views = []


for scene_id in tqdm(range(10)):
    if comm is None:
        break

    comm.fast_reset(scene_id)

    # We will go over the line below later
    comm.remove_terrain()
    top_view = get_scene_cameras(comm, [-1])
    views += top_view

IPython.display.display(display_grid_img(views, nrows=2))

# %%

comm.reset(4)

# %%

imgs_prev = get_scene_cameras(comm, [-4])
display_grid_img(imgs_prev, nrows=1)

# %%

s, graph = comm.environment_graph()
graph

# %%

comm.reset(4)
comm.add_character("chars/Female2", initial_room="kitchen")
s, g = comm.environment_graph()
# %%

s, nc = comm.camera_count()
indices = range(nc - 6, nc)
imgs_prev = get_scene_cameras(comm, indices)
display_grid_img(imgs_prev, nrows=2)

# %%

from demo.utils_demo import add_node, add_edge, find_nodes

nodes = find_nodes(graph, class_name="sofa")

sofa = None

if nodes:
    sofa = nodes[0]
    add_node(
        graph,
        {
            "class_name": "cat",
            "category": "Animals",
            "id": 1000,
            "properties": [],
            "states": [],
        },
    )
    add_edge(graph, 1000, "ON", sofa["id"])

# %%

success, message = comm.expand_scene(graph)

imgs_final = get_scene_cameras(comm, [-4])
display_grid_img(imgs_prev + imgs_final, nrows=1)

# %%

cat_id = [node["id"] for node in g["nodes"] if node["class_name"] == "cat"][0]

script = []

if sofa:
    script = [
        "<char0> [Walk] <sofa> ({})".format(sofa["id"]),
        "<char0> [Find] <cat> ({})".format(cat_id),
        "<char0> [Grab] <cat> ({})".format(cat_id),
        "<char0> [Sit] <sofa> ({})".format(sofa["id"]),
    ]

# %%

success, message = comm.render_script(
    script=script,
    processing_time_limit=60,
    find_solution=False,
    image_width=320,
    image_height=240,
    skip_animation=False,
    recording=True,
    save_pose_data=True,
    file_name_prefix="relax",
)

# %%
