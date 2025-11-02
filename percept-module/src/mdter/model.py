from .mdter_model.hubconf import _make_detr
from collections import defaultdict
import torch
import torchvision.transforms as T
import torch.nn.functional as F
from .utils import rescale_bboxes
from typing import List

torch.set_grad_enabled(False)


class MDTERModel:
    def __init__(self):
        # model = torch.hub.load(
        #   'ashkamath/mdetr:main',
        #   'mdetr_efficientnetB3_phrasecut',
        #   pretrained=True,
        #   return_postprocessor=False,
        # )
        self.model = _make_detr("timm_tf_efficientnet_b3_ns", mask=True, contrastive_align_loss=False)
        checkpoint = torch.hub.load_state_dict_from_url(
            url="https://zenodo.org/record/4721981/files/pretrained_EB3_checkpoint.pth",
            map_location="cpu",
            check_hash=True,
        )
        self.model.load_state_dict(checkpoint["model"], strict=False)

        # # enforce strict state-dict loading by re-applying the current state dict with strict=True
        # try:
        #   sd = model.state_dict()
        #   model.load_state_dict(sd, strict=True)
        # except Exception:
        #   # if strict re-load fails, keep the originally loaded model
        #   pass
        #

        if torch.cuda.is_available():
            self.model = self.model.cuda()
        self.model.eval()

        # standard PyTorch mean-std input image normalization
        self.transform = T.Compose([
            T.Resize(800),
            T.ToTensor(),
            T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ])

    def infer_segmentation(self, im, caption: str):
        img = self.transform(im).unsqueeze(0).cuda()

        # propagate through the model
        outputs = self.model(img, [caption])

        # keep only predictions with 0.9+ confidence
        probas = 1 - outputs['pred_logits'].softmax(-1)[0, :, -1].cpu()
        keep = (probas > 0.9).cpu()

        # convert boxes from [0; 1] to image scales
        bboxes_scaled = rescale_bboxes(outputs['pred_boxes'].cpu()[0, keep], im.size)

        # Interpolate masks to the correct size
        w, h = im.size
        masks = F.interpolate(outputs["pred_masks"], size=(h, w),
                              mode="bilinear", align_corners=False)
        masks = masks.cpu()[0, keep].sigmoid() > 0.5

        tokenized = self.model.detr.transformer.tokenizer.batch_encode_plus(
            [caption],
            padding="longest",
            return_tensors="pt"
        ).to(img.device)

        # Extract the text spans predicted by each box
        positive_tokens = (outputs["pred_logits"].cpu()[
                           0, keep].softmax(-1) > 0.1).nonzero().tolist()
        predicted_spans = defaultdict(str)
        for tok in positive_tokens:
            item, pos = tok
            if pos < 255:
                span = tokenized.token_to_chars(0, pos)
                predicted_spans[item] += " " + caption[span.start:span.end]

        print('predicted spans', predicted_spans)
        print('positive_tokens', positive_tokens)

        labels = [predicted_spans[k] for k in sorted(list(predicted_spans.keys()))]

        return {
            'boxes': bboxes_scaled,
            'labels': labels,
            'scores': probas[keep],
            'masks': masks
        }
