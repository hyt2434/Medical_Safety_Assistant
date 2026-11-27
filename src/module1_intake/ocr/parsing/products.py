"""Literal fields for simple name/ingredient table labels, without lookup."""

import re

NUMBER = r'\d+(?:[.,]\d+)?'
STRENGTH = rf'{NUMBER}\s*(?:mcg|mg|g|%)(?:\s*/\s*(?:{NUMBER}\s*)?(?:ml|g))?'


def parse_quantity_product(raw):
    """Parse literal product prefix; parentheses have no assumed medical role."""
    result = {'name_raw': None, 'strength_raw': None, 'package_size_raw': None,
              'ingredient_raw': None, 'parenthetical_raw': None}
    text = re.sub(r'\s+', ' ', raw).strip()
    opening = text.find('(')
    body = text if opening < 0 else text[:opening].strip()
    if opening >= 0:
        depth = 0
        for index in range(opening, len(text)):
            depth += (text[index] == '(') - (text[index] == ')')
            if depth < 0 or (depth == 0 and index != len(text)-1):
                return result, ['product_structure']
        if depth:
            return result, ['product_structure']
        result['parenthetical_raw'] = text[opening+1:-1]
    elif ')' in text:
        return result, ['product_structure']
    combined = rf'{STRENGTH}(?:\s*\+\s*{STRENGTH})*'
    match = re.fullmatch(rf'(.+?)\s*({combined})(?:\s*[,;]\s*({NUMBER}\s*ml))?', body, re.I)
    if not match or not any(c.isalpha() for c in match[1]) or re.search(r'\d|[()]', match[1]):
        return result, ['product_structure']
    result.update(name_raw=match[1].strip(), strength_raw=match[2], package_size_raw=match[3])
    return result, ['parenthetical_raw'] if result['parenthetical_raw'] else []


def parse_table_product(raw):
    result = {'name_raw': raw, 'strength_raw': None,
              'package_size_raw': None, 'ingredient_raw': None}
    text = re.sub(r'\s+', ' ', raw).strip()
    # Nested/unbalanced parentheses cannot be safely classified by these rules.
    if text.count('(') != text.count(')') or text.count('(') > 1:
        return result, ['product_structure', 'strength_raw']
    parenthetical = re.search(r'\(([^()]*)\)\s*$', text)
    body = text[:parenthetical.start()].strip() if parenthetical else text
    if '(' in body or ')' in body:
        return result, ['product_structure', 'strength_raw']
    strength = re.search(STRENGTH + r'(?![\w/])', body, re.I)
    package = re.search(rf'{NUMBER}\s*ml\s*$', body, re.I)
    if not strength and not package and re.search(r'\d', body):
        return result, ['product_structure', 'strength_raw']
    if strength and package and package.start() < strength.end():
        package = None
    start = min([m.start() for m in (strength, package) if m] or [len(body)])
    name = body[:start].strip(' ,')
    remainder = body[start:]
    # Every suffix character must be explained, rather than dropping unknown text.
    for match in sorted([m for m in (strength, package) if m], key=lambda m: m.start(), reverse=True):
        begin, end = match.start() - start, match.end() - start
        remainder = remainder[:begin] + remainder[end:]
    if not name or not any(c.isalpha() for c in name) or remainder.strip(' ,;'):
        if not any(c.isalpha() for c in name):
            result['name_raw'] = None
        return result, ['product_structure', 'strength_raw']
    result['name_raw'] = name
    result['strength_raw'] = strength.group(0) if strength else None
    result['package_size_raw'] = package.group(0) if package else None
    uncertain = [] if strength else ['strength_raw']
    if parenthetical:
        ingredient = parenthetical.group(1).strip()
        repeated = re.search(r'\s*(' + STRENGTH + r')\s*$', ingredient, re.I)
        if repeated:
            normalize = lambda value: re.sub(r'\s+', '', value).lower().replace(',', '.')
            if strength and normalize(repeated.group(1)) == normalize(strength.group(0)):
                ingredient = ingredient[:repeated.start()].strip()
            else:
                uncertain.append('ingredient_raw')
        result['ingredient_raw'] = ingredient or None
        # Table parentheses are a candidate ingredient span, not verified identity.
        if 'ingredient_raw' not in uncertain:
            uncertain.append('ingredient_raw')
    return result, uncertain


def parse_numbered_product(text):
    """Recognize complete strength expressions, leaving unsupported suffixes raw."""
    result = {'name_raw': None, 'strength_raw': None,
              'ingredient_raw': None, 'package_size_raw': None}
    flat = re.sub(r'\s+', ' ', text).strip()
    ingredient = re.search(r'\(([^()]*)\)\s*$', flat)
    if ingredient and not re.match(r'^\s*\d+(?:[.,]\d+)?\s*(?:mcg|mg|g|%)', ingredient[1], re.I):
        result['ingredient_raw'] = ingredient[1]
        flat = flat[:ingredient.start()].strip()
    number = r'\d+(?:[.,]\d+)?'
    component = rf'{number}\s*(?:mcg|mg|g|%)'
    expression = rf'(?:\({component}(?:\s*\+\s*{component})*\)|{component}(?:\s*\+\s*{component})*)(?:\s*/\s*(?:{number}\s*)?(?:ml|g))?'
    def incomplete_strength():
        # Preserve only an independently delimited name, never repair ar/ap to +.
        prefix = re.match(rf'^(?P<name>.+?\[[^\]]+\])\s+(?={component})', flat, re.I)
        if prefix:
            result['name_raw'] = prefix['name']
            return result, ['strength_structure', 'strength_raw', 'ingredient_raw']
        return result, ['product_structure', 'strength_raw']
    match = re.fullmatch(rf'(?P<name>.+?)\s+(?P<strength>{expression})(?:\s*-\s*(?P<package>{number}\s*ml))?', flat, re.I)
    if match:
        if re.search(component, match['name'], re.I) and not re.search(r'\[.*?\]\s*$', match['name']):
            return incomplete_strength()
        result.update(name_raw=match['name'], strength_raw=match['strength'], package_size_raw=match['package'])
        return result, (['ingredient_raw'] if ingredient else [])
    return incomplete_strength()



def parse_strength_product(raw):
    # Remove only isolated trailing punctuation, keeping the full original evidence.
    cleaned = re.sub(r'(?:\s+[-=|<>])+\s*$', '', raw).strip()
    # Only pair explicit name-strength spans; never infer missing components.
    body = re.sub(r'\s*\([^()]*\)\s*$', '', cleaned).rstrip(' .')
    parts = re.split(r'\s*[,;+]\s*(?=[A-Za-zÀ-ỹ])', body)
    pairs = [re.fullmatch(rf'([^\d()]+?)\s*({STRENGTH})', part, re.I) for part in parts]
    if len(parts) > 1 and all(pairs):
        components = [{'name_raw': p[1].strip(), 'strength_raw': p[2],
                       'source_text': part} for p, part in zip(pairs, parts)]
        return {'name_raw': None, 'strength_raw': None, 'ingredient_raw': None,
                'package_size_raw': None, 'components_raw': components}, ['product_structure', 'components_raw']
    match = re.fullmatch(rf'(.+?)\s*-\s*({STRENGTH})', cleaned, re.I)
    if (match and any(c.isalpha() for c in match[1])
            and match[1].count('(') == match[1].count(')')
            and match[1].count('(') <= 1
            and not re.search(r'\)[^(]*\(', match[1])):
        return {'name_raw': match[1].strip(), 'strength_raw': match[2],
                'ingredient_raw': None, 'package_size_raw': None}, ['name_raw']
    return parse_table_product(cleaned)



def split_product(text: str) -> tuple[str, str | None, bool]:
    """Split only an unambiguous trailing strength; preserve complex labels."""
    number = r"\d+(?:[.,]\d+)?"
    unit = r"(?:mcg|mg|g|ml|%)"
    component = rf"{number}\s*{unit}"
    strength = rf"(?:\({component}(?:\s*\+\s*{component})*\)|{component})(?:\s*/\s*(?:g|ml))?"
    match = re.fullmatch(rf"(?P<name>.+?)\s+(?P<strength>{strength})", text, re.I)
    if match:
        name = match.group('name')
        # Nested strength/form/package descriptions are not safely separable.
        if name.count('(') == name.count(')') and not re.search(component, name, re.I):
            return name, match.group('strength'), False
    return text, None, True

