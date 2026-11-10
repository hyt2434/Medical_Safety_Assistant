import unittest
from module1_intake.ocr.parsing.tables import extract_quantity_only_table
from module1_intake.ocr.parsing.products import parse_quantity_product


def word(text, x, y):
    return {'text':text,'bbox':{'x0':x,'x1':x+15,'y0':y,'y1':y+10}}


class QuantityOnlyTests(unittest.TestCase):
    def test_combination_nested_description_and_package(self):
        fields, flags = parse_quantity_product('Brand Lotion 5mg/g+20mg/g ,40ml (Alpha (form) + Beta)')
        self.assertEqual(fields['name_raw'], 'Brand Lotion')
        self.assertEqual(fields['strength_raw'], '5mg/g+20mg/g')
        self.assertEqual(fields['package_size_raw'], '40ml')
        self.assertEqual(fields['parenthetical_raw'], 'Alpha (form) + Beta')
        self.assertIsNone(fields['ingredient_raw'])
        self.assertNotIn('product_structure', flags)
        self.assertIn('product_structure', parse_quantity_product('Brand 5mg (broken')[1])
        self.assertIn('product_structure', parse_quantity_product('Brand 5mg junk')[1])

    def sample(self):
        words = [word('Số',300,0), word('lượng',330,0)]
        for ordinal,y in ((1,40),(2,100),(4,160)):
            words += [word(str(ordinal)+'/',10,y), word('Brand 5mg',50,y),
                      word('X60',300,y),word('Viên',350,y),word('uống sáng',50,y+25)]
        return words+[word('Lời',10,210)]

    def test_bad_ordinal_retained_and_merged_quantity_split(self):
        result = extract_quantity_only_table(self.sample())
        self.assertEqual(len(result['medications']),3)
        item = result['medications'][-1]
        self.assertIn('4/',item['evidence_text'])
        self.assertEqual(item['quantity_raw'],'60 Viên')
        self.assertIn('row_number_unverified',item['uncertain_fields'])

    def test_missing_quantity_or_footer_rejected(self):
        self.assertIsNone(extract_quantity_only_table(self.sample()[:-1]))
        self.assertIsNone(extract_quantity_only_table([w for w in self.sample() if w['text']!='Viên']))
