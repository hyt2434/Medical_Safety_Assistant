import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from api.app import app
from module1_intake.ocr.parsing.dispatcher import extract_printed_prescription, find_numbered_row_starters, split_product
from module1_intake.ocr.models.extraction import Extraction
from module1_intake.ocr.parsing.products import parse_table_product
from module1_intake.ocr.parsing.tables import reading_lines


def word(text: str, x: int, y: int, confidence: float = 95) -> dict:
    return {
        "text": text,
        "confidence": confidence,
        "bbox": {"x0": x, "y0": y, "x1": x + 20, "y1": y + 16},
    }


class NumberedRowsTest(unittest.TestCase):
    def test_literal_product_fields(self) -> None:
        cases = [
            ('Ibufen D 100 mg/5ml, 120ml ( Ibuprofen )', 'Ibufen D', '100 mg/5ml', '120ml', 'Ibuprofen'),
            ('Cerepone Dry 125mg/5ml ( Cefprozil\n125mg/5ml )', 'Cerepone Dry', '125mg/5ml', None, 'Cefprozil'),
            ('Thymorosin300mg/50ml(Thymomodulin)', 'Thymorosin', '300mg/50ml', None, 'Thymomodulin'),
            ('Kidafort 60ml (Sit, Vitamin)', 'Kidafort', None, '60ml', 'Sit, Vitamin'),
            ('Drug 0,5mg/ml', 'Drug', '0,5mg/ml', None, None),
        ]
        for text, name, strength, package, ingredient in cases:
            with self.subTest(text=text):
                fields, _ = parse_table_product(text)
                self.assertEqual([fields[k] for k in ('name_raw', 'strength_raw', 'package_size_raw', 'ingredient_raw')],
                                 [name, strength, package, ingredient])

    def test_ambiguous_product_is_not_silently_truncated(self) -> None:
        for text in ['Drug 10mg/unknown', 'Drug (Brand 10mg', 'Drug 10mg extra',
                     'Drug (Brand (1mg/g)) 10g']:
            fields, flags = parse_table_product(text)
            self.assertEqual(fields['name_raw'], text)
            self.assertIsNone(fields['strength_raw'])
            self.assertIn('product_structure', flags)

    def test_reading_order_with_vertical_jitter(self) -> None:
        words = [word('15', 400, 98), word('Drug', 80, 102), word('1', 40, 100),
                 word('Uống', 80, 135), word('10mg', 150, 99)]
        self.assertEqual(reading_lines(words, 10), ['1 Drug 10mg 15', 'Uống'])

    def test_processed_image_field_mapping(self) -> None:
        path = Path('data/local/module1/cv-second-layout/illumination_normalized.json')
        if not path.exists():
            self.skipTest('Local CV evidence is not present')
        parsed = Extraction.model_validate(extract_printed_prescription(json.loads(path.read_text(encoding='utf-8'))))
        medicine = parsed.medications[1]
        self.assertEqual(medicine.name_raw, 'Ibufen D')
        self.assertEqual(medicine.strength_raw, '100 mg/5ml')
        self.assertEqual(medicine.package_size_raw, '120ml')
        self.assertEqual(medicine.ingredient_raw, 'Ibuprofen')
        self.assertTrue(medicine.evidence_text.startswith('(27 Ibufen D'))
        self.assertIn('khi sốt', medicine.instructions_raw)
        self.assertEqual(medicine.administrations, [])
        self.assertIsNone(parsed.medications[3].strength_raw)
        self.assertEqual(parsed.medications[3].package_size_raw, '60ml')

    def test_quantity_table_with_damaged_ordinals(self) -> None:
        words = [word(t, x, 40) for t, x in [('Tên', 80), ('thuốc', 110),
                 ('hoạt', 150), ('chất', 180), ('Số', 380), ('lượng', 410)]]
        for index, marker in enumerate(['1', '(2', '3/DrugC', '§']):
            y = 100 + index * 60
            words.append(word(marker, 50, y))
            if index != 2:
                words.append(word('Drug', 85, y))
            words.extend([word('X', 360, y), word('1', 395, y), word('Lọ', 435, y),
                          word('Uống khi cần', 85, y + 25)])
        words.append(word('Ghi chú:', 45, 350))
        result = Extraction.model_validate(extract_printed_prescription({'words': words}))
        self.assertEqual(len(result.medications), 4)
        self.assertEqual(result.medications[2].product_raw, 'DrugC')
        self.assertIn('row_number', result.medications[3].uncertain_fields)
        self.assertTrue(all(not m.administrations for m in result.medications))
        self.assertTrue(all(m.instructions_raw == 'Uống khi cần' for m in result.medications))
        # Do not silently extend the last medication into footer/patient text.
        with self.assertRaises(ValueError):
            extract_printed_prescription({'words': words[:-1]})

    def test_second_local_layout(self) -> None:
        path = Path('data/local/module1/test-output/second-layout-evidence.json')
        if not path.exists():
            self.skipTest('Local second-layout evidence is not present')
        result = Extraction.model_validate(extract_printed_prescription(json.loads(path.read_text(encoding='utf-8'))))
        self.assertEqual(len(result.medications), 5)
        self.assertIn('125mg/5ml)', result.medications[0].product_raw)
        self.assertNotIn('125mg/5ml)', result.medications[0].instructions_raw)
        self.assertIn('khi sốt', result.medications[1].instructions_raw)
        self.assertIn('quantity_raw', result.medications[1].uncertain_fields)
        self.assertIn('row_number', result.medications[-1].uncertain_fields)

    def test_product_strengths(self) -> None:
        self.assertEqual(split_product('Drug (Brand) 16 mg'), ('Drug (Brand)', '16 mg', False))
        self.assertEqual(split_product('Cream (30mg + 0,5mg)/g'), ('Cream', '(30mg + 0,5mg)/g', False))
        complex_label = 'Tacrolimus (Protopic (1mg/g Ointment) 0.1%) 10g'
        self.assertEqual(split_product(complex_label), (complex_label, None, True))
        self.assertTrue(split_product('Drug (Brand 10mg')[2])

    def test_advice_boundary_and_phases_without_local_files(self) -> None:
        words = [word('Thuốc', 100, 40), word('điều', 140, 40), word('trị', 180, 40)]
        words += [word('1', 100, 100), word('Drug', 140, 100), word('10mg', 180, 100)]
        words += [word('Sáng 01 viên trong 04 ngày đầu, sáng 0.5 viên trong 04 tiếp theo', 140, 140)]
        words += [word('2', 100, 200), word('Cream', 140, 200), word('1mg/g', 180, 200)]
        words += [word('Bôi buổi tối 01 lần', 140, 240)]
        words += [word('Lời', 100, 280), word('dặn:', 140, 280), word('Tiếp', 180, 274), word('tục', 220, 282)]
        words += [word('Tái khám: Ngày 01/01/2027', 100, 320)]
        parsed = Extraction.model_validate(extract_printed_prescription({'words': words}))
        first, last = parsed.medications
        self.assertEqual([a.phase_raw for a in first.administrations], ['trong 04 ngày đầu', 'trong 04 tiếp theo'])
        self.assertIsNone(first.dose_raw)
        self.assertIsNone(first.frequency_raw)
        self.assertIn('schedule_phases', first.uncertain_fields)
        self.assertNotIn('Tiếp', last.instructions_raw)
        self.assertIn('Tiếp', ' '.join(parsed.document_instructions_raw))
        self.assertNotIn('Tái khám', ' '.join(parsed.document_instructions_raw))
        self.assertIsNone(last.administrations[0].phase_raw)

    def test_bare_consecutive_numbers_are_row_starters(self) -> None:
        words = [word("1", 100, 100), word("01", 400, 130), word("2", 102, 180), word("3", 99, 260)]
        self.assertEqual([item["text"] for item in find_numbered_row_starters(words)], ["1", "2", "3"])

    def test_isolated_dose_number_is_not_a_row_starter(self) -> None:
        self.assertEqual(find_numbered_row_starters([word("01", 400, 130)]), [])

    def test_existing_sample_evidence_has_five_medications(self) -> None:
        evidence = Path("data/local/module1/test-output/image_ocr_evidence.json")
        if not evidence.exists():
            self.skipTest("Local sample evidence is not present")
        result = extract_printed_prescription(json.loads(evidence.read_text(encoding="utf-8")))
        self.assertEqual(len(result["medications"]), 5)
        self.assertEqual(result["medications"][0]["name_raw"], "Methyl prednisolon (MEDROL)")
        self.assertNotIn('Tiếp', result['medications'][-1]['instructions_raw'])
        self.assertIn('Lời dặn:', ' '.join(result['document_instructions_raw']))
        self.assertNotIn('QUÝ KHÁCH', ' '.join(result['document_instructions_raw']))
        self.assertTrue(result["requires_user_review"])


class ApiTest(unittest.TestCase):
    def test_health(self) -> None:
        response = TestClient(app).get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_rejects_non_image_upload(self) -> None:
        response = TestClient(app).post(
            "/api/v1/ocr/extractions",
            files={"file": ("prescription.txt", b"not an image", "text/plain")},
        )
        self.assertEqual(response.status_code, 415)


if __name__ == "__main__":
    unittest.main()
