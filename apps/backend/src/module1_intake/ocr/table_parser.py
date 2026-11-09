"""Conservative adapter for name/ingredient and quantity tables."""

import re
import statistics
import unicodedata

from .product_fields import parse_table_product


def plain(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower())
                   if unicodedata.category(c) != 'Mn').replace('đ', 'd')


def center(word):
    return (word['bbox']['y0'] + word['bbox']['y1']) / 2


def reading_lines(words, tolerance):
    """Cluster by vertical centers, then read left-to-right within each line."""
    lines = []
    for word in sorted(words, key=center):
        if not lines or abs(center(word) - statistics.median(center(w) for w in lines[-1])) > tolerance:
            lines.append([word])
        else:
            lines[-1].append(word)
    return [' '.join(w['text'] for w in sorted(line, key=lambda w: w['bbox']['x0']))
            for line in lines]


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
        return None

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
