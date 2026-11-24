"""Printed STT/name-strength tables with damaged ordinal OCR."""
import re
import statistics
from module1_intake.ocr.common.text_geometry import plain, center
from module1_intake.ocr.parsing.products import parse_table_product
from module1_intake.ocr.parsing.products import STRENGTH


from module1_intake.ocr.parsing.products import parse_strength_product


def extract_strength_table(words):
    for header in words:
        if plain(header['text']).strip(' .:') != 'stt':
            continue
        height = max(1, header['bbox']['y1'] - header['bbox']['y0'])
        heading = ' '.join(w['text'] for w in sorted(words, key=lambda w: w['bbox']['x0'])
                           if abs(center(w)-center(header)) < height * 1.5)
        if re.search(r'ten\s+thuoc\s*-?\s*ham\s+luong', plain(heading)):
            break
    else:
        return None
    footers = [w for w in words if plain(w['text']) == 'cong' and center(w) > center(header)]
    if not footers:
        raise ValueError('Bảng STT/hàm lượng chưa có mốc kết thúc để kiểm tra đủ mục')
    footer = min(footers, key=center)
    footer_text = ' '.join(w['text'] for w in sorted(words, key=lambda w: w['bbox']['x0'])
                           if abs(center(w)-center(footer)) < height)
    count = re.search(r'cong\s+khoan\s*[:;]?\s*(\d+)\b', plain(footer_text))
    if not count:
        raise ValueError('Chưa đọc được tổng số khoản trong bảng thuốc')
    region = [w for w in words if center(header)+height < center(w) < footer['bbox']['y0']
              and (w['bbox']['x0'] + w['bbox']['x1']) / 2 > header['bbox']['x1']]
    groups = []
    for word in sorted(region, key=center):
        if not groups or abs(center(word) - statistics.median(center(w) for w in groups[-1])) > height:
            groups.append([word])
        else:
            groups[-1].append(word)
    lines = [' '.join(w['text'] for w in sorted(group, key=lambda w: w['bbox']['x0'])) for group in groups]
    starts = [i for i, line in enumerate(lines) if re.search(r'\d\s*(?:mcg|mg)\b', line, re.I)]
    if len(starts) != int(count[1]):
        raise ValueError('Số mục tách được chưa khớp tổng khoản trên bảng; cần kiểm tra ảnh')
    medications = []
    for index, start in enumerate(starts):
        end = starts[index+1] if index+1 < len(starts) else len(lines)
        product = lines[start].lstrip('| ').strip()
        instructions = '\n'.join(lines[start+1:end])
        # Every row must have corroborating usage text, not just a strength.
        if not re.search(r'ngay|uong|chia', plain(instructions)):
            raise ValueError('Chưa ghép được hướng dẫn dùng với từng hàng thuốc')
        fields, flags = parse_strength_product(product)
        # Use the left table boundary, even if the name itself was omitted by OCR.
        product_words = groups[start]
        x0 = int(header['bbox']['x1'] + 1)
        y0 = max(0, int(min(w['bbox']['y0'] for w in product_words) - height * .4))
        x1 = max(w['bbox']['x1'] for w in product_words)
        y1 = max(w['bbox']['y1'] for w in product_words) + 2
        # Limit padding against neighboring lines; do not erase pixels inside words.
        if start:
            previous_bottom = max(w['bbox']['y1'] for w in groups[start-1])
            if previous_bottom < min(w['bbox']['y0'] for w in product_words):
                y0 = max(y0, int((previous_bottom + min(w['bbox']['y0'] for w in product_words))/2))
        if start + 1 < len(groups):
            next_top = min(w['bbox']['y0'] for w in groups[start+1])
            bottom = max(w['bbox']['y1'] for w in product_words)
            if next_top > bottom:
                y1 = min(y1, int((bottom + next_top)/2))
        crop = {'left': x0, 'top': y0, 'width': int(x1-x0+2), 'height': int(y1-y0)}
        medications.append({'product_raw': product, **fields,
            'product_region': crop, 'product_parser': 'strength_table',
            'instructions_raw': instructions, 'evidence_text': '\n'.join(lines[start:end]),
            'uncertain_fields': list(dict.fromkeys(flags + ['row_number_unreadable', 'instructions_raw', 'ocr_low_confidence'])),
            'schedule_requires_review': True})
    return {'medications': medications, 'requires_user_review': True,
            'warnings': ['Tách bảng theo tiêu đề STT/hàm lượng và đối chiếu tổng khoản; thứ tự là vị trí hàng, không phải số OCR đã xác minh. Không suy liều mỗi lần từ tổng liều ngày.']}
