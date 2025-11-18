import torch
import numpy as np
from typing import Tuple

import re


# for output bounding box post-processing
def box_cxcywh_to_xyxy(x: torch.Tensor):
    x_c, y_c, w, h = x.unbind(1)
    b = [(x_c - 0.5 * w), (y_c - 0.5 * h), (x_c + 0.5 * w), (y_c + 0.5 * h)]
    return torch.stack(b, dim=1)


def rescale_bboxes(out_bbox: torch.Tensor, size: Tuple[int, int]):
    img_w, img_h = size
    b = box_cxcywh_to_xyxy(out_bbox)
    b = b * torch.tensor([img_w, img_h, img_w, img_h], dtype=torch.float32)
    return b


def get_category_from_caption(caption: str) -> str:
    """Extracts the category name from a caption string.

    Args:
        caption (str): The caption string, e.g., "a chair", "an apple".

    Returns:
        str: The extracted category name, e.g., "chair", "apple".
    """

    cleaned_caption = re.sub(r"(?<=[a-zA-Z])\s+(?=[a-z])", "", caption.strip())
    words = cleaned_caption.split()

    if len(words) > 1:
        return " ".join(words[1:])
    return cleaned_caption
