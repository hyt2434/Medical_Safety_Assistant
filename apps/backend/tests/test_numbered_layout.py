import json
import unittest
from pathlib import Path

from module1_intake.ocr.numbered_parser import numbered_starters, product_fields, extract_numbered_prescription, parse_timing_labels
from module1_intake.ocr.parser import extract_printed_prescription
from module1_intake.ocr.parser_models import Extraction


def word(text, x, y):
    return {'text': text, 'confidence': 95, 'bbox': {'x0': x, 'x1': x+20, 'y0': y, 'y1': y+16}}


class NumberedLayoutTests(unittest.TestCase):
    def test_attached_ordinal_and_damaged_strength(self):
        starters = numbered_starters([word('1.', 50, 100), word('2.Brand', 50, 200)])
        self.assertEqual(len(starters), 2)
        fields, flags = product_fields('Brand [CODE] 500mg ar 20mg (Alpha + Beta)')
        self.assertIsNone(fields['strength_raw'])
        self.assertIn('product_structure', flags)

    def test_jpe_layout(self):
        path = Path('data/local/module1/test-output/jpe-evidence.json')
        if not path.exists():
            self.skipTest('Local JPE evidence unavailable')
        result = extract_printed_prescription(json.loads(path.read_text(encoding='utf-8')))
        meds = result['medications']
        self.assertEqual(len(meds), 5)
        self.assertTrue(meds[1]['product_raw'].startswith('Miderix'))
        self.assertIsNone(meds[0]['strength_raw'])
        self.assertIsNone(meds[1]['strength_raw'])
        self.assertEqual(meds[3]['strength_raw'], '120mg + 55mg + 2mcg + 8mcg')
        self.assertNotIn('Page', meds[-1]['instructions_raw'])
        self.assertTrue(all('sau ăn' in m['instructions_raw'] for m in meds[:4]))
    def test_unreadable_morning_preserves_evidence(self):
        result = parse_timing_labels('Sáng: ] Chiều: 1 Tối 1\nCách dùng: Uống; sau ăn')
        self.assertEqual([a['dose_raw'] for a in result], [None, '1', '1'])
        self.assertEqual(result[0]['source_text'], 'Sáng: ]')
        self.assertEqual(result[0]['issue'], 'unreadable_dose')
        self.assertIsNone(result[2]['issue'])

    def test_empty_dose_and_morning_only(self):
        result = parse_timing_labels('Sáng: Chiều: 1')
        self.assertIsNone(result[0]['dose_raw'])
        self.assertEqual(result[0]['source_text'], 'Sáng:')
        self.assertEqual(parse_timing_labels('Sáng: 1')[0]['dose_raw'], '1')
        self.assertEqual(len(parse_timing_labels('Sáng: 1')), 1)
        self.assertEqual(parse_timing_labels('Uống sau ăn và trước khi ngủ'), [])

    def test_explicit_units_and_instruction_boundary(self):
        result = parse_timing_labels('Sáng: 2 ml Cách dùng: Uống sau ăn')
        self.assertEqual(result[0]['dose_raw'], '2 ml')
        self.assertEqual(result[0]['source_text'], 'Sáng: 2 ml')

    def test_unrelated_numbers_and_dose_numbers_are_excluded(self):
        words = [word('24.', 200, 10), word('1.', 50, 100), word('2.', 50, 200),
                 word('1', 250, 140), word('3.', 50, 350)]
        self.assertEqual([w['text'] for w in numbered_starters(words)], ['1.', '2.', '3.'])

    def test_compound_and_package(self):
        fields, _ = product_fields('Brand [CODE] 100mg + 25mg +\n300mg (Alpha + Beta)')
        self.assertEqual(fields['strength_raw'], '100mg + 25mg + 300mg')
        fields, _ = product_fields('Brand (20mg + 582mg + 196mg)/10ml (Alpha)')
        self.assertEqual(fields['strength_raw'], '(20mg + 582mg + 196mg)/10ml')
        fields, _ = product_fields('Brand 50mg/ml - 10ml (Alpha)')
        self.assertEqual(fields['package_size_raw'], '10ml')
        self.assertEqual(fields['strength_raw'], '50mg/ml')

    def test_no_header_numbered_prose_is_not_prescription(self):
        self.assertIsNone(extract_numbered_prescription([word('1.', 50, 100), word('2.', 50, 200)]))

    def test_header_independent_rows_and_missing_units(self):
        words = [word('ĐƠN THUỐC', 50, 30)]
        for i, y in enumerate([100, 200], 1):
            words += [word(f'{i}.', 50, y), word('Brand 10mg (Alpha)', 90, y),
                      word('x', 600, y-5), word('10 ngày = 20 Viên', 630, y-5),
                      word('Sáng: 1', 90, y+30), word('Cách dùng: Uống; sau ăn', 90, y+55)]
        words += [word('Khi', 50, 300), word('tái khám', 90, 300)]
        result = extract_numbered_prescription(words)
        self.assertEqual(len(result['medications']), 2)
        self.assertEqual(result['medications'][0]['quantity_raw'], '20 Viên')
        self.assertIn('dose_unit_missing', result['medications'][0]['uncertain_fields'])
        self.assertNotIn('schedule_incomplete', result['medications'][0]['uncertain_fields'])
        self.assertNotIn('Khi', result['medications'][-1]['instructions_raw'])

    def test_actual_third_image(self):
        path = Path('data/local/module1/test-output/third-layout-evidence.json')
        if not path.exists():
            self.skipTest('Local evidence unavailable')
        raw = json.loads(path.read_text(encoding='utf-8'))
        result = Extraction.model_validate(extract_printed_prescription(raw))
        self.assertEqual(len(result.medications), 6)
        self.assertTrue(all(m.duration_raw and m.quantity_raw for m in result.medications))
        self.assertEqual(result.medications[2].strength_raw, '100mg + 25mg + 150mg + 50mg + 300mg')
        self.assertEqual(result.medications[-1].package_size_raw, '10ml')
        self.assertEqual([a.dose_raw for a in result.medications[-1].administrations], [None, '1', '1'])
        self.assertEqual(result.medications[-1].administrations[0].issue, 'unreadable_dose')
        self.assertIn('schedule_incomplete', result.medications[-1].uncertain_fields)
        self.assertTrue(result.document_instructions_raw)
        self.assertNotIn('Khi tái khám', result.medications[-1].instructions_raw)
