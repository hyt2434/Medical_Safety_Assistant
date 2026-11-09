"""Literal fields for simple name/ingredient table labels, without lookup."""

import re

NUMBER = r'\d+(?:[.,]\d+)?'
STRENGTH = rf'{NUMBER}\s*(?:mcg|mg|g|%)(?:\s*/\s*(?:{NUMBER}\s*)?(?:ml|g))?'


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
    if not name or remainder.strip(' ,;'):
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
