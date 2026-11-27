"""Conservative component grammar. Salt forms are never silently converted to bases."""
import re
from shared.dav_import.normalize import parse_strength, split_components
from .text import clean, key, strength_key

DOSE = r'\d+(?:[.,]\d+)?\s*(?:mcg|µg|μg|ug|mg|g|IU|UI|%)(?:\s*/\s*(?:\d+(?:[.,]\d+)?)?\s*(?:ml|mL|l|g|mg|viên|dose))?'
INLINE = re.compile(rf'^(.*?)\s*({DOSE})\s*$', re.I)
BASE_DECLARATION = re.compile(r'^(.*?)\s*\((dưới dạng\s+.+|as\s+.+|tương đương (?:với\s+)?[^()]+)\)\s*$', re.I)


def _split(raw):
    """Comma is a separator only outside parentheses and decimal numbers."""
    depth = start = 0
    result = []
    for i, char in enumerate(raw):
        if char == '(':
            depth += 1
        elif char == ')':
            depth -= 1
        elif depth == 0 and (char in ';+' or (char == ',' and not
                (i > 0 and i + 1 < len(raw) and raw[i-1].isdigit() and raw[i+1].isdigit()))):
            result.append(raw[start:i].strip())
            start = i + 1
        if depth < 0:
            raise ValueError('UNBALANCED_PARENTHESES')
    if depth:
        raise ValueError('UNBALANCED_PARENTHESES')
    result.append(raw[start:].strip())
    if any(not x for x in result):
        raise ValueError('EMPTY_COMPONENT')
    return result


def parse_ingredients(original, strength=''):
    result = {'original_text': original, 'original_strength': strength,
              'status': 'PARSED', 'ingredients': [], 'issues': []}
    structured = isinstance(original, list)
    if structured:
        if not original or any(not isinstance(x, dict) or not isinstance(x.get('name'), str)
                               or not x['name'].strip() for x in original):
            result.update(status='UNRESOLVED', issues=['INVALID_COMPONENT_ARRAY'])
            return result
        parts = [x['name'] for x in original]
        doses = [x.get('strength') or '' for x in original]
    elif isinstance(original, str) and clean(original):
        try:
            parts = _split(clean(original))
            # Reuse the ingestion grammar for explicit semicolon/plus dose lists.
            doses = split_components(clean(strength)) if clean(strength) else []
            if len(doses) != len(parts):
                doses = [''] * len(parts)
                if clean(strength):
                    result['issues'].append('STRENGTH_COMPONENT_ASSOCIATION_REVIEW')
        except ValueError as e:
            result.update(status='REVIEW_REQUIRED', issues=[str(e)])
            return result
    else:
        result.update(status='UNRESOLVED', issues=['MISSING_INGREDIENTS'])
        return result
    seen = set()
    for index, part in enumerate(parts):
        name, dose = clean(part), clean(doses[index])
        item_issues = []
        inline = INLINE.fullmatch(name)
        if inline:
            name, inline_dose = inline.groups()
            if dose and strength_key(dose) != strength_key(inline_dose):
                item_issues.append('INLINE_SEPARATE_STRENGTH_CONFLICT')
            else:
                dose = inline_dose
        declaration = BASE_DECLARATION.fullmatch(name)
        basis = None
        if declaration:
            # The source explicitly names the active ingredient outside parentheses.
            # The supplied form is retained as evidence, not asserted chemically equivalent.
            name, basis = declaration.groups()
        name = clean(name)
        if not name or re.search(r'[();+:]|\b(?:chứa|mỗi|tương đương|micronized)\b', name, re.I):
            item_issues.append('UNSUPPORTED_INGREDIENT_DESCRIPTION')
        if '/' in name or ',' in name or re.search(r'\d+\s*(?:mg|g|iu|ui|%)\b', name, re.I):
            item_issues.append('AMBIGUOUS_INGREDIENT_BOUNDARY')
        if key(name) in seen:
            item_issues.append('DUPLICATE_COMPONENT_REVIEW')
        seen.add(key(name))
        parsed = parse_strength(dose)
        if parsed['status'] != 'PARSED':
            result['issues'].append('STRENGTH_MISSING_OR_UNRESOLVED')
        result['ingredients'].append({'ordinal': index + 1, 'original_ingredient': part,
            'normalized_ingredient': name, 'source_form_declaration': basis,
            'strength_raw': dose, 'strength': parsed,
            'extraction_status': 'REVIEW_REQUIRED' if item_issues else 'PARSED', 'issues': item_issues})
    if any(x['issues'] for x in result['ingredients']):
        result['status'] = 'REVIEW_REQUIRED'
    result['issues'] = sorted(set(result['issues']))
    return result
