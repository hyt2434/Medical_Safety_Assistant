"""Route OCR evidence to supported document layouts."""
from module1_intake.ocr.parsing.legacy import find_numbered_row_starters, split_product, extract_legacy_prescription
from module1_intake.ocr.parsing.receipt import extract_receipt
from module1_intake.ocr.parsing.strength_table import extract_strength_table
from module1_intake.ocr.parsing.tables import extract_quantity_table
from module1_intake.ocr.parsing.numbered import extract_numbered_prescription
from module1_intake.ocr.parsing.headerless import extract_headerless

def extract_printed_prescription(raw):
    words = raw.get('words') or []
    for parser in (extract_receipt, extract_strength_table, extract_quantity_table,
                   extract_numbered_prescription, extract_headerless):
        result = parser(words)
        if result is not None:
            return result
    return extract_legacy_prescription(words)
