"""Conservative spelling candidates from the project's source-qualified snapshot.

Names are suggestions, never product identification or clinical validation.
"""
import csv
import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

CATALOG = Path(__file__).resolve().parents[3] / "data/datasets/medications.csv"


def normalize(value):
    folded = unicodedata.normalize("NFKD", value).casefold().replace("đ", "d")
    return " ".join(''.join(c for c in folded if not unicodedata.combining(c)).split())


def strength_key(value):
    return re.sub(r"\s+", "", normalize(value)).replace(",", ".")


def distance(a, b):
    previous = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        current = [i]
        for j, y in enumerate(b, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (x != y)))
        previous = current
    return previous[-1]


@lru_cache(maxsize=1)
def catalog_rows():
    with CATALOG.open(encoding="utf-8-sig", newline="") as source:
        return tuple(
            {"id": r["id"], "name": r["brand_name"],
             "strength": json.loads(r["identity_definition"]).get("strength", ""),
             "ingredient": json.loads(r["identity_definition"]).get("ingredients", ""),
             "form": r["dosage_form"], "source_record_id": r["source_record_id"]}
            for r in csv.DictReader(source)
            if r["identity_state"] == "SOURCE_REGISTERED_PRODUCT_ESTABLISHED"
            and r["level2_qualified"] == "true"
        )


def suggestions(name, strength, rows):
    query = normalize(name)
    if len(query) < 5 or len(query) > 120:
        return []
    # Exact names are not spelling errors, even when the strength differs.
    if any(normalize(row["name"]) == query for row in rows):
        return []
    limit = 1 if len(query) < 8 else 2
    candidates = []
    for row in rows:
        candidate = normalize(row["name"])
        if abs(len(candidate) - len(query)) > limit:
            continue
        if strength and strength_key(strength) != strength_key(row["strength"]):
            continue
        # Never correct numeric suffixes that may encode a different product.
        if re.findall(r"\b\d+(?:[.,]\d+)?\b", query) != re.findall(r"\b\d+(?:[.,]\d+)?\b", candidate):
            continue
        edits = distance(query, candidate)
        if edits <= limit:
            candidates.append((edits, row))
    seen, result = set(), []
    for _, row in sorted(candidates, key=lambda item: (item[0], item[1]["name"], item[1]["id"])):
        key = (normalize(row["name"]), strength_key(row["strength"]), row["form"])
        if key not in seen:
            seen.add(key)
            result.append(row)
    return result[:3]
