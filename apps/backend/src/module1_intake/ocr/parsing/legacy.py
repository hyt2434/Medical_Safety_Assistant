"""Geometry-based parser for numbered, printed prescriptions.

The parser deliberately uses only OCR text and coordinates. It does not guess
drug names from a catalogue and does not infer missing medical instructions.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

Word = dict[str, Any]


from module1_intake.ocr.parsing.products import split_product


def _plain(text: str) -> str:
    value = "".join(
        char
        for char in unicodedata.normalize("NFD", text.casefold())
        if unicodedata.category(char) != "Mn"
    )
    return value.replace("đ", "d")


def find_numbered_row_starters(words: list[Word]) -> list[Word]:
    """Find a consecutive row-number sequence, including bare ``1 2 3``.

    Bare numbers are accepted only if they begin at 1, are vertically ordered,
    and occupy approximately the same x column. This avoids treating a dose
    such as ``01 viên`` as a medication row.
    """
    punctuated = [word for word in words if re.fullmatch(r"\d+[.)]", word["text"].strip())]
    if punctuated:
        return sorted(punctuated, key=lambda word: word["bbox"]["y0"])

    candidates: list[tuple[int, Word]] = []
    for word in words:
        match = re.fullmatch(r"(\d+)", word["text"].strip())
        if match and 1 <= int(match.group(1)) <= 50:
            candidates.append((int(match.group(1)), word))
    if not candidates:
        return []

    heights = sorted(max(1, word["bbox"]["y1"] - word["bbox"]["y0"]) for _, word in candidates)
    median_height = heights[len(heights) // 2]
    x_tolerance = max(12, median_height * 2)
    max_y_gap = max(90, median_height * 9)
    runs: list[list[Word]] = []
    for number, first in candidates:
        if number != 1:
            continue
        run = [first]
        expected = 2
        previous = first
        while True:
            matches = [
                word
                for value, word in candidates
                if value == expected
                and 0 < word["bbox"]["y0"] - previous["bbox"]["y0"] <= max_y_gap
                and abs(word["bbox"]["x0"] - first["bbox"]["x0"]) <= x_tolerance
            ]
            if not matches:
                break
            previous = min(matches, key=lambda word: word["bbox"]["y0"])
            run.append(previous)
            expected += 1
        if len(run) >= 2:
            runs.append(run)
    return max(runs, key=lambda run: (len(run), -run[0]["bbox"]["y0"]), default=[])


def _join_lines(words: list[Word], tolerance: float) -> list[str]:
    lines: list[list[Any]] = []
    for word in sorted(words, key=lambda item: (item["bbox"]["y0"], item["bbox"]["x0"])):
        center = (word["bbox"]["y0"] + word["bbox"]["y1"]) / 2
        if not lines or abs(center - lines[-1][0]) > tolerance:
            lines.append([center, [word]])
        else:
            lines[-1][1].append(word)
            lines[-1][0] = sum(
                (item["bbox"]["y0"] + item["bbox"]["y1"]) / 2 for item in lines[-1][1]
            ) / len(lines[-1][1])
    return [
        " ".join(item["text"] for item in sorted(line, key=lambda item: item["bbox"]["x0"]))
        for _, line in lines
    ]


def _has_hospital_header(words: list[Word], first: Word) -> bool:
    for word in words:
        if (
            _plain(word["text"]).strip(":") == "thuoc"
            and word["bbox"]["y0"] < first["bbox"]["y0"]
            and abs(word["bbox"]["x0"] - first["bbox"]["x0"]) <= 120
        ):
            same_line = {
                _plain(item["text"]).strip(":,.")
                for item in words
                if abs(item["bbox"]["y0"] - word["bbox"]["y0"]) <= 16
            }
            if {"dieu", "tri"} <= same_line:
                return True
    return False


def extract_legacy_prescription(words):
    starters = find_numbered_row_starters(words)
    if not starters:
        raise ValueError("Không tìm thấy dãy số thứ tự thuốc liên tiếp")
    if not _has_hospital_header(words, starters[0]):
        raise ValueError("Chưa nhận diện được tiêu đề danh sách thuốc in")

    heights = sorted(max(1, word["bbox"]["y1"] - word["bbox"]["y0"]) for word in words)
    median_height = heights[len(heights) // 2]
    left_edge = min(word["bbox"]["x0"] for word in starters) - median_height
    advice_y = min(
        (
            word["bbox"]["y0"]
            for word in words
            if word["bbox"]["y0"] > starters[-1]["bbox"]["y0"]
            and word["bbox"]["x0"] >= left_edge
            and _plain(word["text"]).strip(":") == "loi"
        ),
        default=None,
    )
    # Include ascenders/diacritics that start above the heading's own y0.
    advice_cutoff = (advice_y - median_height * .6 if advice_y is not None
                     else starters[-1]['bbox']['y0'] + median_height * 10)
    schedule_pattern = re.compile(
        r"(?P<timing>Sáng|Trưa|Chiều|Tối)\s*:?\s*(?P<dose>\d+(?:[.,]\d+)?)\s*"
        r"(?P<unit>viên|ống|gói|muỗng|ml)",
        re.I,
    )
    topical_pattern = re.compile(
        r"buổi\s+(?P<timing>sáng|trưa|chiều|tối)\s+(?P<dose>\d+(?:[.,]\d+)?)\s+lần",
        re.I,
    )
    medications = []
    for index, starter in enumerate(starters):
        y = starter["bbox"]["y0"]
        row_end = starters[index + 1]["bbox"]["y0"] if index + 1 < len(starters) else advice_cutoff
        title_words = sorted(
            [
                word
                for word in words
                if word["bbox"]["x0"] > starter["bbox"]["x1"]
                and abs(word["bbox"]["y0"] - y) <= median_height
            ],
            key=lambda item: item["bbox"]["x0"],
        )
        gaps = [
            (title_words[pos + 1]["bbox"]["x0"] - title_words[pos]["bbox"]["x1"], pos)
            for pos in range(len(title_words) - 1)
        ]
        large_gaps = [gap for gap in gaps if gap[0] >= max(60, median_height * 3)]
        split_at = max(large_gaps)[1] + 1 if large_gaps else len(title_words)
        product_words, quantity_words = title_words[:split_at], title_words[split_at:]
        quantity_x = quantity_words[0]["bbox"]["x0"] if quantity_words else float("inf")

        product = ' '.join(word['text'] for word in product_words)
        name, strength, ambiguous_product = split_product(product)
        body_words = [
            word
            for word in words
            if y + median_height < word["bbox"]["y0"] < row_end - 2
            and left_edge <= word["bbox"]["x0"] < quantity_x - median_height
        ]
        duration_words = [
            word
            for word in words
            if y + median_height < word["bbox"]["y0"] < row_end - 2
            and word["bbox"]["x0"] >= quantity_x - median_height
        ]
        instructions = "\n".join(_join_lines(body_words, max(8, median_height * 0.75))) or None
        administrations = []
        if instructions:
            matches = list(schedule_pattern.finditer(instructions))
            for position, match in enumerate(matches):
                end = matches[position + 1].start() if position + 1 < len(matches) else len(instructions)
                tail = instructions[match.end():end]
                phase = re.search(r'trong\s+\d+\s+(?:ngày\s+)?(?:đầu|tiếp\s+theo)', tail, re.I)
                administrations.append({
                    'timing_raw': match.group('timing'),
                    'dose_raw': f"{match.group('dose')} {match.group('unit')}",
                    'phase_raw': phase.group(0) if phase else None,
                })
            administrations.extend(
                {"timing_raw": match.group("timing"), "dose_raw": f'{match.group("dose")} lần'}
                for match in topical_pattern.finditer(instructions)
            )
        uncertain = []
        for field, field_words in (
            ("name_raw", name),
            ("strength_raw", strength),
            ("quantity_raw", quantity_words),
        ):
            if not field_words:
                uncertain.append(field)
        if ambiguous_product:
            uncertain.append('product_structure')
        phased = bool(instructions and re.search(r'\b(đầu|tiếp\s+theo|sau\s+đó|giảm)\b', instructions, re.I))
        if phased:
            uncertain.append('schedule_phases')
        evidence_words = product_words + quantity_words + body_words + duration_words
        if any(float(word.get("confidence", 0)) < 85 for word in evidence_words):
            uncertain.append("ocr_low_confidence")
        route = None
        if instructions:
            first_word = instructions.split()[0].strip(" ,.;:")
            if _plain(first_word).startswith(("uong", "dungngoai")):
                route = first_word
        medications.append(
            {
                "product_raw": product or None,
                "name_raw": name or None,
                "strength_raw": strength,
                "dose_raw": None if phased else "\n".join(item["dose_raw"] for item in administrations) or None,
                "route_raw": route,
                "frequency_raw": None if phased else "\n".join(item["timing_raw"] for item in administrations) or None,
                "duration_raw": " ".join(_join_lines(duration_words, max(8, median_height * 0.75))) or None,
                "quantity_raw": " ".join(word["text"] for word in quantity_words) or None,
                "instructions_raw": instructions,
                "administrations": administrations,
                "schedule_requires_review": True,
                "evidence_text": "\n".join(_join_lines(evidence_words, max(8, median_height * 0.75))),
                "uncertain_fields": uncertain,
            }
        )
    document_lines = []
    if advice_y is not None:
        advice_words = [w for w in words if w['bbox']['x0'] >= left_edge
                        and w['bbox']['y0'] >= advice_cutoff]
        for line in _join_lines(advice_words, max(8, median_height * .75)):
            plain = _plain(line).strip().lstrip('-> .')
            if re.match(r'(?:quy khach|phieu chi dinh|https|tai kham|ngay\s+\d|bac si)', plain):
                break
            if any(char.isalnum() for char in line):
                document_lines.append(line)
    return {
        "medications": medications,
        "document_instructions_raw": document_lines,
        "warnings": ["Kết quả OCR phải được người dùng đối chiếu với đơn thuốc gốc"],
        "requires_user_review": True,
    }
