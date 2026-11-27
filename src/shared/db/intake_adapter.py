"""Shared Core intake/confirmed-handoff boundary for all Module 1 input sources."""
from copy import deepcopy
from uuid import UUID
from shared.intake_contracts import Medication, ConfirmedEntry, Module2Handoff

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


def entry_medication(row):
    """Read the shared confirmed-medication shape, without extractor-specific models."""
    return Medication.model_validate({k: v for k, v in row['medication_fields'].items() if k != 'schema'})


def assert_latest_entry(repo, row):
    versions = repo._all('''SELECT id FROM msa.medication_entry_versions
        WHERE item_id=%s AND user_id=%s ORDER BY version_no DESC LIMIT 1''', (row['item_id'], repo.owner))
    if not versions or str(versions[0]['id']) != str(row['id']):
        raise ValueError('Entry has a newer version; redisplay before confirmation')


def build_confirmed_handoff(repo, workflow_id):
    """Build the existing DTO from an owned, completed Core review, for any source.

    Review adapters own explicit action/revision/display-digest validation before
    Core confirmation. This read-only function never confirms an entry itself.
    """
    workflow = repo._owned('workflow_instances', workflow_id)
    rows = [repo._owned('medication_entry_versions', identity)
            for identity in workflow['context'].get('entry_version_ids', [])]
    if not rows or workflow['state'] != 'COMPLETED':
        raise ValueError('Completed owner confirmation required')
    for row in rows:
        assert_latest_entry(repo, row)
        if row['confirmed_at'] is None:
            raise ValueError('Unconfirmed entry cannot leave Module 1')
    return Module2Handoff(conversation_id=UUID(str(workflow['conversation_id'])), intake_id=UUID(str(workflow['intake_session_id'])),
        entries=[ConfirmedEntry(entry_version_id=UUID(str(row['id'])), content_digest=row['content_digest'],
                                medication=entry_medication(row)) for row in rows],
        requested_workflows=workflow['context'].get('requested_workflows', ['MEDICATION_INTAKE']))


def persist_module1(repo, intake, original_bytes, extraction, *, modality, input_payload,
                    extractor_name, extractor_version, content_type=None, message=None, item_locators=None):
    raw = extraction.model_dump() if hasattr(extraction, "model_dump") else deepcopy(extraction)
    if not isinstance(raw, dict) or not isinstance(raw.get("medications"), list):
        raise ValueError("Module 1 extraction must contain medications array")
    if item_locators is not None and (not isinstance(item_locators, list) or
            len(item_locators) != len(raw['medications']) or any(not isinstance(x, dict) for x in item_locators)):
        raise ValueError('Item locators must be an object array aligned with medications')
    result = deepcopy(raw)
    result.update(schema="extraction.v4", medications=[medication_fields(m) for m in raw["medications"]])
    result.setdefault("warnings", [])
    result.setdefault("document_instructions_raw", [])
    inp = repo.record_input(intake, modality, original_bytes, payload=input_payload,
                            content_type=content_type, message=message)
    attempt = repo.record_extraction(inp["id"], extractor_name, extractor_version, result)
    entries = [repo.create_item(attempt["id"], n, med,
                               **({'locator': deepcopy(item_locators[n - 1])} if item_locators is not None else {}))
               for n, med in enumerate(result["medications"], 1)]
    return {"input": inp, "extraction": attempt, "entries": entries, "requires_user_review": True}
