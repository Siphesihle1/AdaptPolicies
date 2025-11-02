# ViLD library

from easydict import EasyDict

import numpy as np
import torch
import clip

from tqdm import tqdm

from matplotlib import pyplot as plt
from matplotlib import patches

import collections
import json
import numpy as np

import os
import os.path as osp

from PIL import Image
from pprint import pprint
from scipy.special import softmax
import yaml
import tensorflow as tf

import cv2

from .utils import *
from .constants import *
from .prompt_templates import *
from .viz import paste_instance_masks

from typing import *

class ViLDModel:
  def __init__(self):
    clip.available_models()
    self.model, self.preprocess = clip.load("ViT-B/32")
    self.session = tf.compat.v1.Session(graph=tf.Graph())
    self.saved_model_dir = os.path.join(os.environ['MODEL_DIR'], 'vild')
    
    tf.compat.v1.saved_model.load(sess=self.session, tags=['serve'], export_dir=self.saved_model_dir)
  
  def build_text_embedding(self, categories: List[Dict[str, Any]]) -> np.ndarray:
    if FLAGS.prompt_engineering:
      templates = multiple_templates
    else:
      templates = single_template

    run_on_gpu = torch.cuda.is_available()

    with torch.no_grad():
      all_text_embeddings = []
      print('Building text embeddings...')

      for category in tqdm(categories):
        texts = [
          template.format(processed_name(category['name'], rm_dot=True),
            article=article(category['name']))
          for template in templates
        ]

        if FLAGS.this_is:
          texts = [
            'This is ' + text if text.startswith('a') or text.startswith('the') else text
            for text in texts
          ]

        texts = clip.tokenize(texts) #tokenize

        if run_on_gpu:
          texts = texts.cuda()
        
        text_embeddings = self.model.encode_text(texts) #embed with text encoder
        text_embeddings /= text_embeddings.norm(dim=-1, keepdim=True)
        text_embedding = text_embeddings.mean(dim=0)
        text_embedding /= text_embedding.norm()
        all_text_embeddings.append(text_embedding)
      
      all_text_embeddings = torch.stack(all_text_embeddings, dim=1)
      
      if run_on_gpu:
        all_text_embeddings = all_text_embeddings.cuda()

    return all_text_embeddings.cpu().numpy().T
  
  def detect_object_categories(
    self, 
    image_path: str, 
    category_names: List[str], 
    params: Tuple[int, float, float, float]
  ):
    #################################################################
    # Preprocessing categories and get params
    category_names = ['background'] + category_names
    categories = [{'name': item, 'id': idx+1,} for idx, item in enumerate(category_names)]

    max_boxes_to_draw, nms_threshold, min_rpn_score_thresh, min_box_area = params
    
    #################################################################
    # Obtain results and read image
    roi_boxes, roi_scores, detection_boxes, scores_unused, box_outputs, detection_masks, visual_features, image_info = \
    self.session.run(
      [
        'RoiBoxes:0', 
        'RoiScores:0', 
        '2ndStageBoxes:0', 
        '2ndStageScoresUnused:0', 
        'BoxOutputs:0', 
        'MaskOutputs:0', 
        'VisualFeatOutputs:0', 
        'ImageInfo:0'
      ],
      feed_dict={'Placeholder:0': [image_path,]}
    )
    
    roi_boxes = np.squeeze(roi_boxes, axis=0)
    # no need to clip the boxes, already done
    roi_scores = np.squeeze(roi_scores, axis=0)
    detection_boxes = np.squeeze(detection_boxes, axis=(0, 2))
    scores_unused = np.squeeze(scores_unused, axis=0)
    box_outputs = np.squeeze(box_outputs, axis=0)
    detection_masks = np.squeeze(detection_masks, axis=0)
    visual_features = np.squeeze(visual_features, axis=0)
    
    image_info = np.squeeze(image_info, axis=0)  # obtain image info
    image_scale = np.tile(image_info[2:3, :], (1, 2))
    image_height = int(image_info[0, 0])
    image_width = int(image_info[0, 1])

    rescaled_detection_boxes = detection_boxes / image_scale # rescale
    
    #################################################################
    # Filter boxes

    # Apply non-maximum suppression to detected boxes with nms threshold.
    nmsed_indices = nms(
      detection_boxes,
      roi_scores,
      thresh=nms_threshold
    )
    
    # Compute RPN box size.
    box_sizes = (
      rescaled_detection_boxes[:, 2] - rescaled_detection_boxes[:, 0]) \
      * (rescaled_detection_boxes[:, 3] - rescaled_detection_boxes[:, 1]
    )
      
    # Filter out invalid rois (nmsed rois)
    valid_indices = np.where(
      np.logical_and(
        np.isin(np.arange(len(roi_scores), dtype=int), nmsed_indices),
        np.logical_and(
          np.logical_not(np.all(roi_boxes == 0., axis=-1)),
          np.logical_and(
            roi_scores >= min_rpn_score_thresh,
            box_sizes > min_box_area
          )
        )
      )
    )[0]
    print('number of valid indices', len(valid_indices))
    
    detection_roi_scores = roi_scores[valid_indices][:max_boxes_to_draw, ...]
    detection_boxes = detection_boxes[valid_indices][:max_boxes_to_draw, ...]
    detection_masks = detection_masks[valid_indices][:max_boxes_to_draw, ...]
    detection_visual_feat = visual_features[valid_indices][:max_boxes_to_draw, ...]
    rescaled_detection_boxes = rescaled_detection_boxes[valid_indices][:max_boxes_to_draw, ...]

    #################################################################
    # Compute text embeddings and detection scores, and rank results
    text_features = self.build_text_embedding(categories)

    raw_scores = detection_visual_feat.dot(text_features.T)
    if FLAGS.use_softmax:
      scores_all = softmax(FLAGS.temperature * raw_scores, axis=-1)
    else:
      scores_all = raw_scores

    indices = np.argsort(-np.max(scores_all, axis=1))  # Results are ranked by scores
    indices_fg = np.array([i for i in indices if np.argmax(scores_all[i]) != 0])
    
    boxes = rescaled_detection_boxes[indices_fg]
    scores = detection_roi_scores[indices_fg]
    scores_all = scores_all[indices_fg]
    
    ymin, xmin, ymax, xmax = np.split(rescaled_detection_boxes, 4, axis=-1)
    processed_boxes = np.concatenate([xmin, ymin, xmax - xmin, ymax - ymin], axis=-1)
    segmentations = paste_instance_masks(
      detection_masks, processed_boxes, image_height, image_width
    )[indices_fg]
    
    if scores is None: return None
    
    labels = [category_names[np.argmax(category_scores)] for category_scores in scores_all]
    
    return {
      'boxes': boxes,
      'labels': labels,
      'scores': scores,
      'masks': segmentations,
      'image': np.asarray(Image.open(open(image_path, 'rb')).convert("RGB")),
      'valid_indices': valid_indices[:max_boxes_to_draw][indices_fg],
      'scores_all': scores_all
    }
    
      
      
    
    