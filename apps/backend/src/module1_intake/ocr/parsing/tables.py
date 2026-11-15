"""Conservative adapter for name/ingredient and quantity tables."""

import re
import statistics
import unicodedata

from module1_intake.ocr.parsing.products import parse_table_product, parse_quantity_product


from module1_intake.ocr.common.text_geometry import plain, center, reading_lines

def extract_quantity_table(words):
    """Return None unless both table headings and aligned row markers exist.

    Quantity separators locate rows independently of misread ordinal digits.
    No OCR substitutions or medical schedule inference are performed.
    """
    for header in words:
        if plain(header['text']).strip(':.') != 'ten':
            continue
        height = max(1, header['bbox']['y1'] - header['bbox']['y0'])
        heading = [w for w in words if abs(center(w) - center(header)) <= height]
        tokens = {plain(w['text']).strip(':.') for w in heading}
        if not {'thuoc', 'hoat', 'chat', 'so', 'luong'} <= tokens:
            continue
        quantity_header = next(w for w in heading if plain(w['text']).strip(':.') == 'so')
        break
    else:
        return extract_quantity_only_table(words)

    left = header['bbox']['x0'] - height * 5
    quantity_x = quantity_header['bbox']['x0']
    footer = [w['bbox']['y0'] for w in words
              if center(w) > center(header) + height * 2
              and w['bbox']['x0'] < header['bbox']['x0'] + height * 2
              and plain(w['text']).startswith(('ghi', 'cong'))]
    if not footer:
        raise ValueError('Chưa xác định được điểm kết thúc bảng thuốc; cần kiểm tra ảnh')
    end = min(footer)
    region = [w for w in words if center(header) + height < center(w) < end
              and w['bbox']['x0'] >= left]
    anchors = sorted([w for w in region
                      if quantity_x - height * 4 <= w['bbox']['x0'] <= quantity_x
                      and re.fullmatch(r'[“”"\s]*[xX](?:[1IlL])?', w['text'])], key=center)
    if len(anchors) < 2:
        raise ValueError('Chưa tìm đủ mốc cột số lượng để tách bảng thuốc')
    column = statistics.median(w['bbox']['x0'] for w in anchors)
    anchors = [w for w in anchors if abs(w['bbox']['x0'] - column) <= height]
    # Require visible numbered markers on multiple rows; X in prose is not a table.
    markers = []
    for anchor in anchors:
        candidates = [w for w in region if w['bbox']['x0'] < header['bbox']['x0']
                      and abs(center(w) - center(anchor)) <= height]
        markers.append(min(candidates, key=lambda w: w['bbox']['x0']) if candidates else None)
    if sum(bool(w and re.match(r'^\(?\d+(?:[/.)]|$)', w['text'])) for w in markers) < 2:
        raise ValueError('Không đủ bằng chứng số thứ tự trong bảng thuốc')

    medications = []
    for index, anchor in enumerate(anchors):
        top = center(anchor) - height
        bottom = center(anchors[index + 1]) - height if index + 1 < len(anchors) else end
        row = [w for w in region if top <= center(w) < bottom]
        title = [w for w in row if w['bbox']['x0'] < column - height
                 and abs(center(w) - center(anchor)) <= height]
        title.sort(key=lambda w: w['bbox']['x0'])
        title_text = ' '.join(w['text'] for w in title)
        title_text = re.sub(r'^\s*(?:\(?\d+\)?\s*[/.)]?|§\s*/)\s*', '', title_text)
        body = [w for w in row if w['bbox']['x0'] < column - height and w not in title]
        lines = []
        for w in sorted(body, key=center):
            if not lines or abs(center(w) - statistics.mean(center(t) for t in lines[-1])) > height * .75:
                lines.append([w])
            else:
                lines[-1].append(w)
        texts = [' '.join(w['text'] for w in sorted(line, key=lambda t: t['bbox']['x0'])) for line in lines]
        # A wrapped parenthetical product description belongs to the product.
        while texts and title_text.count('(') > title_text.count(')'):
            if not re.match(r'^\s*\d+(?:[.,]\d+)?\s*(?:mg|mcg|g|ml)', texts[0], re.I):
                break
            title_text += '\n' + texts.pop(0)
        quantity = [w for w in row if w['bbox']['x0'] >= column - height
                    and abs(center(w) - center(anchor)) <= height and w is not anchor]
        quantity.sort(key=lambda w: w['bbox']['x0'])
        fields, uncertain = parse_table_product(title_text)
        uncertain.append('instructions_raw')
        # XL may be OCR's merged "X 1"; retain it rather than invent quantity 1.
        if anchor['text'].strip('“”" ').lower() != 'x':
            quantity.insert(0, anchor)
            uncertain.append('quantity_raw')
        if not quantity or not re.fullmatch(r'\d+', quantity[0]['text']):
            if 'quantity_raw' not in uncertain:
                uncertain.append('quantity_raw')
        marker = markers[index]
        if not marker or not re.match(r'^\(?\d+', marker['text']):
            uncertain.append('row_number')
        if any(w.get('confidence', 0) < 85 for w in row):
            uncertain.append('ocr_low_confidence')
        medications.append({
            'product_raw': title_text, **fields,
            'quantity_raw': ' '.join(w['text'] for w in quantity) or None,
            'instructions_raw': '\n'.join(texts) or None,
            'administrations': [], 'schedule_requires_review': True,
            'evidence_text': '\n'.join(reading_lines(row, height * .75)),
            'uncertain_fields': uncertain,
        })
    return {'medications': medications, 'document_instructions_raw': [],
            'warnings': ['Bảng thuốc được tách theo cột số lượng; tên, hàm lượng và hướng dẫn cần xác nhận.'],
            'requires_user_review': True}


def extract_quantity_only_table(words):
    """Require slash ordinals plus an aligned X/quantity column on every row."""
    markers = sorted([w for w in words if re.fullmatch(r'\d+/', w['text'])], key=center)
    if len(markers) < 2:
        return None
    h = statistics.median(w['bbox']['y1']-w['bbox']['y0'] for w in markers)
    if h <= 0 or max(w['bbox']['x0'] for w in markers)-min(w['bbox']['x0'] for w in markers) > h*2:
        return None
    heading = plain(' '.join(w['text'] for w in words if center(w) < center(markers[0])))
    if not re.search(r'so\s+luong', heading):
        return None
    footer = [w['bbox']['y0'] for w in words if center(w) > center(markers[-1])
              and plain(w['text']).strip(':') in ('loi','ghi')
              and abs(w['bbox']['x0']-markers[0]['bbox']['x0']) < h*4]
    if not footer:
        return None
    anchors = []
    for marker in markers:
        matches = [w for w in words if re.fullmatch(r'[xX]\d*', w['text'])
                   and w['bbox']['x0'] > marker['bbox']['x1']+h*5
                   and abs(center(w)-center(marker)) <= h*2]
        if len(matches) != 1:
            return None
        anchors.append(matches[0])
    if max(w['bbox']['x0'] for w in anchors)-min(w['bbox']['x0'] for w in anchors) > h*2:
        return None
    medications = []
    for i, (marker, anchor) in enumerate(zip(markers, anchors)):
        bottom = min(center(markers[i+1]),center(anchors[i+1]))-h if i+1 < len(markers) else min(footer)
        top = min(center(marker),center(anchor))-h
        row = [w for w in words if top <= center(w) < bottom]
        quantity = sorted([w for w in row if w['bbox']['x0'] >= anchor['bbox']['x0']
                           and abs(center(w)-center(anchor)) <= h], key=lambda w:w['bbox']['x0'])
        q = re.sub(r'^[xX]\s*', '', ' '.join(w['text'] for w in quantity))
        if not re.fullmatch(r'\d+\s+(?:vien|lo|goi|chai|ong|tuyp)', plain(q)):
            return None
        left = [w for w in row if marker['bbox']['x0']-h <= w['bbox']['x0'] < anchor['bbox']['x0'] and w is not marker]
        lines = reading_lines(left, h*.7)
        if not lines:
            return None
        product = lines.pop(0)
        while lines and product.count('(') > product.count(')'):
            if re.search(r'\b(?:uong|boi|ngay|sang|toi)\b', plain(lines[0])):
                break
            product += '\n'+lines.pop(0)
        if not lines:
            return None
        fields, flags = parse_quantity_product(product)
        # Bound the product above the first usage line, preserving wrapped description.
        usage = [w for w in left if w['text'] in lines[0].split()]
        cutoff = min((w['bbox']['y0'] for w in usage), default=bottom)
        product_words = [w for w in left if center(w) < cutoff]
        region = None
        if product_words:
            x0 = min(w['bbox']['x0'] for w in product_words)
            y0 = min(w['bbox']['y0'] for w in product_words)
            region = {'left': x0, 'top': y0,
                      'width': max(w['bbox']['x1'] for w in product_words)-x0,
                      'height': max(w['bbox']['y1'] for w in product_words)-y0}
        medications.append({'product_raw': product, **fields, 'quantity_raw': q,
            'product_region': region, 'product_parser': 'quantity_table',
            'instructions_raw': '\n'.join(lines), 'evidence_text': '\n'.join(reading_lines(row,h*.7)),
            'uncertain_fields': flags+['row_number_unverified','instructions_raw','ocr_low_confidence'],
            'schedule_requires_review': True})
    return {'medications':medications,'requires_user_review':True,
            'warnings':['Tách theo cột số lượng và dấu thứ tự; ordinal là vị trí mục, số OCR trong evidence chưa được xác minh.']}
