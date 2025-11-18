from collections import defaultdict
from pprint import pprint
from typing import List, Literal, Optional, Union

import torch
import torch.nn.functional as F
import torchvision.transforms as T
from torch import Tensor

from .mdter_model.hubconf import _make_detr
from .utils import get_category_from_caption, rescale_bboxes

from vild.utils import article

torch.set_grad_enabled(False)


class MDTERModel:
    def __init__(
        self,
        model_name: Union[
            Literal["mdetr_efficientnetB5"], Literal["mdetr_efficientnetB3_phrasecut"]
        ],
    ):
        self.model_name = model_name
        self.model = torch.hub.load(
            "ashkamath/mdetr:main",
            model_name,
            pretrained=True,
            return_postprocessor=False,
        )

        if torch.cuda.is_available():
            self.model = self.model.cuda()

        self.model.eval()

        # standard PyTorch mean-std input image normalization
        self.transform = T.Compose(
            [
                T.Resize(800),
                T.ToTensor(),
                T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
            ]
        )

    def infer_segmentation(self, im, caption: str):
        img = self.transform(im).unsqueeze(0).cuda()

        # propagate through the model
        outputs = self.model(img, [caption])

        # keep only predictions with 0.9+ confidence
        probas = 1 - outputs["pred_logits"].softmax(-1)[0, :, -1].cpu()
        keep = (probas > 0.9).cpu()

        # convert boxes from [0; 1] to image scales
        bboxes_scaled = rescale_bboxes(outputs["pred_boxes"].cpu()[0, keep], im.size)

        # Interpolate masks to the correct size
        w, h = im.size
        masks = F.interpolate(
            outputs["pred_masks"], size=(h, w), mode="bilinear", align_corners=False
        )
        masks = masks.cpu()[0, keep].sigmoid() > 0.5

        tokenized = self.model.detr.transformer.tokenizer.batch_encode_plus(
            [caption], padding="longest", return_tensors="pt"
        ).to(img.device)

        # Extract the text spans predicted by each box
        positive_tokens = (
            (outputs["pred_logits"].cpu()[0, keep].softmax(-1) > 0.1).nonzero().tolist()
        )
        predicted_spans = defaultdict(str)
        for tok in positive_tokens:
            item, pos = tok
            if pos < 255:
                span = tokenized.token_to_chars(0, pos)
                predicted_spans[item] += " " + caption[span.start : span.end]

        labels = [predicted_spans[k] for k in sorted(list(predicted_spans.keys()))]

        return {
            "boxes": bboxes_scaled,
            "labels": labels,
            "scores": probas[keep],
            "masks": masks,
        }

    def infer_bounding_boxes(self, im, caption):
        # mean-std normalize the input image (batch-size: 1)
        img = self.transform(im).unsqueeze(0).cuda()

        # propagate through the model
        memory_cache = self.model(img, [caption], encode_and_save=True)
        outputs = self.model(
            img, [caption], encode_and_save=False, memory_cache=memory_cache
        )

        # keep only predictions with 0.7+ confidence
        probas = 1 - outputs["pred_logits"].softmax(-1)[0, :, -1].cpu()
        keep = (probas > 0.7).cpu()

        # convert boxes from [0; 1] to image scales
        bboxes_scaled = rescale_bboxes(outputs["pred_boxes"].cpu()[0, keep], im.size)

        # Extract the text spans predicted by each box
        positive_tokens = (
            (outputs["pred_logits"].cpu()[0, keep].softmax(-1) > 0.1).nonzero().tolist()
        )
        predicted_spans = defaultdict(str)
        for tok in positive_tokens:
            item, pos = tok
            if pos < 255:
                span = memory_cache["tokenized"].token_to_chars(0, pos)
                predicted_spans[item] += " " + caption[span.start : span.end]

        labels = [predicted_spans[k] for k in sorted(list(predicted_spans.keys()))]

        return {
            "boxes": bboxes_scaled,
            "labels": labels,
            "scores": probas[keep],
            "masks": None,
        }

    def detect_object_categories(self, image, category_names: List[str]):
        cat_boxes = Tensor()
        cat_scores = Tensor()
        cat_masks = Tensor()
        cat_labels = []

        for catetory in category_names:
            caption = f"{article(catetory)} {catetory}"
            results = (
                self.infer_bounding_boxes(image, caption)
                if self.model_name == "mdetr_efficientnetB5"
                else self.infer_segmentation(image, caption)
            )

            if len(cat_boxes) == 0:
                cat_boxes = results["boxes"]
                cat_scores = results["scores"]
                cat_masks = results["masks"]
            else:
                cat_boxes = torch.cat((cat_boxes, results["boxes"]), dim=0)
                cat_scores = torch.cat((cat_scores, results["scores"]), dim=0)

                if results["masks"] != None:
                    cat_masks = torch.cat((cat_masks, results["masks"]), dim=0)

            cat_labels += list(map(get_category_from_caption, results["labels"]))

        return {
            "boxes": cat_boxes,
            "labels": cat_labels,
            "scores": cat_scores,
            "masks": cat_masks,
        }
