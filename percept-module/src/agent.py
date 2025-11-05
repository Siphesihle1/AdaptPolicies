# %%
from ai2thor_agent import get_scene_metadata
from pprint import pprint

# %%
env, event = get_scene_metadata()
env.stop()

# %%
import matplotlib.pyplot as plt

metadata = event.metadata
objects = metadata["objects"]

# %%
categories = list(set([obj["objectType"] for obj in objects]))
pprint(categories)

# %%
from mdter.model import MDTERModel
from PIL import Image
from mdter.viz import plot_results

mdter = MDTERModel("mdetr_efficientnetB3_phrasecut")

image = Image.fromarray(event.cv2img)
# image.show()

print(f"category: {categories[0]}")
results = mdter.infer_segmentation(image, "A plate; an egg")
pprint(results)

plot_results(
    image, results["scores"], results["boxes"], results["labels"], results["masks"]
)

# %%
