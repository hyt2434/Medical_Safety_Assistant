"""Conservative parsing: unresolved semantics stay visible, never guessed."""
from datetime import datetime
from decimal import Decimal, InvalidOperation
import json
import re
import unicodedata
from .common import digest

ALIASES = {
    'registration_number': ['Số GPLH', 'Số đăng ký', 'Số ĐKLH'],
    'brand_name': ['Tên thuốc'], 'ingredients': ['Hoạt chất'], 'strength': ['Hàm lượng'],
    'dosage_form': ['Dạng bào chế'], 'manufacturer': ['Tên công ty sản xuất', 'Cơ sở sản xuất'],
    'previous_registration_number': ['Số đăng ký cũ'], 'decision_number': ['Số quyết định'],
    'valid_until': ['Ngày hết hạn SĐK', 'Ngày hết hạn'], 'effective_date': ['Ngày cấp'],
    'packaging': ['Quy cách đóng gói'], 'route': ['Đường dùng'], 'event_type': ['Loại sự kiện'],
    'claimed_status': ['Trạng thái'],
}
FORMS = {
    'viên nén': 'tablet', 'viên nén bao phim': 'film_coated_tablet',
    'viên nang cứng': 'hard_capsule', 'viên nang mềm': 'soft_capsule',
    'dung dịch uống': 'oral_solution', 'dung dịch tiêm': 'injection_solution',
    'viên nén giải phóng kéo dài': 'extended_release_tablet',
    'bột pha hỗn dịch uống': 'powder_for_oral_suspension',
    'tablet': 'tablet', 'hard capsule': 'hard_capsule',
}
UNITS = {'g': ('mg', Decimal(1000)), 'mg': ('mg', Decimal(1)),
         'mcg': ('mg', Decimal('.001')), 'µg': ('mg', Decimal('.001')),
         'μg': ('mg', Decimal('.001')), 'ug': ('mg', Decimal('.001')),
         'ml': ('mL', Decimal(1)), 'l': ('mL', Decimal(1000)),
         'iu': ('IU', Decimal(1)), 'ui': ('IU', Decimal(1)), '%': ('%', Decimal(1))}
NUMBER = r'\d+(?:[.,]\d+)?'
STRENGTH = re.compile(rf'^\s*({NUMBER})\s*(mg|mcg|µg|μg|ug|g|ml|l|iu|ui|%)'
                      rf'(?:\s*/\s*({NUMBER})?\s*(ml|l|g|mg|viên|tablet|capsule|dose))?\s*$', re.I)


def text(value):
    return unicodedata.normalize('NFC', str(value or '')).strip()


def key(value):
    return ' '.join(text(value).casefold().split())


def decimal_string(value):
    return format(value.normalize(), 'f')


def parse_strength(raw):
    result = {'raw': text(raw), 'status': 'UNRESOLVED', 'amount': None, 'unit': None,
              'denominator_amount': None, 'denominator_unit': None,
              'basis': 'UNSPECIFIED', 'percent_basis': None}
    match = STRENGTH.fullmatch(text(raw))
    if not match:
        return result
    amount, unit, denominator, denominator_unit = match.groups()
    # A nonzero number with exactly three separator-following digits can mean
    # a decimal or a thousands grouping in mixed-locale exports. Preserve for review.
    if re.fullmatch(r'[1-9]\d*[.,]\d{3}', amount) or (denominator and re.fullmatch(r'[1-9]\d*[.,]\d{3}', denominator)):
        return result
    amount = Decimal(amount.replace(',', '.'))
    if amount <= 0:
        return result
    canonical_unit, factor = UNITS[unit.casefold()]
    result.update(status='PARSED', amount=decimal_string(amount * factor), unit=canonical_unit)
    if canonical_unit == '%':
        result['status'] = 'REVIEW_REQUIRED'  # w/w, w/v, v/v absent; never infer a concentration
    if denominator_unit:
        du = denominator_unit.casefold()
        dunit, dfactor = UNITS.get(du, (du, Decimal(1)))
        dvalue = Decimal((denominator or '1').replace(',', '.'))
        if dvalue <= 0:
            result['status'] = 'UNRESOLVED'
            return result
        result.update(denominator_amount=decimal_string(dvalue * dfactor), denominator_unit=dunit)
    return result


def canonicalize(row, column_map):
    """Explicit map is canonical-field -> exact export header. Conflicting aliases fail per row."""
    result = {}
    problems = []
    for field, aliases in ALIASES.items():
        names = [column_map[field]] if field in column_map else [field, *aliases]
        found = [row[n] for n in names if n in row and row[n] is not None and row[n] != '']
        if len({json.dumps(v, ensure_ascii=False, sort_keys=True) for v in found}) > 1:
            problems.append(('CONFLICTING_COLUMNS_' + field, 'ERROR', 'Provide an explicit column map'))
        result[field] = found[0] if found else ''
    return result, problems


def split_components(raw):
    # Split only explicit semicolon/plus outside parentheses; slash and comma are ambiguous.
    parts = []
    start = depth = 0
    for i, char in enumerate(raw):
        if char == '(':
            depth += 1
        elif char == ')':
            depth -= 1
        elif char in ';+' and depth == 0:
            parts.append(raw[start:i].strip())
            start = i + 1
        if depth < 0:
            raise ValueError('Unbalanced ingredient parentheses')
    if depth:
        raise ValueError('Unbalanced ingredient parentheses')
    parts.append(raw[start:].strip())
    if any(not p for p in parts):
        raise ValueError('Empty ingredient component')
    return parts


def components(raw, strength):
    problems = []
    if isinstance(raw, str) and raw.lstrip().startswith('['):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return [], [('INVALID_COMPONENT_JSON', 'ERROR', 'Expected JSON component array')]
    if isinstance(raw, list):
        result = []
        if not raw:
            return [], [('MISSING_INGREDIENTS', 'ERROR', 'No components')]
        for c in raw:
            if not isinstance(c, dict) or not isinstance(c.get('name'), str) or not c['name'].strip():
                return [], [('INVALID_COMPONENT', 'ERROR', 'Each component needs a source name')]
            result.append({'name_raw': text(c['name']), 'strength_raw': text(c.get('strength')),
                           'basis_raw': text(c.get('basis')) or None})
    elif isinstance(raw, str) and raw.strip():
        try:
            names = split_components(text(raw))
            strengths = split_components(text(strength)) if text(strength) else []
        except ValueError as e:
            return [], [('COMPONENT_LAYOUT', 'ERROR', str(e))]
        # No positional guess if separators/counts disagree.
        aligned = len(names) == len(strengths)
        if not aligned:
            problems.append(('COMPONENT_STRENGTH_COUNT', 'WARNING', 'Ingredient/strength count mismatch'))
        result = []
        for i, name in enumerate(names):
            if ',' in name or '/' in name:
                problems.append(('AMBIGUOUS_INGREDIENT_SEPARATOR', 'WARNING', 'Review comma/slash ingredient text'))
            result.append({'name_raw': name, 'strength_raw': strengths[i] if aligned else '', 'basis_raw': None})
    else:
        return [], [('MISSING_INGREDIENTS', 'ERROR', 'No components')]
    for c in result:
        c['strength'] = parse_strength(c['strength_raw'])
        if c['strength']['status'] != 'PARSED':
            problems.append(('STRENGTH_UNRESOLVED', 'WARNING', 'Missing, unsupported, or basis-ambiguous strength'))
        if re.search(r'\d+\s*(mg|mcg|g|iu|ui)\b', c['name_raw'], re.I):
            problems.append(('INLINE_STRENGTH_IN_NAME', 'WARNING', 'Embedded strengths need explicit component association'))
    if len({key(c['name_raw']) for c in result}) != len(result):
        problems.append(('REPEATED_COMPONENT', 'WARNING', 'Repeated ingredient requires review; do not collapse'))
    return result, problems


def date_field(value, name, problems):
    raw = text(value)
    if not raw:
        return None
    for fmt in ('%Y-%m-%d', '%d/%m/%Y'):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            pass
    problems.append(('INVALID_DATE_' + name, 'WARNING', 'Expected ISO date or dd/MM/yyyy'))
    return None


def normalize(row, column_map, synthetic):
    n, problems = canonicalize(row, column_map)
    for field in ALIASES:
        if field != 'ingredients':
            if isinstance(n[field], (dict, list, bool)):
                problems.append(('INVALID_TYPE_' + field, 'ERROR', 'Expected scalar text'))
                n[field] = ''
            n[field] = text(n[field])
    for field in ('registration_number', 'brand_name', 'manufacturer', 'dosage_form'):
        if not n[field]:
            problems.append(('MISSING_' + field.upper(), 'ERROR', 'Required identity field absent'))
    n['registration_key'] = n['registration_number'].upper()
    n['components'], cp = components(n['ingredients'], n['strength'])
    problems.extend(cp)
    n.pop('ingredients')
    n['dosage_form_normalized'] = FORMS.get(key(n['dosage_form']))
    if not n['dosage_form_normalized']:
        problems.append(('UNKNOWN_DOSAGE_FORM', 'WARNING', 'Preserve full form/release wording for review'))
    n['effective_date_normalized'] = date_field(n['effective_date'], 'effective_date', problems)
    n['valid_until_normalized'] = date_field(n['valid_until'], 'valid_until', problems)
    if n['effective_date_normalized'] and n['valid_until_normalized'] and n['effective_date_normalized'] > n['valid_until_normalized']:
        problems.append(('DATE_ORDER', 'ERROR', 'Effective date is after validity end'))
    event = key(n['event_type'])
    n['event_type_normalized'] = event if event in {'original_grant', 'renewal', 'amendment', 'withdrawal', 'correction'} else 'unknown'
    if n['event_type_normalized'] == 'unknown':
        problems.append(('UNKNOWN_EVENT_TYPE', 'WARNING', 'Unknown source event; no status inference'))
    status = 'QUARANTINED' if any(p[1] == 'ERROR' for p in problems) else ('REVIEW_REQUIRED' if problems else 'VALID')
    # Product signatures are candidate equivalence only, not pharmaceutical adjudication.
    identity = {'synthetic': synthetic, 'brand': key(n['brand_name']), 'manufacturer': key(n['manufacturer']),
                'form': n['dosage_form_normalized'] or key(n['dosage_form']), 'route': key(n['route']),
                'components': sorted([{'name': key(c['name_raw']), 'basis': key(c['basis_raw']),
                    'strength': {k: v for k, v in c['strength'].items() if k != 'raw'}} for c in n['components']], key=digest)}
    # Incomplete/ambiguous identity is never merged across source rows.
    if problems:
        identity['unresolved_row_sha256'] = digest(row)
    return n, status, problems, digest(identity)
