from module1_intake.ocr.parsing.dispatcher import extract_printed_prescription
from module1_intake.ocr.parsing.usage_list import extract_usage_list


def evidence(lines):
    words = []
    for row, line in enumerate(lines):
        x = 20
        for token in line.split():
            width = len(token) * 8
            words.append({'text': token, 'confidence': 90,
                          'bbox': {'x0': x, 'x1': x + width, 'y0': row * 30, 'y1': row * 30 + 14}})
            x += width + 8
    return words


def test_cropped_numbered_usage_without_header_footer_or_quantity_column():
    words = evidence(['1. TestAlpha 40mg (IngredientAlpha 40mg)', 'Ngày uống 3 lần, mỗi lần 1 viên',
                      '2. TestBeta 5mg', 'Ngày uống 2 lần, mỗi lần 1 viên',
                      '4. TestGamma (IngredientGamma)', 'Ngày uống 1 lần, mỗi lần 1 viên'])
    result = extract_printed_prescription({'words': words})
    assert len(result['medications']) == 3
    assert result['medications'][0]['strength_raw'] == '40mg'
    assert result['medications'][2]['strength_raw'] is None
    assert result['medications'][1]['instructions_raw'] == 'Ngày uống 2 lần, mỗi lần 1 viên'
    assert all(item['schedule_requires_review'] for item in result['medications'])
    assert all('name_raw' in item['uncertain_fields'] for item in result['medications'])
    assert result['review_guidance']['reason'] == 'FALLBACK_LAYOUT'


def test_missing_ordinal_needs_strength_and_adjacent_usage():
    result = extract_usage_list(evidence(['TestAlpha 40mg', 'Ngày uống 1 lần, mỗi lần 1 viên',
                                         'TestBeta 5mg', 'Ngày uống 2 lần, mỗi lần 1 viên']))
    assert len(result['medications']) == 2
    assert result['medications'][0]['name_raw'] == 'TestAlpha'


def test_numbered_prose_and_dosing_advice_are_not_medication_lists():
    assert extract_usage_list(evidence(['1. Uống nước mỗi ngày', '2. Ăn uống điều độ'])) is None
    assert extract_usage_list(evidence(['1. Xét nghiệm 40mg', '2. Báo cáo 5mg'])) is None
    assert extract_usage_list(evidence(['1. Buổi sáng', 'Ngày uống nước', '2. Buổi chiều', 'Ngày uống nước'])) is None


def test_unbalanced_product_stays_literal_and_is_flagged():
    result = extract_usage_list(evidence(['1. TestAlpha 40mg (Ingredient', 'Ngày uống 1 lần',
                                         '2. TestBeta 5mg', 'Ngày uống 2 lần']))
    assert result['medications'][0]['product_raw'] == 'TestAlpha 40mg (Ingredient'
    assert 'product_structure' in result['medications'][0]['uncertain_fields']
    assert result['medications'][0]['strength_raw'] is None
