"""Formatting keys retain Vietnamese diacritics and all formulation numbers."""
import re
import unicodedata
from decimal import Decimal, localcontext
from fractions import Fraction
from .registration_parser import registration_cell
from shared.dav_import.normalize import parse_strength, FORMS


def clean(value):
    return ' '.join(unicodedata.normalize('NFKC', str(value or '')).split())


def key(value):
    return clean(value).casefold()


def brand_key(value):
    # Punctuation at token boundaries only. Never drop accents, numbers or join tokens.
    return key(re.sub(r'[-‐‑–—]', ' ', clean(value)))


def registration(value):
    parsed = registration_cell(clean(value))
    if parsed:
        return parsed['primary'].upper()
    # Literal formats present in the published Core catalog. This is a lookup
    # key, not evidence of regulatory validity/current authorization. Never fill
    # missing digits or accept trailing commentary as part of an identifier.
    retained = clean(value)
    if re.fullmatch(r'(?:(?:VD3|SP3|GC)-\d+-\d{2}|QLSP-[A-Z]\d{2}-\d+-\d{2})', retained, re.I):
        return retained.upper()
    return None


def strength_key(value):
    parsed = parse_strength(value)
    if parsed['status'] == 'PARSED':
        return tuple(parsed[f] for f in ('amount', 'unit', 'denominator_amount', 'denominator_unit'))
    return ('raw', key(value))


def form_key(value):
    return FORMS.get(key(value), key(value))


def normalized_form(value):
    """Reuse registry forms, retaining release and device distinctions."""
    aliases = {
        'tablet, film coated': 'film_coated_tablet', 'tablet, coated': 'coated_tablet',
        'tablet, extended release': 'extended_release_tablet',
        'tablet, delayed release': 'delayed_release_tablet',
        'capsule, delayed release': 'delayed_release_capsule',
        'capsule, extended release': 'extended_release_capsule',
        'injection, solution': 'injection_solution', 'solution for injection': 'injection_solution',
        'injection, suspension': 'injection_suspension',
        'solution for injection in pre-filled pen': 'injection_solution_in_pre_filled_pen',
    }
    return aliases.get(key(value), form_key(value))


def strength_signature(value):
    """Exact scalar/labelled dose signatures; unknown semantics remain raw.

    Labels, chemical forms, component association and percent basis are retained.
    A ratio uses exact rational arithmetic, never rounded clinical dose values.
    """
    from .ingredients import _split
    value = clean(value)
    if not value:
        return ('raw', '')
    if len(value) > 4096:
        return ('raw', key(value))
    try:
        parts = _split(value)
    except ValueError:
        return ('raw', key(value))
    doses = [_atomic_strength(p) for p in parts]
    if all(d is not None for d in doses):
        return tuple(doses)
    labelled = []
    for part in parts:
        item = None
        for match in re.finditer(r'(?<=\s)\d', part):
            label, dose = part[:match.start()].strip(), _atomic_strength(part[match.start():])
            if dose is not None and _ingredient_label(label):
                item = (key(label), dose)
                break
        if item is None:
            return ('raw', key(value))
        labelled.append(item)
    if len({label for label, dose in labelled}) != len(labelled):
        return ('raw', key(value))
    return ('named', tuple(sorted(labelled)))


def _ratio_string(value):
    """Return an exact decimal where finite, otherwise an exact rational key."""
    denominator = value.denominator
    twos = fives = 0
    while denominator % 2 == 0:
        twos += 1
        denominator //= 2
    while denominator % 5 == 0:
        fives += 1
        denominator //= 5
    if denominator != 1:
        return f'{value.numerator}/{value.denominator}'
    places = max(twos, fives)
    digits = str(value.numerator * (10 ** places // value.denominator))
    if not places:
        return digits
    digits = digits.zfill(places + 1)
    return (digits[:-places] + '.' + digits[-places:]).rstrip('0').rstrip('.')


def _scalar_key(parsed):
    amount = Fraction(Decimal(parsed['amount']))
    denominator = parsed['denominator_amount']
    if parsed['denominator_unit']:
        amount /= Fraction(Decimal(denominator))
        denominator = '1'
    return (_ratio_string(amount), parsed['unit'], denominator, parsed['denominator_unit'])


def _exact_parse(value):
    # The shared parser scales units with Decimal. Give it enough precision to
    # preserve every supplied digit rather than silently rounding long values.
    with localcontext() as context:
        context.prec = max(28, len(value) + 16)
        return parse_strength(value)


def _atomic_strength(value):
    value = clean(value)
    if value.count('(') > 16:
        return None
    # Multiple uniform thousands groups are explicit grouping. A single group
    # such as 100.000 IU or 1,578 g remains locale-ambiguous.
    value = re.sub(r'(?<![\w.,])\d{1,3}([.,])\d{3}(?:\1\d{3})+(?![\d.,])',
                   lambda m: m.group().replace(m[1], ''), value)
    value = re.sub(r'(?<=\d)\s*gam\b', ' g', value, flags=re.I)
    # Explicit mega-IU only. Lowercase mIU is not silently treated as mega-IU.
    mega = re.fullmatch(r'(\d+(?:[.,]\d+)?)\s*(?:MIU|(?i:triệu\s+(?:IU|UI)))', value)
    if mega:
        parsed = _exact_parse(mega[1] + ' IU')
        if parsed['status'] == 'PARSED':
            parsed['amount'] = _ratio_string(Fraction(Decimal(parsed['amount'])) * 1000000)
            return _scalar_key(parsed)
    percent = re.fullmatch(r'(\d+(?:[.,]\d+)?)\s*%\s*(?:\(\s*(w/v|w/w|v/v|kl/tt|kl/kl|tt/tt)\s*\)|(w/v|w/w|v/v|kl/tt|kl/kl|tt/tt))', value, re.I)
    if percent:
        basis = (percent[2] or percent[3]).casefold()
        numerator, denominator = ('mL', 'mL') if basis in {'v/v', 'tt/tt'} else (
            ('g', 'g') if basis in {'w/w', 'kl/kl'} else ('g', 'mL'))
        parsed = _exact_parse(f'{percent[1]} {numerator}/100 {denominator}')
        return _scalar_key(parsed) if parsed['status'] == 'PARSED' else None
    # mIU/MIU are case-sensitive SI prefixes; the existing grammar otherwise
    # treats IU/UI as equivalent unit spellings.
    if re.search(r'\bmIU\b', value):
        return None
    parsed = _exact_parse(value)
    if parsed['status'] == 'PARSED':
        return _scalar_key(parsed)
    # A repeated explicit assertion is accepted only when both sides agree,
    # e.g. 20 mg/mL (2% w/v). Never choose between contradictory assertions.
    depth = 0
    for i in range(len(value) - 1, -1, -1):
        if value[i] == ')': depth += 1
        elif value[i] == '(':
            depth -= 1
            if depth == 0 and value.endswith(')') and i > 0:
                left, right = _atomic_strength(value[:i]), _atomic_strength(value[i + 1:-1])
                return left if left is not None and left == right else None
    return None


def _ingredient_label(value):
    """Opaque literal ingredient/form label, never a salt/base equivalence."""
    if not any(c.isalpha() for c in value) or re.search(r'[:;/+%=~]|\b\d|\b(?:mỗi|chứa|trong|tương đương|liều|sau khi|kháng nguyên|chuẩn hóa)\b', key(value)):
        return False
    depth = 0
    for c in value:
        depth += (c == '(') - (c == ')')
        if depth < 0: return False
    return depth == 0


def comparable_strength(signature, ingredient, component_count):
    """Unwrap one explicit label only when the approved single component agrees."""
    if signature[0] == 'named' and component_count == 1 and len(signature[1]) == 1:
        label, dose = signature[1][0]
        if label == key(ingredient):
            return (dose,)
    return signature


def complete_strength_signature(signature, component_count):
    if signature[0] == 'raw':
        return False
    # New labelled profiles cannot conceal an unquantified component.
    return signature[0] != 'named' or len(signature[1]) == component_count


def ocr_name_key(value):
    """Candidate-retrieval key only; never an exact identity or ingredient key."""
    return value.translate(str.maketrans('015', 'ols')).replace('rn', 'm').replace('vv', 'w')


def review_name_compatible(query, target):
    """One edit/transposition for review only; preserve numbers and release labels."""
    if min(len(query), len(target)) < 4 or max(len(query), len(target)) > 120:
        return False
    release = r'\b(?:xr|sr|cr|mr|er|xl|retard|forte|plus|junior)\b'
    if re.findall(release, query) != re.findall(release, target):
        return False
    if re.findall(r'\d+(?:[.,]\d+)?', query) != re.findall(r'\d+(?:[.,]\d+)?', target):
        # A digit substituted inside an alphabetic name may be OCR damage.
        # Numeric product variants themselves are never corrected or completed.
        if re.search(r'\d', target) or ocr_name_key(query) != ocr_name_key(target):
            return False
    if query != target and ocr_name_key(query) == ocr_name_key(target):
        return True
    if len(query) == len(target):
        differences = [i for i, (a, b) in enumerate(zip(query, target)) if a != b]
        return len(differences) == 1 or (len(differences) == 2 and differences[1] == differences[0] + 1
            and query[differences[0]] == target[differences[1]] and query[differences[1]] == target[differences[0]])
    if abs(len(query) - len(target)) != 1:
        return False
    longer, shorter = (query, target) if len(query) > len(target) else (target, query)
    first = next((i for i, (a, b) in enumerate(zip(longer, shorter)) if a != b), len(shorter))
    return longer[first + 1:] == shorter[first:]

