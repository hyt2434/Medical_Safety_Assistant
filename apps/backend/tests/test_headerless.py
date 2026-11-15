import unittest
from module1_intake.ocr.parsing.headerless import extract_headerless


def word(text, x, y):
    return {'text': text, 'confidence': 95, 'bbox': {'x0': x, 'x1': x+20, 'y0': y, 'y1': y+10}}


class HeaderlessTests(unittest.TestCase):
    def sample(self):
        words = [word('ĐƠN', 50, 0), word('THUỐC', 80, 0)]
        for i, y in enumerate((60, 140, 220), 1):
            words += [word(str(i), 10, y), word('Brand', 50, y),
                      word('28', 300, y), word('viên', 330, y),
                      word('Uống', 50, y+30), word('28', 80, y+30), word('ngày', 110, y+30)]
        return words + [word('Lời', 10, 290), word('dặn:', 40, 290)]

    def test_no_heading_or_strength_required(self):
        result = extract_headerless(self.sample())
        self.assertEqual(len(result['medications']), 3)
        self.assertEqual(result['medications'][0]['duration_raw'], '28 ngày')
        self.assertEqual(result['medications'][0]['quantity_raw'], '28 viên')
        self.assertIsNone(result['medications'][0]['strength_raw'])

    def test_missing_quantity_or_footer_not_accepted(self):
        self.assertIsNone(extract_headerless([w for w in self.sample() if w['text'] != 'viên']))
        self.assertIsNone(extract_headerless(self.sample()[:-2]))
