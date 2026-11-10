"""Formatting keys retain Vietnamese diacritics and all formulation numbers."""
import re
import unicodedata
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
    return parsed['primary'].upper() if parsed else None


def strength_key(value):
    parsed = parse_strength(value)
    if parsed['status'] == 'PARSED':
        return tuple(parsed[f] for f in ('amount', 'unit', 'denominator_amount', 'denominator_unit'))
    return ('raw', key(value))


def form_key(value):
    return FORMS.get(key(value), key(value))

