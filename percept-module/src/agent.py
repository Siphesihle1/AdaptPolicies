# %%
from ai2thor_agent import get_scene_metadata
from pprint import pprint

# %%
env, event = get_scene_metadata()
env.stop()

# %%
import matplotlib.pyplot as plt

metadata = event.metadata
objects = metadata['objects']

# plt.imshow(event.cv2img)
# plt.show()

#k%%
categories = list(set([obj['objectType'] for obj in objects]))
pprint(categories)

# %%
from mdter.model import MDTERModel
from PIL import Image
from mdter.viz import plot_results

mdter = MDTERModel()

image = Image.fromarray(event.cv2img)
pprint(image)
# image.show()

results = mdter.infer_segmentation(image, categories[0])
pprint(results)

# plot_results(
#     image, 
#     results[scores'], 
#     results['boxes'], 
#     results['labels'], 
#     results['masks'],
# )

# %%

