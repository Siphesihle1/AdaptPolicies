# %
from ai2thor_agent import get_scene_metadata
from pprint import pprint

# %%
env, event = get_scene_metadata()
env.stop()

# %%
metadata = event.metadata
objects = metadata["objects"]

# %%
categories = list(set([obj["objectType"] for obj in objects]))
pprint(categories)
print(f"number of categories = {len(categories)}")

# %%

# Get image and save to file path
from PIL import Image

image = Image.fromarray(event.frame, mode="RGB")
image_path = "./scene_images/event_frame.png"

image.save(image_path)

# %%
from vild.model import ViLDModel
from vild.viz import visualize_boxes_and_labels_on_image_array
from vild.constants import overall_fig_size

import numpy as np

import matplotlib.pyplot as plt

vild = ViLDModel()

max_boxes_to_draw = 25  # @param {type:"integer"}

nms_threshold = 0.05  # @param {type:"slider", min:0, max:0.9, step:0.05}
min_rpn_score_thresh = 0.9  # @param {type:"slider", min:0, max:1, step:0.01}
min_box_area = 220  # @param {type:"slider", min:0, max:10000, step:1.0}

params = max_boxes_to_draw, nms_threshold, min_rpn_score_thresh, min_box_area

vild_results = vild.detect_object_categories(image_path, categories, params)
vild_image_w_dets = np.array([])

if vild_results:
    vild_image_w_dets = visualize_boxes_and_labels_on_image_array(
        np.array(image),
        vild_results["boxes"],
        vild_results["labels"],
        instance_masks=vild_results["masks"],
        classes=np.arange(len(vild_results["labels"])) + 1,
        scores=vild_results["scores"],
        use_normalized_coordinates=False,
        max_boxes_to_draw=max_boxes_to_draw,
        min_score_thresh=min_rpn_score_thresh,
        skip_scores=True,
        skip_labels=False,
    )

# %%
from mdter.model import MDTERModel
from mdter.viz import plot_results

mdter = MDTERModel("mdetr_efficientnetB5")

print("category:", categories[0])
mdter_results = mdter.detect_object_categories(image, [categories[0]])

mdter_image_w_dets = visualize_boxes_and_labels_on_image_array(
    np.array(image),
    mdter_results["boxes"].cpu().numpy(),
    mdter_results["labels"],
    # instance_masks=mdter_results["masks"].cpu().numpy().astype(np.uint8),
    classes=np.arange(len(mdter_results["labels"])) + 1,
    scores=mdter_results["scores"].cpu().numpy(),
    use_normalized_coordinates=False,
    skip_scores=True,
    skip_labels=False,
    bounding_box_order=(1, 0, 3, 2),
)
# %%

# Plot images with detections side-by-side
fig, ax = plt.subplots(1, 2, figsize=overall_fig_size)
plt.axis("off")
ax[0].imshow(vild_image_w_dets)
ax[0].set_title("ViLD Detections")
ax[0].axis("off")
ax[1].imshow(mdter_image_w_dets)
ax[1].set_title("MDTER Detections")
ax[1].axis("off")
plt.show()

# %%
