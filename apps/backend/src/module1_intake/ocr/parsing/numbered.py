"""Header-independent numbered prescriptions with corroborating usage evidence."""

import re
import statistics

from module1_intake.ocr.common.text_geometry import center, plain, reading_lines


def parse_timing_labels(instructions):
    """Retain observed schedule labels even when their dose is unreadable."""
    administrations = []
    for line in instructions.splitlines():
        # A colon is required for unreadable values; numeric schedules may omit it.
        labels = [m for m in re.finditer(r'\b([^\W\d_]+)\s*(?::|(?=\d))', line)
                  if plain(m[1]) in ('sang', 'trua', 'chieu', 'toi')]
        for index, label in enumerate(labels):
            end = labels[index + 1].start() if index + 1 < len(labels) else len(line)
            segment = line[label.end():end]
            # Do not swallow same-line instructions as part of a dose.
            boundary = re.search(r'\b(?:cach\s*dung|uong|dung\s+ngoai)\b', plain(segment))
            if boundary:
                segment = segment[:boundary.start()]
            value = segment.strip().rstrip(';').strip()
            dose = re.fullmatch(r'\d+(?:[.,]\d+)?(?:\s*(?:viên|vien|ml|gói|goi|ống|ong|giọt|giot))?', value, re.I)
            administrations.append({
                'timing_raw': label[1],
                'timing_normalized': {'sang': 'morning', 'trua': 'noon', 'chieu': 'afternoon', 'toi': 'evening'}[plain(label[1])],
                'dose_raw': value if dose else None,
                'source_text': (line[label.start():label.end()] + segment).strip(),
                'issue': None if dose else 'unreadable_dose',
            })
    return administrations


def numbered_starters(words):
    candidates = []
    for word in words:
        match = re.match(r'^(\d{1,2})[.)/](?=[^\W\d_]|$)', word['text'].strip())
        if match:
            candidates.append((int(match[1]), word))
    runs = []
    for value, first in candidates:
        if value != 1:
            continue
        run = [first]
        height = max(1, first['bbox']['y1'] - first['bbox']['y0'])
        for expected in range(2, 100):
            options = [w for n, w in candidates if n == expected
                       and center(w) > center(run[-1]) + height
                       and abs(w['bbox']['x0'] - first['bbox']['x0']) <= height * 3]
            if not options:
                break
            run.append(min(options, key=center))
        if len(run) >= 2:
            runs.append(run)
    return max(runs, key=len, default=[])


from module1_intake.ocr.parsing.products import parse_numbered_product as product_fields


def extract_numbered_prescription(words):
    starters = numbered_starters(words)
    if not starters:
        return None
    height = statistics.median(w['bbox']['y1'] - w['bbox']['y0'] for w in starters)
    # Require multiple independent signals; numbered prose alone is insufficient.
    text = plain(' '.join(w['text'] for w in words))
    if not ('don' in text and 'thuoc' in text):
        return None
    first_y = center(starters[0]) - height * 1.5
    left = min(w['bbox']['x0'] for w in starters) - height * 2
    relevant = [w for w in words if center(w) >= first_y and w['bbox']['x0'] >= left]
    quantity_markers = [w for w in relevant if re.match(r'^x(?:\d|$)', w['text'], re.I)
                        and w['bbox']['x0'] > left + height * 15]
    if len(quantity_markers) < 2:
        return None
    column = statistics.median(w['bbox']['x0'] for w in quantity_markers)
    footer_y = None
    page_markers = [w for w in relevant if plain(w['text']) == 'page'
                    and center(w) > center(starters[-1]) + height]
    if page_markers:
        footer_y = min(w['bbox']['y0'] for w in page_markers)
    for w in relevant:
        if center(w) <= center(starters[-1]) + height:
            continue
        if plain(w['text']).strip(':') in ('khi', 'loi', 'ghi', 'tai', 'bac') and w['bbox']['x0'] < left + height * 5:
            nearby = ' '.join(plain(t['text']) for t in sorted(relevant, key=lambda t: t['bbox']['x0'])
                               if abs(center(t)-center(w)) < height)
            if re.search(r'khi tai kham|loi dan|ghi chu|tai kham|bac si', nearby):
                footer_y = min(footer_y, center(w) - height) if footer_y is not None else center(w) - height
                break
    end = footer_y if footer_y is not None else max(center(w) for w in relevant) + height
    medications = []
    matched = 0
    for index, starter in enumerate(starters):
        top = center(starter) - height * 1.5
        bottom = center(starters[index+1]) - height * 1.5 if index+1 < len(starters) else end
        row = [w for w in relevant if top <= center(w) < bottom]
        row_markers = [w for w in quantity_markers if w in row]
        marker = min(row_markers, key=lambda w: abs(center(w)-center(starter))) if row_markers else None
        boundary = marker['bbox']['x0'] if marker else column
        left_top = center(starter) - height * .6
        left_bottom = center(starters[index+1]) - height * .6 if index+1 < len(starters) else end
        left_words = [w for w in relevant if left_top <= center(w) < left_bottom
                      and w['bbox']['x0'] < boundary and w is not starter]
        evidence_left = [starter, *left_words]
        attached_name = re.sub(r'^\d{1,2}[.)/]', '', starter['text'].strip())
        if attached_name:
            left_words.append({**starter, 'text': attached_name})
        right_words = [w for w in row if w['bbox']['x0'] >= boundary
                       and (marker is None or abs(center(w)-center(marker)) < height * .8)]
        lines = reading_lines(left_words, height * .8)
        quantity_text = ' '.join(reading_lines(right_words, height))
        quantity = re.search(r'[xX]\s*(\d+\s*ng[aà]y)\s*:?\s*=\s*(\d+\s*\S+)', quantity_text)
        if quantity:
            matched += 1
        instruction_index = next((i for i, line in enumerate(lines)
                                  if re.search(r'sang\s*:|chieu\s*:|toi\s*:?\s*\d|cach\s*dung|uong', plain(line))), len(lines))
        # Only carry product continuations with open parentheses or a leading +/(.
        for i in range(1, instruction_index):
            previous = ' '.join(lines[:i])
            if previous.count('(') <= previous.count(')') and not previous.rstrip().endswith('+') and not lines[i].lstrip().startswith(('+', '(')):
                instruction_index = i
                break
        product = '\n'.join(lines[:instruction_index])
        groups = []
        for word in sorted(left_words, key=center):
            if not groups or abs(center(word) - statistics.median(center(w) for w in groups[-1])) > height * .8:
                groups.append([word])
            else:
                groups[-1].append(word)
        product_words = [w for group in groups[:instruction_index] for w in group]
        product_region = None
        if product_words:
            x0 = max(0, int(min(w['bbox']['x0'] for w in product_words) - 3))
            y0 = max(0, int(min(w['bbox']['y0'] for w in product_words) - 3))
            product_region = {'left': x0, 'top': y0,
                              'width': int(min(boundary - 2, max(w['bbox']['x1'] for w in product_words) + 3) - x0),
                              'height': int(max(w['bbox']['y1'] for w in product_words) + 3 - y0)}
        instructions = '\n'.join(lines[instruction_index:]) or None
        fields, flags = product_fields(product)
        if not quantity:
            flags.extend(['duration_raw', 'quantity_raw'])
        administrations = []
        if instructions:
            administrations = parse_timing_labels(instructions)
            if any(a['dose_raw'] and re.fullmatch(r'\d+(?:[.,]\d+)?', a['dose_raw']) for a in administrations):
                flags.append('dose_unit_missing')
            if any(a['issue'] for a in administrations):
                flags.append('schedule_incomplete')
            flags.append('instructions_raw')
        else:
            flags.append('instructions_raw')
        evidence_words = evidence_left + right_words
        if any(w.get('confidence', 0) < 85 for w in evidence_words):
            flags.append('ocr_low_confidence')
        route = re.search(r'\b(Uống|Dùng ngoài|Xịt)\b', instructions or '', re.I)
        frequency = re.search(r'\bngày\s+\d+\s+lần\b', instructions or '', re.I)
        # Coordinates belong to the same input image used by Tesseract.
        usage_words = [w for w in left_words
                       if plain(w['text']).startswith(('cach', '(cach'))]
        region = None
        # A spray instruction without time-of-day labels is not a lost oral schedule.
        explicit_spray = route is not None and plain(route[0]) == 'xit' and not administrations
        if usage_words and not explicit_spray:
            region_top = int(starter['bbox']['y1'] + 2)
            region_bottom = int(min(w['bbox']['y0'] for w in usage_words) - 2)
            region_left = max(0, int(min(w['bbox']['x0'] for w in left_words) - height * .4))
            region_right = int(boundary - height)
            if region_bottom > region_top and region_right > region_left:
                region = {'left': region_left, 'top': region_top,
                          'width': region_right - region_left,
                          'height': region_bottom - region_top}
        medications.append({'product_raw': product, **fields,
                            'product_region': product_region,
                            'duration_raw': quantity[1] if quantity else None,
                            'quantity_raw': quantity[2] if quantity else None,
                            'instructions_raw': instructions,
                            'route_raw': route[0] if route else None,
                            'frequency_raw': frequency[0] if frequency else None,
                            'administrations': administrations,
                            'schedule_region': region,
                            'evidence_text': '\n'.join(reading_lines(evidence_words, height * .8)),
                            'uncertain_fields': list(dict.fromkeys(flags)),
                            'schedule_requires_review': True})
    if matched < 2:
        return None
    return {'medications': medications,
            'document_instructions_raw': reading_lines([w for w in relevant if footer_y is not None and center(w) >= footer_y], height),
            'warnings': ['Bố cục đánh số có thời gian/số lượng; kiểm tra đơn vị liều và nội dung OCR trước khi xác nhận.'],
            'requires_user_review': True}
