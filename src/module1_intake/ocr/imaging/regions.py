"""User-selected regions in the EXIF-oriented image; no automatic page discard."""
import math

from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ImageRegion(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    left: float = Field(ge=0, lt=1)
    top: float = Field(ge=0, lt=1)
    right: float = Field(gt=0, le=1)
    bottom: float = Field(gt=0, le=1)

    @model_validator(mode='after')
    def nonempty(self):
        if self.right <= self.left or self.bottom <= self.top:
            raise ValueError('Region must have positive width and height')
        return self


def crop_region(source, destination, region: ImageRegion):
    with Image.open(source) as image:
        width, height = image.size
        box = (math.floor(region.left * width), math.floor(region.top * height),
               math.ceil(region.right * width), math.ceil(region.bottom * height))
        if box[2] - box[0] < 32 or box[3] - box[1] < 32:
            raise ValueError('Vùng đọc quá nhỏ. Hãy chọn đủ tên thuốc, số lượng và cách dùng.')
        image.crop(box).save(destination, format='PNG')
    return {'full_normalized_size': [width, height],
            'selected_region': dict(zip(('left', 'top', 'right', 'bottom'), box)),
            'ocr_size': [box[2] - box[0], box[3] - box[1]],
            'region_to_full_normalized': [[1, 0, box[0]], [0, 1, box[1]], [0, 0, 1]]}
