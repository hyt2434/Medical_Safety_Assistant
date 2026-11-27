"""Conservative fallback for printed product/usage pairs without table headings.

Keep literal OCR and mark every field for review; never repair drug names or doses.
"""
import re
import statistics

from module1_intake.ocr.common.text_geometry import center, plain
from module1_intake.ocr.parsing.products import STRENGTH, parse_table_product


def extract_usage_list(words):
    if not words:
        return None
    height = statistics.median(max(1, w['bbox']['y1'] - w['bbox']['y0']) for w in words)
    groups = []
    for word in sorted(words, key=center):
        if not groups or abs(center(word) - statistics.median(center(w) for w in groups[-1])) > height * .65:
            groups.append([word])
        else:
            groups[-1].append(word)
    lines = []
    for group in groups:
        group.sort(key=lambda w: w['bbox']['x0'])
        lines.append((' '.join(w['text'] for w in group), group))
    usage = re.compile(r'\b(?:uong|cach\s*dung|ngay|ngdy|nady|sang\s*:|chieu\s*:|toi\s*:)')
    ordinal = re.compile(r'^\s*[|\\/\s]*(?:1\s+)?\d{1,2}[.)]\s*')
    footer = re.compile(r'^(?:loi\s*dan|tai\s*kham|bac\s*si|ngay\s+\d+\s+thang|chu\s*ky)\b')
    anchors = []
    for index, (text, group) in enumerate(lines):
        if usage.search(plain(text)) or footer.search(plain(text)):
            continue
        numbered = ordinal.match(text)
        # A damaged/missing ordinal is acceptable only with explicit strength
        # and an immediately following usage line, not arbitrary document text.
        paired = bool(re.search(STRENGTH, text, re.I) and index + 1 < len(lines)
                      and usage.search(plain(lines[index + 1][0])))
        if (numbered or paired) and any(c.isalpha() for c in text):
            anchors.append(index)
    if len(anchors) < 2:
        return None
    medications = []
    corroborated = 0
    for position, index in enumerate(anchors):
        bottom = anchors[position + 1] if position + 1 < len(anchors) else len(lines)
        block = lines[index:bottom]
        end = next((n for n, (text, _) in enumerate(block) if footer.search(plain(text))), len(block))
        block = block[:end]
        instruction_index = next((n for n, (text, _) in enumerate(block) if usage.search(plain(text))), len(block))
        product_lines = []
        quantity = None
        for n, (text, group) in enumerate(block[:instruction_index]):
            # Separate a clearly spaced quantity column; do not strip package
            # sizes or infer quantities from numbers embedded in a product.
            if len(group) >= 3 and group[-2]['text'].isdigit() and plain(group[-1]['text']) in ('vien', 'goi', 'chai', 'ong', 'lo', 'tuyp'):
                if group[-2]['bbox']['x0'] - group[-3]['bbox']['x1'] > height * 3:
                    quantity = ' '.join(w['text'] for w in group[-2:])
                    text = ' '.join(w['text'] for w in group[:-2])
            if n == 0:
                text = ordinal.sub('', text).strip()
            elif product_lines and product_lines[-1].count('(') <= product_lines[-1].count(')'):
                # Unclassified lines remain evidence, never appended to a name.
                break
            product_lines.append(text)
        product = '\n'.join(product_lines)
        instructions = '\n'.join(text for text, _ in block[instruction_index:]) or None
        if not product or not any(c.isalpha() for c in product):
            return None
        if instructions and (quantity or re.search(STRENGTH, product, re.I)):
            corroborated += 1
        fields, flags = parse_table_product(product)
        medications.append({**fields, 'product_raw': product, 'instructions_raw': instructions,
                            'quantity_raw': quantity, 'evidence_text': '\n'.join(text for text, _ in block),
                            'product_parser': 'usage_list', 'schedule_requires_review': True,
                            'uncertain_fields': list(dict.fromkeys(flags + ['name_raw', 'strength_raw', 'instructions_raw', 'ocr_low_confidence']))})
    if corroborated < 2:
        return None
    return {'medications': medications, 'requires_user_review': True,
            'review_guidance': {'action': 'CONFIRM_FIELDS', 'reason': 'FALLBACK_LAYOUT',
                                'message': 'Đã tách bản nháp theo dòng thuốc và cách dùng. Hãy đối chiếu đủ số thuốc, tên, hàm lượng và liều với ảnh gốc; chữ mờ hoặc số thứ tự có thể bị đọc sai.'},
            'warnings': ['Bố cục không có đủ tiêu đề/cột chuẩn. Đây là bản chép OCR cần kiểm tra từng trường; không tự sửa tên hoặc suy đoán liều.']}
