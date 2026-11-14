"""Nạp Medication Dictionary từ các file CSV vào RAM.

Dùng 3 file (xem Data-Overview.md):
  - medications.csv            : id (PC_...), brand_name, dosage_form, level2_qualified
  - medication_ingredients.csv : medication_id, ordinal, original_name_candidate,
                                 ingredient_text_raw, accepted_ingredient_id
  - ingredients.csv (tùy chọn) : id (LI_...), accepted_normalized_name, source_name
"""
from __future__ import annotations

import csv
import logging
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))  # các cột JSON có thể rất dài

_MED_COLS = {"id", "brand_name", "dosage_form", "level2_qualified"}
_COMP_COLS = {
    "medication_id", "ordinal", "original_name_candidate",
    "ingredient_text_raw", "accepted_ingredient_id",
}
_ING_COLS = {"id", "accepted_normalized_name", "source_name"}


class DictionaryError(Exception):
    """Lỗi dữ liệu từ điển (thiếu file / thiếu cột)."""


@dataclass(frozen=True)
class MedicationEntry:
    medication_id: str
    brand_name: str
    dosage_form: str | None
    active_ingredients: tuple[str, ...]  # tên như in trên sản phẩm; rỗng nếu không rõ
    strength: str | None                 # chuỗi hiển thị, KHÔNG phải dữ liệu có cấu trúc
    level2_qualified: bool
    alt_names: tuple[str, ...] = ()      # tên hoạt chất chuẩn hóa, chỉ để tìm kiếm


def _read_rows(path: Path, required: set[str]):
    if not path.exists():
        raise DictionaryError(f"Không tìm thấy file: {path}")
    with path.open(newline="", encoding="utf-8-sig") as f:  # utf-8-sig: file xuất từ Excel có BOM
        reader = csv.DictReader(f)
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise DictionaryError(f"{path.name} thiếu cột: {sorted(missing)}")
        yield from reader


def _strength_part(name: str, text_raw: str) -> str | None:
    """Bỏ tên hoạt chất ở đầu ingredient_text_raw, phần còn lại là hàm lượng."""
    text = text_raw.strip()
    if not text:
        return None
    if name and text.lower().startswith(name.lower()):
        return text[len(name):].strip(" \t-:,;") or None
    return text


def _build_strength(comps: list[tuple[str, str]]) -> str | None:
    """comps: [(tên, ingredient_text_raw)] theo thứ tự ordinal."""
    parts = [(n, _strength_part(n, t)) for n, t in comps]
    if not any(s for _, s in parts):
        return None
    if len(comps) == 1:
        return parts[0][1]
    # nhiều hoạt chất: giữ cả tên để biết hàm lượng của hoạt chất nào
    return " + ".join((t.strip() or n) for n, t in comps)


def _ordinal(value: str) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 10**6


def load_dictionary(data_dir: str | Path) -> list[MedicationEntry]:
    data_dir = Path(data_dir)

    accepted_names: dict[str, str] = {}
    ing_path = data_dir / "ingredients.csv"
    if ing_path.exists():
        for r in _read_rows(ing_path, _ING_COLS):
            name = (r["accepted_normalized_name"] or r["source_name"] or "").strip()
            if name:
                accepted_names[r["id"].strip()] = name
    else:
        logger.warning("Không có ingredients.csv, chỉ dùng tên hoạt chất trong medication_ingredients.csv")

    comps: dict[str, list[tuple[int, str, str, str]]] = defaultdict(list)
    for r in _read_rows(data_dir / "medication_ingredients.csv", _COMP_COLS):
        comps[r["medication_id"].strip()].append((
            _ordinal(r["ordinal"]),
            (r["original_name_candidate"] or "").strip(),
            (r["ingredient_text_raw"] or "").strip(),
            (r["accepted_ingredient_id"] or "").strip(),
        ))

    entries: list[MedicationEntry] = []
    skipped = unresolved = 0
    for r in _read_rows(data_dir / "medications.csv", _MED_COLS):
        mid = r["id"].strip()
        brand = (r["brand_name"] or "").strip()
        if not mid or not brand:
            skipped += 1
            continue

        rows = sorted(comps.get(mid, []), key=lambda c: c[0])
        names: list[str] = []
        alts: list[str] = []
        pairs: list[tuple[str, str]] = []
        seen: set[str] = set()
        for _, orig, text_raw, acc_id in rows:
            acc = accepted_names.get(acc_id, "")
            if acc_id and not acc:
                unresolved += 1  # khóa nối không tìm thấy -> bỏ qua, không làm hỏng bản ghi
            shown = orig or acc
            if not shown:
                continue
            pairs.append((shown, text_raw))
            if shown.lower() not in seen:
                seen.add(shown.lower())
                names.append(shown)
            if acc and acc.lower() not in seen:
                seen.add(acc.lower())
                alts.append(acc)

        entries.append(MedicationEntry(
            medication_id=mid,
            brand_name=brand,
            dosage_form=(r["dosage_form"] or "").strip() or None,
            active_ingredients=tuple(names),
            strength=_build_strength(pairs),
            level2_qualified=(r["level2_qualified"] or "").strip().upper() == "TRUE",
            alt_names=tuple(alts),
        ))

    logger.info("Đã nạp %d sản phẩm (bỏ qua %d dòng thiếu id/brand, %d khóa hoạt chất không nối được)",
                len(entries), skipped, unresolved)
    return entries
