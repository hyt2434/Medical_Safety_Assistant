"""Numbered prescriptions corroborated by quantities and usage, without table headings."""
import re
from module1_intake.ocr.common.text_geometry import plain, center, reading_lines
from module1_intake.ocr.parsing.products import parse_table_product


def extract_headerless(words):
    from module1_intake.ocr.parsing.legacy import find_numbered_row_starters
    text = plain(' '.join(w['text'] for w in words))
    if not re.search(r'don\s+thuoc', text):
        return None
    starters = find_numbered_row_starters(words)
    if len(starters) < 2 or [w['text'].strip(' .)/') for w in starters] != [str(i+1) for i in range(len(starters))]:
        return None
    h = max(1, starters[0]['bbox']['y1']-starters[0]['bbox']['y0'])
    footers = [w['bbox']['y0'] for w in words if center(w) > center(starters[-1])
               and plain(w['text']).strip(':') in ('loi', 'tai')
               and abs(w['bbox']['x0']-starters[0]['bbox']['x0']) < h*3]
    if not footers:
        return None
    medications = []
    for i, anchor in enumerate(starters):
        bottom = center(starters[i+1])-h*2 if i+1 < len(starters) else min(footers)
        row = [w for w in words if center(anchor)-h*2 <= center(w) < bottom
               and w['bbox']['x0'] >= anchor['bbox']['x0']-h]
        title = sorted([w for w in row if abs(center(w)-center(anchor)) <= h*2], key=lambda w:w['bbox']['x0'])
        # Quantity must form the rightmost two tokens, beyond the product.
        if len(title) < 4 or not title[-2]['text'].isdigit() or plain(title[-1]['text']) not in ('vien','goi','lo','chai','ong','tuyp'):
            return None
        product_words = [w for w in title[:-2] if w is not anchor]
        product = ' '.join(w['text'] for w in product_words)
        body = [w for w in row if w not in title]
        instructions = '\n'.join(reading_lines(body, h*.7))
        if not product or not re.search(r'uong|ngay|sang|chieu|toi', plain(instructions)):
            return None
        fields, flags = parse_table_product(product)
        duration = re.search(r'\b\d+\s+ngày\b', instructions, re.I)
        medications.append({'product_raw':product, **fields,
            'duration_raw':duration[0] if duration else None,
            'quantity_raw':' '.join(w['text'] for w in title[-2:]),
            'instructions_raw':instructions,'evidence_text':'\n'.join(reading_lines(row,h*.7)),
            'uncertain_fields':flags+['instructions_raw'], 'schedule_requires_review':True})
    return {'medications':medications,'requires_user_review':True,
            'warnings':['Danh sách không có tiêu đề bảng; đối chiếu số thứ tự, số lượng và hướng dẫn trước khi xác nhận.']}
