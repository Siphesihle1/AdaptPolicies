import numpy as np
import matplotlib.pyplot as plt
from skimage.measure import find_contours
from matplotlib.patches import Polygon
from torch import Tensor
from .constants import COLORS

from typing import List, Optional


def apply_mask(image: np.ndarray, mask: Tensor, color: List[float], alpha=0.5):
    """Apply the given mask to the image."""
    for c in range(3):
        image[:, :, c] = np.where(
            mask == 1,
            image[:, :, c] * (1 - alpha) + alpha * color[c] * 255,
            image[:, :, c],
        )
    return image


def plot_results(
    pil_img,
    scores: Tensor,
    boxes: Tensor,
    labels: List[str],
    masks=None,
):
    plt.figure(figsize=(16, 10))
    np_image = np.array(pil_img)
    ax = plt.gca()
    colors = COLORS * 100
    if masks is None:
        masks = [None for _ in range(len(scores))]
    assert len(scores) == len(boxes) == len(labels) == len(masks)
    for s, (xmin, ymin, xmax, ymax), l, mask, c in zip(
        scores, boxes.tolist(), labels, masks, colors
    ):
        ax.add_patch(
            plt.Rectangle(
                (xmin, ymin), xmax - xmin, ymax - ymin, fill=False, color=c, linewidth=3
            )
        )
        text = f"{l}: {s:0.2f}"
        ax.text(xmin, ymin, text, fontsize=15, bbox=dict(facecolor="white", alpha=0.8))

        if mask is None:
            continue
        np_image = apply_mask(np_image, mask, c)

        # padded_mask = np.zeros((mask.shape[0] + 2, mask.shape[1] + 2), dtype=np.uint8)
        # padded_mask[1:-1, 1:-1] = mask
        # contours = find_contours(padded_mask, 0.5)
        # for verts in contours:
        #     # Subtract the padding and flip (y, x) to (x, y)
        #     verts = np.fliplr(verts) - 1
        #     p = Polygon(verts, facecolor="none", edgecolor=c)
        #     ax.add_patch(p)
    return np_image

    # plt.imshow(np_image)
    # plt.axis("off")
    # plt.show()
    plt.close()
