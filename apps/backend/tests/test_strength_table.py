import json
import unittest
from pathlib import Path
from module1_intake.ocr.parsing.strength_table import extract_strength_table, parse_strength_product


class StrengthTableTests(unittest.TestCase):
    def test_multiple_components_preserve_pairs(self):
        fields, flags = parse_strength_product('Alpha 1000mg, Collagen natri 400mg...(Brand)')
        self.assertEqual([(c['name_raw'], c['strength_raw']) for c in fields['components_raw']],
                         [('Alpha', '1000mg'), ('Collagen natri', '400mg')])
        self.assertIsNone(fields['strength_raw'])
        self.assertIn('product_structure', flags)
        self.assertNotIn('components_raw', parse_strength_product('Alpha 1000mg, Beta ???')[0])

    def test_separator_and_isolated_noise(self):
        fields, flags = parse_strength_product('Example(Alias)-250mg  -')
        self.assertEqual(fields['name_raw'], 'Example(Alias)')
        self.assertEqual(fields['strength_raw'], '250mg')
        self.assertNotIn('product_structure', flags)

    def test_missing_or_damaged_name_is_not_accepted(self):
        fields, flags = parse_strength_product('-500 mg')
        self.assertIsNone(fields['name_raw'])
        self.assertIn('product_structure', flags)
        for text in ('0atese) -500 mg', 'Example 250mg 5', 'Example 200mg ('):
            self.assertIn('product_structure', parse_strength_product(text)[1])

    def test_unrelated_text_not_claimed(self):
        self.assertIsNone(extract_strength_table([]))

    def test_local_sample_and_count_mismatch(self):
        path = Path('data/local/module1/test-output/hospital-e.json')
        if not path.exists():
            self.skipTest('Local evidence unavailable')
        words = json.loads(path.read_text(encoding='utf-8'))['words']
        result = extract_strength_table(words)
        self.assertEqual(len(result['medications']), 6)
        self.assertTrue(all(m['instructions_raw'] for m in result['medications']))
        self.assertTrue(all('dose_raw' not in m for m in result['medications']))
        changed = [dict(w, text='7') if w['text'] == '6' and w['bbox']['y0'] > 690 else w for w in words]
        with self.assertRaises(ValueError):
            extract_strength_table(changed)
