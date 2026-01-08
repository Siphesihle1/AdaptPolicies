import os
from tqdm import tqdm

import virtualhome
from unity_simulator.comm_unity import UnityCommunication
from demo.utils_demo import (
    display_grid_img,
    get_scene_cameras,
    find_nodes,
    add_node,
    add_edge,
)
from unity_simulator import utils_viz


comm = UnityCommunication(file_name=None, port=os.getenv("SIM_PORT", "8082"))

# Sample top-down views of multiple scenes
views = []
for scene_id in tqdm(range(10)):
    comm.reset(scene_id)

    # We will go over the line below later
    comm.remove_terrain()
    top_view = get_scene_cameras(comm, [-1])
    views += top_view

scenes_grid_img = display_grid_img(views, nrows=2)
scenes_grid_img.save(f"{os.getenv('JOB_OUTPUT_DIR')}/vh_sample_scenes.png")

# Modifying a scene
comm.reset(4)
success, graph = comm.environment_graph()
nodes = find_nodes(graph, class_name="sofa")
sofa = None

if nodes:
    sofa = nodes[0]
    print(sofa)

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

scene_wo_cat = get_scene_cameras(comm, [-4])
success, message = comm.expand_scene(graph)
scene_w_cat = get_scene_cameras(comm, [-4])

cat_scene_img = display_grid_img(scene_wo_cat + scene_wo_cat, nrows=1)
cat_scene_img.save(f"{os.getenv('JOB_OUTPUT_DIR')}/cat_scene.png")

# Adding characters
comm.add_character("chars/Female2", initial_room="kitchen")

_, graph = comm.environment_graph()
cat_id = [node["id"] for node in graph["nodes"] if node["class_name"] == "cat"][0]

s, nc = comm.camera_count()
indices = range(nc - 6, nc)
character_scene = get_scene_cameras(comm, indices)

character_scene_img = display_grid_img(character_scene, nrows=2)
character_scene_img.save(f"{os.getenv('JOB_OUTPUT_DIR')}/character_scene.png")

# Generating a video
script = []

if sofa:
    script = [
        "<char0> [Walk] <sofa> ({})".format(sofa["id"]),
        "<char0> [Find] <cat> ({})".format(cat_id),
        "<char0> [Grab] <cat> ({})".format(cat_id),
        "<char0> [Sit] <sofa> ({})".format(sofa["id"]),
    ]

success, message = comm.render_script(
    script=script,
    processing_time_limit=60,
    find_solution=False,
    image_width=320,
    image_height=240,
    skip_animation=False,
    recording=True,
    output_folder=os.getenv("JOB_OUTPUT_DIR", "."),
    save_pose_data=True,
    file_name_prefix="relax",
)

path_video = os.getenv("JOB_OUTPUT_DIR", ".")
utils_viz.generate_video(input_path=path_video, prefix="relax", output_path=path_video)
