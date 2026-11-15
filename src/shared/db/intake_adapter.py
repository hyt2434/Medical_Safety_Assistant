"""Persist Module 1 extraction without altering Module 1 source or bypassing confirmation."""
from copy import deepcopy

RAW_FIELDS = ("name_raw", "strength_raw", "dose_raw", "route_raw", "frequency_raw",
              "duration_raw", "quantity_raw", "instructions_raw", "evidence_text")


def medication_fields(raw):
    value = deepcopy(raw)
    value["schema"] = "medication-entry.v4"
    for key in RAW_FIELDS:
        value.setdefault(key, None)
    value.setdefault("administrations", [])
    value.setdefault("uncertain_fields", [])
    return value


def persist_module1(repo, intake, original_bytes, extraction, *, modality, input_payload,
                    extractor_name, extractor_version, content_type=None, message=None):
    raw = extraction.model_dump() if hasattr(extraction, "model_dump") else deepcopy(extraction)
    if not isinstance(raw, dict) or not isinstance(raw.get("medications"), list):
        raise ValueError("Module 1 extraction must contain medications array")
    result = deepcopy(raw)
    result.update(schema="extraction.v4", medications=[medication_fields(m) for m in raw["medications"]])
    result.setdefault("warnings", [])
    result.setdefault("document_instructions_raw", [])
    inp = repo.record_input(intake, modality, original_bytes, payload=input_payload,
                            content_type=content_type, message=message)
    attempt = repo.record_extraction(inp["id"], extractor_name, extractor_version, result)
    entries = [repo.create_item(attempt["id"], n, med) for n, med in enumerate(result["medications"], 1)]
    return {"input": inp, "extraction": attempt, "entries": entries, "requires_user_review": True}
