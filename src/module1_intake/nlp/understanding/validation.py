"""Source grounding and conservative slot-role checks, independent of inference."""
import re
import unicodedata

from ..models import Intent, Medication, Understanding


def fold(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text.casefold().replace("đ", "d"))
                   if unicodedata.category(c) != "Mn")


STRENGTH = re.compile(r"\d+(?:[.,]\d+)?\s*(?:mcg|µg|μg|mg|g|iu|ui|%)(?![a-z])", re.I)
DOSE = re.compile(r"(?:\d+(?:[.,/]\d+)?|mot|hai|nua)\s*(?:vien|ml|giot|nhat|ong|goi)\b")
QUANTITY = re.compile(r"(?:\d+|mot|hai)\s*(?:hop|vi|chai|lo|goi|ong|vien|tui)\b")
NEGATION = re.compile(r"\b(?:khong (?:con )?(?:uong|dung)|chua (?:uong|dung)|da ngung|ngung uong)\b")
UNCERTAINTY = re.compile(r"\b(?:co le|hinh nhu|khong chac|khong nho|khong ro)\b")
FREQUENCY = re.compile(r"\b(?:moi|hang|ngay|tuan|lan|cach)\b")
TIMING = re.compile(r"\b(?:sang|trua|chieu|toi|dem|an|ngu|luc|gio)\b|\d{1,2}:\d{2}")
RECORD_REQUEST = re.compile(
    r"^(?:(?:vui long|hay|giup toi|toi muon|toi can)\s+)?"
    r"(?:luu(?: lai)?|them thuoc|them vao (?:danh sach|ho so)|ghi nhan|ghi thuoc|nhap thuoc)\b")
DAYPART = re.compile(r"\b(?:sang|trua|chieu|toi|dem)\b")
CONJOINED_DAYPARTS = re.compile(r"(?:sang|trua|chieu|toi|dem)(?:\s+va\s+(?:sang|trua|chieu|toi|dem))+")
GROUPED_DAYPARTS = re.compile(
    r"\b(?:sang|trua|chieu|toi|dem)\s+(?:va|hoac|den)\s+(?:sang|trua|chieu|toi|dem)\b")


class EvidenceError(ValueError):
    pass


def _present(value: str | None, evidence: str, key: str) -> None:
    if value is not None and (not value.strip() or value not in evidence):
        raise EvidenceError(f"Unsupported source span: {key}")


def _dose_role(value: str, evidence: str) -> bool:
    normalized = fold(value)
    if re.search(r"\b(?:hop|vi|chai|lo|tui)\b", normalized):
        return False
    if STRENGTH.search(normalized):
        prefix = fold(evidence[:evidence.find(value)])[-35:]
        return re.search(r"\b(?:moi lan|lieu(?: dung)?)\s*[:=]?\s*$", prefix) is not None or re.search(r"\b(?:moi lan|lieu)\b", normalized) is not None
    return DOSE.search(normalized) is not None


def raw_marker(text: str, pattern: re.Pattern) -> str | None:
    """Return original Unicode bytes' text, including decomposed Vietnamese accents."""
    match = pattern.search(fold(text))
    if not match:
        return None
    offsets = [len(fold(text[:i])) for i in range(len(text) + 1)]
    start = offsets.index(match.start())
    end = max(i for i, size in enumerate(offsets) if size == match.end())
    return text[start:end]


def record_request_marker(source: str) -> str | None:
    """Conservative affirmative request prefix; reports/questions/negation do not match."""
    return raw_marker(source.lstrip(), RECORD_REQUEST)


def timing_slots(timing_raw: str | None) -> list[str]:
    """Split only an explicit conjunction of bare dayparts, never alternatives/ranges.

    Keep the parent phrase and dose intact. This is a source-span projection,
    not a daily-dose calculation or an interpretation of complex instructions.
    """
    if timing_raw is None:
        return []
    normalized = fold(timing_raw)
    if CONJOINED_DAYPARTS.fullmatch(normalized):
        names = [match.group() for match in DAYPART.finditer(normalized)]
        if len(set(names)) == len(names):
            return [raw_marker(timing_raw, re.compile(r"\b" + name + r"\b")) for name in names]
    return [timing_raw]


def validate_medication(med: Medication, source: str) -> Medication:
    _present(med.evidence_text, source, "evidence_text")
    start = source.find(med.evidence_text)
    preceding = re.split(r"[;\n]", source[:start])[-1]
    if (NEGATION.search(fold(preceding)) or UNCERTAINTY.search(fold(preceding))):
        raise EvidenceError("Evidence omitted preceding negation/uncertainty; include the full clause")
    for key, value in med.model_dump().items():
        if key.endswith("_raw"):
            _present(value, med.evidence_text, key)
    for admin in med.administrations:
        _present(admin.timing_raw, med.evidence_text, "timing_raw")
        _present(admin.dose_raw, med.evidence_text, "administration.dose_raw")
        if admin.timing_raw and not TIMING.search(fold(admin.timing_raw)):
            raise EvidenceError("Invalid timing role")
        if admin.timing_raw and DAYPART.fullmatch(fold(admin.timing_raw)):
            if any(re.search(r"\b" + re.escape(fold(admin.timing_raw)) + r"\b", group.group())
                   for group in GROUPED_DAYPARTS.finditer(fold(med.evidence_text))):
                raise EvidenceError("Grouped timing evidence must be retained")
        if admin.dose_raw and not _dose_role(admin.dose_raw, med.evidence_text):
            raise EvidenceError("Invalid administration dose role")
        expected_slots = timing_slots(admin.timing_raw)
        for slot in admin.timing_slots_raw:
            _present(slot, admin.timing_raw or "", "timing_slots_raw")
        if admin.timing_slots_raw and admin.timing_slots_raw != expected_slots:
            raise EvidenceError("Unsupported administration timing slots")
    for key, pattern in (("strength_raw", STRENGTH),
                         ("quantity_raw", QUANTITY), ("frequency_raw", FREQUENCY)):
        value = getattr(med, key)
        if value and not pattern.search(fold(value)):
            raise EvidenceError(f"Invalid slot role: {key}")
    for key in ("dose_raw", "quantity_raw"):
        value = getattr(med, key)
        if value:
            prefix = fold(med.evidence_text[:med.evidence_text.find(value)])[-35:]
            if key == "dose_raw" and re.search(r"(?:so luong|sl|cap|tong)\s*[:=]?\s*$", prefix):
                raise EvidenceError("Dispensed quantity mislabeled as dose")
            if key == "quantity_raw" and re.search(r"(?:moi lan|lieu|uong)\s*[:=]?\s*$", prefix):
                raise EvidenceError("Dose mislabeled as dispensed quantity")
    if med.dose_raw and not _dose_role(med.dose_raw, med.evidence_text):
        raise EvidenceError("Strength/package quantity cannot be a dose")
    if med.strength_raw:
        prefix = fold(med.evidence_text[:med.evidence_text.find(med.strength_raw)])[-35:]
        if re.search(r"\b(?:moi lan|lieu(?: dung)?)\s*[:=]?\s*$", prefix):
            raise EvidenceError("Explicit administered amount mislabeled as strength")
    if med.strength_raw and med.strength_raw == med.dose_raw:
        raise EvidenceError("One amount cannot establish both strength and dose")
    if med.duration_raw and not re.search(r"\b(?:ngay|tuan|thang|nam)\b", fold(med.duration_raw)):
        raise EvidenceError("Invalid duration role")
    allowed = set(Medication.model_fields) - {"uncertain_fields", "evidence_text"}
    if not set(med.uncertain_fields) <= allowed:
        raise EvidenceError("Unknown uncertain field")
    result = med.model_copy(deep=True)
    for admin in result.administrations:
        admin.timing_slots_raw = timing_slots(admin.timing_raw)
    for pattern, key in ((NEGATION, "negation_raw"), (UNCERTAINTY, "uncertainty_raw")):
        marker = raw_marker(med.evidence_text, pattern)
        if marker and getattr(result, key) is None:
            setattr(result, key, marker)
        if getattr(result, key) and not pattern.search(fold(getattr(result, key))):
            raise EvidenceError(f"Unsupported {key}")
    if result.uncertainty_raw:
        # Model annotations may add uncertainty, but must never suppress the
        # backend's conservative flags by returning a nonempty, incomplete list.
        result.uncertain_fields = list(dict.fromkeys(result.uncertain_fields + [
            key for key in ("name_raw", "strength_raw", "dose_raw")
            if getattr(result, key) is not None
        ]))
    return result


def validate_understanding(value: Understanding, source: str) -> Understanding:
    for candidate in value.intents:
        _present(candidate.evidence_text, source, "intent evidence")
        _present(candidate.record_request_raw, candidate.evidence_text, "record_request_raw")
        if candidate.record_request_raw:
            marker = record_request_marker(source)
            if (candidate.intent != Intent.ADD_MEDICATION or marker is None or
                    marker not in candidate.evidence_text or
                    record_request_marker(candidate.record_request_raw) is None):
                raise EvidenceError("Unsupported explicit record request")
    meds = [validate_medication(med, source) for med in value.medications]
    if len({m.evidence_text for m in meds}) != len(meds):
        raise EvidenceError("Duplicate medication evidence")
    spans = sorted((source.find(m.evidence_text), source.find(m.evidence_text) + len(m.evidence_text)) for m in meds)
    if any(a[1] > b[0] for a, b in zip(spans, spans[1:])):
        raise EvidenceError("Overlapping medication evidence; separate the medication clauses")
    return value.model_copy(update={"medications": meds})
