"""Decode supported single-frame images into a shared OCR coordinate space."""
import warnings
from PIL import Image, ImageOps, UnidentifiedImageError

SUFFIXES = {'.jpg', '.jpeg', '.jpe', '.png', '.webp', '.bmp', '.tif', '.tiff', '.gif'}
CONTENT_TYPES = {'image/jpeg', 'image/png', 'image/webp', 'image/bmp',
                 'image/x-ms-bmp', 'image/tiff', 'image/gif'}
DESCRIPTION = 'JPG/JPEG/JPE, PNG, WebP, BMP, TIFF/TIF và GIF một khung hình'
FORMATS = {'JPEG', 'PNG', 'WEBP', 'BMP', 'TIFF', 'GIF'}
MAX_PIXELS = 25_000_000


def prepare_image(source, destination):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(source) as original:
                if original.format not in FORMATS:
                    raise ValueError('Nội dung tệp không thuộc định dạng ảnh được hỗ trợ')
                if getattr(original, 'n_frames', 1) != 1:
                    raise ValueError('Chưa hỗ trợ ảnh động hoặc TIFF nhiều trang; hãy tách từng trang thành ảnh riêng')
                if original.width * original.height > MAX_PIXELS:
                    raise ValueError('Ảnh vượt quá giới hạn 25 triệu pixel')
                metadata = {'source_format': original.format, 'source_size': list(original.size),
                            'ocr_format': 'PNG', 'coordinate_space': 'normalized_image'}
                oriented = ImageOps.exif_transpose(original)
                rgba = oriented.convert('RGBA')
                canvas = Image.new('RGBA', rgba.size, 'white')
                canvas.alpha_composite(rgba)
                canvas.convert('RGB').save(destination, format='PNG')
                metadata['ocr_size'] = list(canvas.size)
                return metadata
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise ValueError('Tệp ảnh hỏng, không đọc được hoặc vượt giới hạn kích thước') from error
