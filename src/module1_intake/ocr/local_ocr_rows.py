"""Conservative adapter for numbered, printed medication columns.

Only Tesseract words/geometry are inputs. Never reads a drug dictionary or truth.
Returns None for older layouts so their existing adapter stays available.
"""
import re
import unicodedata


def find_numbered_row_starters(words):
    """Return an aligned, consecutive medication-row number sequence.

    Punctuated numbers keep the historical behavior. Bare numbers are accepted
    only when they form a sequence beginning at 1 in approximately one column;
    this prevents doses such as ``01 viên`` from becoming medication rows.
    """
    punctuated = [w for w in words if re.fullmatch(r'\d+[.)]', w['text'].strip())]
    if punctuated:
        return sorted(punctuated, key=lambda w: w['bbox']['y0'])

    candidates = []
    for word in words:
        match = re.fullmatch(r'(\d+)', word['text'].strip())
        if match and 1 <= int(match.group(1)) <= 50:
            candidates.append((int(match.group(1)), word))
    if not candidates:
        return []

    heights = sorted(max(1, w['bbox']['y1'] - w['bbox']['y0']) for _, w in candidates)
    median_height = heights[len(heights) // 2]
    x_tolerance = max(12, median_height * 2)
    max_y_gap = max(90, median_height * 9)
    runs = []
    for number, first in candidates:
        if number != 1:
            continue
        run = [first]
        expected = 2
        previous = first
        while True:
            matches = [word for value, word in candidates
                       if value == expected
                       and 0 < word['bbox']['y0'] - previous['bbox']['y0'] <= max_y_gap
                       and abs(word['bbox']['x0'] - first['bbox']['x0']) <= x_tolerance]
            if not matches:
                break
            previous = min(matches, key=lambda w: w['bbox']['y0'])
            run.append(previous)
            expected += 1
        if len(run) >= 2:
            runs.append(run)
    return max(runs, key=lambda run: (len(run), -run[0]['bbox']['y0']), default=[])


def _plain(text):
    value = ''.join(character for character in unicodedata.normalize('NFD', text.casefold())
                    if unicodedata.category(character) != 'Mn')
    return value.replace('đ', 'd')


def _join_lines(words, line_tolerance):
    lines = []
    for word in sorted(words, key=lambda item: (item['bbox']['y0'], item['bbox']['x0'])):
        center = (word['bbox']['y0'] + word['bbox']['y1']) / 2
        if not lines or abs(center - lines[-1][0]) > line_tolerance:
            lines.append([center, [word]])
        else:
            lines[-1][1].append(word)
            lines[-1][0] = sum((item['bbox']['y0'] + item['bbox']['y1']) / 2
                               for item in lines[-1][1]) / len(lines[-1][1])
    return [' '.join(item['text'] for item in sorted(line, key=lambda item: item['bbox']['x0']))
            for _, line in lines]


def _hospital_header(words, first_starter):
    candidates = []
    for word in words:
        if (_plain(word['text']).strip(':') != 'thuoc'
                or word['bbox']['y0'] >= first_starter['bbox']['y0']
                or abs(word['bbox']['x0'] - first_starter['bbox']['x0']) > 120):
            continue
        same_line = {_plain(item['text']).strip(':,.') for item in words
                     if abs(item['bbox']['y0'] - word['bbox']['y0']) <= 16}
        if {'dieu', 'tri'} <= same_line:
            candidates.append(word)
    return max(candidates, key=lambda item: item['bbox']['y0'], default=None)


def _extract_hospital_rows(words, starters, header):
    heights = sorted(max(1, word['bbox']['y1'] - word['bbox']['y0']) for word in words)
    median_height = heights[len(heights) // 2]
    left_edge = min(starter['bbox']['x0'] for starter in starters) - median_height
    advice_y = min((word['bbox']['y0'] for word in words
                    if word['bbox']['y0'] > starters[-1]['bbox']['y0']
                    and word['bbox']['x0'] >= left_edge
                    and _plain(word['text']).strip(':') == 'loi'),
                   default=None)
    instruction_end = (advice_y - median_height * .6 if advice_y is not None
                       else starters[-1]['bbox']['y0'] + median_height * 10)
    strength_pattern = re.compile(r'\d+(?:[.,]\d+)?\s*(?:mcg|mg|g|ml|%)(?:/(?:g|ml))?', re.I)
    administration_pattern = re.compile(
        r'(?P<timing>Sáng|Trưa|Chiều|Tối)\s*:?\s*(?P<dose>\d+(?:[.,]\d+)?)\s*'
        r'(?P<unit>viên|ống|gói|muỗng|ml)', re.I)
    topical_pattern = re.compile(
        r'buổi\s+(?P<timing>sáng|trưa|chiều|tối)\s+(?P<dose>\d+(?:[.,]\d+)?)\s+lần', re.I)
    medications = []
    for index, starter in enumerate(starters):
        y = starter['bbox']['y0']
        row_end = starters[index + 1]['bbox']['y0'] if index + 1 < len(starters) else instruction_end
        title_words = sorted([word for word in words
                              if word['bbox']['x0'] > starter['bbox']['x1']
                              and abs(word['bbox']['y0'] - y) <= median_height],
                             key=lambda item: item['bbox']['x0'])
        gaps = [(title_words[position + 1]['bbox']['x0'] - title_words[position]['bbox']['x1'], position)
                for position in range(len(title_words) - 1)]
        large_gaps = [item for item in gaps if item[0] >= max(60, median_height * 3)]
        split_at = max(large_gaps)[1] + 1 if large_gaps else len(title_words)
        product_words = title_words[:split_at]
        quantity_words = title_words[split_at:]
        quantity_x = quantity_words[0]['bbox']['x0'] if quantity_words else float('inf')
        duration_x = quantity_x - median_height if quantity_words else float('inf')

        strength_at = next((position for position, word in enumerate(product_words)
                            if strength_pattern.search(word['text'])), None)
        if strength_at is None:
            name_words, strength_words = product_words, []
        else:
            name_words, strength_words = product_words[:strength_at], product_words[strength_at:]

        body_words = [word for word in words
                      if y + median_height < word['bbox']['y0'] < row_end - 2
                      and left_edge <= word['bbox']['x0'] < duration_x]
        duration_words = [word for word in words
                          if y + median_height < word['bbox']['y0'] < row_end - 2
                          and word['bbox']['x0'] >= duration_x]
        instruction_lines = _join_lines(body_words, max(8, median_height * .75))
        instructions = '\n'.join(instruction_lines) or None
        duration = ' '.join(_join_lines(duration_words, max(8, median_height * .75))) or None
        administrations = []
        if instructions:
            for match in administration_pattern.finditer(instructions):
                administrations.append({'timing_raw': match.group('timing'),
                                        'dose_raw': f"{match.group('dose')} {match.group('unit')}"})
            for match in topical_pattern.finditer(instructions):
                administrations.append({'timing_raw': match.group('timing'),
                                        'dose_raw': f"{match.group('dose')} lần"})
        uncertain = []
        if not name_words:
            uncertain.append('name_raw')
        if not strength_words:
            uncertain.append('strength_raw')
        if not quantity_words:
            uncertain.append('quantity_raw')
        evidence_words = product_words + quantity_words + body_words + duration_words
        if any(word['confidence'] < 85 for word in evidence_words):
            uncertain.append('ocr_low_confidence')
        route = None
        if instructions:
            first = instructions.split()[0].strip(' ,.;:')
            if _plain(first).startswith('uong') or _plain(first).startswith('dungngoai'):
                route = first
        timing_spans = [item['timing_raw'] for item in administrations]
        dose_spans = [item['dose_raw'] for item in administrations]
        medications.append({
            'name_raw': ' '.join(word['text'] for word in name_words) or None,
            'strength_raw': ' '.join(word['text'] for word in strength_words) or None,
            'dose_raw': '\n'.join(dose_spans) or None,
            'route_raw': route,
            'frequency_raw': '\n'.join(timing_spans) or None,
            'duration_raw': duration,
            'quantity_raw': ' '.join(word['text'] for word in quantity_words) or None,
            'instructions_raw': instructions,
            'administrations': administrations,
            'evidence_text': '\n'.join(_join_lines(evidence_words, max(8, median_height * .75))),
            'uncertain_fields': uncertain,
        })
    return {'medications': medications, 'document_instructions_raw': [],
            'warnings': ['Hospital printed-prescription layout; every literal field requires confirmation'],
            'requires_user_review': True}


def extract_printed_rows(raw):
    words=raw['words']
    starters=find_numbered_row_starters(words)
    if starters:
        header = _hospital_header(words, starters[0])
        if header is not None:
            return _extract_hospital_rows(words, starters, header)
    # Product names may contain "Strength". A column header must precede rows.
    first_y=starters[0]['bbox']['y0'] if starters else float('inf')
    headers=[w for w in words if w['text'].casefold().strip(':')=='strength' and w['bbox']['y0']<first_y]
    if len(headers)!=1: return None
    cutoff=headers[0]['bbox']['x0']-35
    if not starters: raise ValueError('No numbered medication rows found')
    medications=[]
    for i,starter in enumerate(starters):
        y=starter['bbox']['y0']
        line=sorted([w for w in words if abs(w['bbox']['y0']-y)<25 and w['bbox']['x0']>starter['bbox']['x1']],key=lambda w:w['bbox']['x0'])
        names=[w for w in line if w['bbox']['x0']<cutoff]
        strengths=[w for w in line if w['bbox']['x0']>=cutoff]
        name=' '.join(w['text'] for w in names) or None
        strength=' '.join(w['text'] for w in strengths) or None
        next_y=starters[i+1]['bbox']['y0'] if i+1<len(starters) else y+160
        below=[w for w in words if y+30<w['bbox']['y0']<next_y-20]
        anchors=[w for w in below if w['text'].casefold() in ('form:','form')]
        form_words=[]
        if len(anchors)==1:
            anchor=anchors[0]
            form_words=sorted([w for w in below if abs(w['bbox']['y0']-anchor['bbox']['y0'])<20 and w['bbox']['x0']>anchor['bbox']['x1']],key=lambda w:w['bbox']['x0'])
        form=' '.join(w['text'] for w in form_words) or None
        uncertain=[]
        if not name: uncertain.append('name_raw')
        if not strength: uncertain.append('strength_raw')
        if not form: uncertain.append('dosage_form_raw')
        if any(w['confidence']<85 for w in names+strengths+form_words): uncertain.append('ocr_low_confidence')
        medications.append({'name_raw':name,'strength_raw':strength,'dosage_form_raw':form,
            'dose_raw':None,'route_raw':None,'frequency_raw':None,'duration_raw':None,'quantity_raw':None,
            'instructions_raw':None,'administrations':[],
            'evidence_text':' '.join(w['text'] for w in line+form_words),'uncertain_fields':uncertain})
    return {'medications':medications,'document_instructions_raw':[],
        'warnings':['Printed enumerated rows only; literal fields require confirmation'], 'requires_user_review':True}
