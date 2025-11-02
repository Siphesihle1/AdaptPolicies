# %%
from ai2thor_agent import get_scene_metadata

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
print(categories)

# %%
from mdter.model import MDTERModel
from PIL import Image
from mdter.viz import plot_results

mdter = MDTERModel()

image = Image.fromarray(event.cv2img)
image.show()

results = mdter.infer_segmentation(image, categories[0])

print('category = ', categories[0])
print(
    'scores = ', len(results['scores']), 
    '\nboxes = ', len(results['boxes']), 
    '\nlabels = ', len(results['labels']), 
    '\nmasks = ', len(results['masks'])
)

# plot_results(
#     image, 
#     results[scores'], 
#     results['boxes'], 
#     results['labels'], 
#     results['masks'],
# )

# %%

