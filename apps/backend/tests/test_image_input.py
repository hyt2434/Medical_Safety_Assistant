import tempfile
import unittest
from pathlib import Path
from PIL import Image
from module1_intake.ocr.image_input import prepare_image


class ImageInputTests(unittest.TestCase):
    def test_supported_formats_decode_to_png(self):
        with tempfile.TemporaryDirectory() as directory:
            for extension in ('jpg', 'jpe', 'JPE', 'png', 'webp', 'bmp', 'tiff', 'gif'):
                with self.subTest(extension=extension):
                    source = Path(directory) / f'image.{extension}'
                    target = Path(directory) / 'normalized.png'
                    Image.new('RGB', (32, 24), 'white').save(source)
                    metadata = prepare_image(source, target)
                    with Image.open(target) as result:
                        self.assertEqual(result.format, 'PNG')
                        self.assertEqual(result.size, (32, 24))
                    self.assertEqual(metadata['ocr_size'], [32, 24])

    def test_multiple_frames_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            for extension in ('tiff', 'gif'):
                source = Path(directory) / f'multi.{extension}'
                Image.new('RGB', (10, 10), 'white').save(source, save_all=True,
                    append_images=[Image.new('RGB', (10, 10), 'black')])
                with self.assertRaisesRegex(ValueError, 'nhiều trang'):
                    prepare_image(source, Path(directory) / 'out.png')

    def test_fake_image_and_transparency(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'input.png'
            target = Path(directory) / 'out.png'
            source.write_text('not an image')
            with self.assertRaises(ValueError):
                prepare_image(source, target)
            Image.new('RGBA', (10, 10), (0, 0, 0, 0)).save(source)
            prepare_image(source, target)
            with Image.open(target) as result:
                self.assertEqual(result.getpixel((0, 0)), (255, 255, 255))

    def test_exif_orientation(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'input.jpg'
            target = Path(directory) / 'out.png'
            exif = Image.Exif()
            exif[274] = 6
            Image.new('RGB', (30, 20)).save(source, exif=exif)
            self.assertEqual(prepare_image(source, target)['ocr_size'], [20, 30])
