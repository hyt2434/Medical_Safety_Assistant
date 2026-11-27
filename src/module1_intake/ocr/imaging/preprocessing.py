"""Conservative scan-like grayscale preparation, without automatic page cropping."""
import math
from collections import Counter
import cv2
import numpy as np
from PIL import Image


def preprocess_document(source, destination):
    with Image.open(source) as image:
        gray = np.asarray(image.convert('L'))
    h, w = gray.shape
    scale = min(2.0, max(1.0, 1800 / w), math.sqrt(12_000_000 / (w * h)))
    scale = max(1.0, scale)  # never reduce the original resolution
    nw, nh = round(w * scale), round(h * scale)
    if (nw, nh) != (w, h):
        gray = cv2.resize(gray, (nw, nh), interpolation=cv2.INTER_CUBIC)
    # Gentle local contrast; no thresholding, erosion, sharpening or cropping.
    p10, p90 = np.percentile(gray, (10, 90))
    contrast = p90 - p10 < 110
    if contrast:
        gray = cv2.createCLAHE(clipLimit=1.3, tileGridSize=(8, 8)).apply(gray)
    Image.fromarray(gray).save(destination)
    return {'version': 'scan_gray_v1', 'operations': ['grayscale'] +
            (['upscale'] if (nw, nh) != (w, h) else []) + (['clahe'] if contrast else []),
            'source_size': [w, h], 'output_size': [nw, nh],
            'source_to_output': [[nw/w, 0, 0], [0, nh/h, 0], [0, 0, 1]],
            'coordinate_space': 'preprocessed_image',
            'page_crop': 'disabled_to_preserve_content', 'deskew': 'not_applied',
            'contrast_clip_limit': 1.3 if contrast else None}


