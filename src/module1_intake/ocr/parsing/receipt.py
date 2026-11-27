"""Conservative receipt adapter. Missing OCR cells remain missing."""
import re
import statistics
from module1_intake.ocr.common.text_geometry import plain, center


def extract_receipt(words):
    text = plain(' '.join(w['text'] for w in words))
    if not re.search(r'bang\s+ke\s+thu', text):
        return None
    heights = [w['bbox']['y1'] - w['bbox']['y0'] for w in words if w['text'].strip()]
    height = statistics.median(heights)
    lines = []
    for word in sorted(words, key=center):
        if not lines or abs(center(word) - statistics.median(center(w) for w in lines[-1])) > height * .75:
            lines.append([word])
        else:
            lines[-1].append(word)
    lines = [sorted(line, key=lambda w: w['bbox']['x0']) for line in lines]
    def line_text(line):
        return ' '.join(w['text'] for w in line)
    header = next((i for i, line in enumerate(lines) if 'ten hang hoa' in plain(line_text(line))), None)
    if header is None:
        raise ValueError('Bảng kê được nhận diện nhưng chưa tìm được cột tên hàng hóa')
    # Unit column locates the boundary independently of damaged price headings.
    units = [w for line in lines[header+1:] for w in line
             if plain(w['text']) in ('vien', 'chai', 'hop', 'goi', 'ong', 'tuyp')]
    if not units:
        raise ValueError('Chưa xác định được cột đơn vị của bảng kê')
    unit_x = statistics.median(w['bbox']['x0'] for w in units)
    items = []
    group = None
    total = None
    for line in lines[header+1:]:
        literal = line_text(line)
        normalized = plain(literal)
        if re.search(r'\b(?:tong|teng)\s+cong\b', normalized):
            amounts = re.findall(r'\d[\d.,]*', literal)
            total = amounts[-1] if amounts else None
            break
        if re.match(r'^I{1,3}[.)]\s', literal, re.I):
            group = literal
            continue
        if not group:
            continue
        if re.match(r'^so\s', normalized) or 'hsd' in normalized:
            if items:
                item = items[-1]
                item['evidence_text'] += '\n' + literal
                item['item_region']['height'] = int(max(w['bbox']['y1'] for w in line) + height * .3 - item['item_region']['top'])
                lot = re.search(r'^so\s+lo\s*:\s*(\S+)', normalized)
                expiry = re.search(r'HSD\s*:\s*(\S+)', literal, re.I)
                if lot:
                    item['lot_number_raw'] = lot[1]
                else:
                    item['uncertain_fields'].append('lot_number_raw')
                if expiry:
                    item['expiry_date_raw'] = expiry[1]
            continue
        name_words = [w for w in line if w['bbox']['x0'] < unit_x - height]
        # Noise and separators are retained in full OCR, never made into products.
        if not name_words or max(w.get('confidence', 0) for w in name_words) < 60:
            continue
        if not all(w['bbox']['y1'] - w['bbox']['y0'] > height * .45 for w in name_words):
            continue
        name = line_text(name_words)
        cells = [w['text'] for w in line if w not in name_words]
        unit = cells.pop(0) if cells and plain(cells[0]) in ('vien', 'chai', 'hop', 'goi', 'ong', 'tuyp') else None
        numeric = [value for value in cells if re.fullmatch(r'\d+(?:[.,]\d+)*', value)]
        quantity = numeric[0] if unit and len(numeric) == 3 else None
        price, amount = numeric[-2:] if len(numeric) >= 2 else (None, None)
        package = re.search(r'\b\d+(?:[.,]\d+)?\s*ml\b', name, re.I)
        item = {'group_raw': group, 'product_raw': name, 'unit_raw': unit,
                'item_region': {'left': max(0, int(min(w['bbox']['x0'] for w in line) - height * .3)),
                                'top': max(0, int(min(w['bbox']['y0'] for w in line) - height * .8)),
                                'width': 1, 'height': int(height * 3.5)},
                'item_rechecks': [],
                'quantity_raw': quantity, 'unit_price_raw': price, 'amount_raw': amount,
                'package_size_raw': package[0] if package else None,
                'lot_number_raw': None, 'expiry_date_raw': None,
                'evidence_text': literal, 'uncertain_fields': []}
        item['uncertain_fields'] = [key for key in ('unit_raw', 'quantity_raw', 'unit_price_raw', 'amount_raw') if item[key] is None]
        items.append(item)
    if not items:
        raise ValueError('Chưa tách được mặt hàng trong bảng kê')
    right = max(w['bbox']['x1'] for w in words)
    for index, item in enumerate(items):
        region = item['item_region']
        region['width'] = int(right - region['left'])
        if index + 1 < len(items):
            region['height'] = min(region['height'], items[index+1]['item_region']['top'] - region['top'])
        item['field_status'] = {key: 'not_extracted' if item[key] is None else 'extracted_unconfirmed'
                                for key in ('unit_raw', 'quantity_raw', 'unit_price_raw', 'amount_raw', 'lot_number_raw', 'expiry_date_raw')}
        item['uncertain_fields'] = [key for key, status in item['field_status'].items() if status == 'not_extracted']
    medications = [{'product_raw': item['product_raw'], 'name_raw': item['product_raw'],
                    'package_size_raw': item['package_size_raw'],
                    'quantity_raw': ' '.join(filter(None, (item['quantity_raw'], item['unit_raw']))) or None,
                    'evidence_text': item['evidence_text'], 'schedule_requires_review': False,
                    'uncertain_fields': item['uncertain_fields'] + ['purchase_not_confirmed_as_current_medication']}
                   for item in items if re.fullmatch(r'i[.)]\s*thuoc', plain(item['group_raw']))]
    return {'document_type': 'PHARMACY_RECEIPT', 'receipt_items': items,
            'receipt_total_raw': total, 'medications': medications,
            'warnings': ['Bảng kê mua hàng không cung cấp liều dùng; xác nhận sản phẩm đang sử dụng. Các ô OCR thiếu được giữ trống.'],
            'requires_user_review': True}
