"""Coordinate the existing Core repository; no new storage or DB schema."""
from copy import deepcopy
from contextlib import contextmanager
from typing import Any, Protocol
from uuid import UUID

from shared.db.intake_adapter import medication_fields, persist_module1, entry_medication, assert_latest_entry

from ..models import Medication


class Repository(Protocol):
    owner: UUID
    def create_conversation(self) -> dict: ...
    def create_intake(self, conversation=None, *, purpose="MEDICATION_COLLECTION") -> dict: ...
    def create_workflow(self, conversation, workflow_type, *, intake=None, origin_message=None) -> dict: ...
    def append_message(self, conversation, role, body, metadata=None) -> dict: ...
    def transition_workflow(self, workflow, state, *, expected_revision, context=None) -> dict: ...
    def _owned(self, table, identity, *, lock=False) -> dict: ...
    def _all(self, query, params=()) -> list[dict]: ...
    def _one(self, query, params=()) -> dict: ...
    def digest(self, value) -> str: ...
    def record_input(self, intake, modality, original_bytes, *, payload, content_type=None, message=None) -> dict: ...
    def record_extraction(self, input_id, extractor_name, extractor_version, result, *, status="SUCCEEDED", errors=None) -> dict: ...
    def create_item(self, extraction, ordinal, medication_fields, *, locator=None) -> dict: ...
    def correct_entry(self, entry, medication_fields, *, source_extraction=None) -> dict: ...
    def confirm_entry(self, entry, displayed_digest, request_key, *, explicit_confirmation) -> dict: ...


def fields(med: Medication) -> dict[str, Any]:
    # V4 explicitly permits extension fields and already uses dosage_form_raw in Module 2.
    return medication_fields(med.model_dump())


def medication(row: dict) -> Medication:
    return entry_medication(row)


def extraction(meds: list[Medication]) -> dict:
    return {"schema": "extraction.v4", "medications": [fields(m) for m in meds],
            "warnings": [], "document_instructions_raw": []}


def message_metadata(voice=None):
    metadata = {"schema": "message.v4", "content_refs": [], "input_source": "VOICE" if voice else "TEXT"}
    if voice:
        metadata['voice'] = deepcopy(voice)
    return metadata


def input_payload(text, message):
    payload = {"schema": "input.v4", "digest_basis": "ORIGINAL_BYTES", "text": text}
    metadata = message.get('metadata') or {}
    payload['input_source'] = metadata.get('input_source', 'TEXT')
    if payload['input_source'] == 'VOICE':
        payload['voice'] = deepcopy(metadata['voice'])
    return payload


def manual_selection(repo, row):
    """Only the current version's explicit form selection can constrain identity."""
    if not row.get('source_extraction_id'):
        return None
    attempt = repo._owned('intake_extractions', row['source_extraction_id'])
    inp = repo._owned('intake_inputs', attempt['input_id'])
    payload = inp.get('payload_or_locator', inp.get('payload', {}))
    if inp['modality'] == 'MANUAL' and payload.get('input_source') == 'MANUAL':
        return deepcopy(payload.get('manual_fields', {}).get('selected_product'))
    return None


class CoreStore:
    def __init__(self, repo: Repository):
        self.repo = repo

    def workflow(self, identity) -> dict:
        return self.repo._owned("workflow_instances", identity)

    @contextmanager
    def turn(self, identity):
        # Session advisory lock leaves the connection IDLE between Core operations.
        # An outer transaction would violate CoreRepository's transaction contract.
        key = "nlp-v1:" + str(self.repo.owner) + ":" + str(identity)
        locked = self.repo._one("SELECT pg_try_advisory_lock(hashtextextended(%s,0)) AS locked", (key,))["locked"]
        if not locked:
            raise ValueError("Conversation turn is already in progress")
        try:
            yield
        finally:
            self.repo._one("SELECT pg_advisory_unlock(hashtextextended(%s,0)) AS unlocked", (key,))

    def entries(self, workflow: dict) -> list[dict]:
        ids = workflow["context"].get("entry_version_ids", [])
        return [self.repo._owned("medication_entry_versions", identity) for identity in ids]

    def assert_latest(self, row: dict) -> None:
        assert_latest_entry(self.repo, row)

    def save(self, workflow: dict, text: str, message: dict, meds: list[Medication],
             updates: dict[int, Medication], provider: str) -> list[dict]:
        old = self.entries(workflow)
        payload = input_payload(text, message)
        if not updates:
            saved = persist_module1(self.repo, workflow["intake_session_id"], text.encode("utf-8"),
                                    extraction(meds), modality="TEXT", input_payload=payload,
                                    extractor_name=provider, extractor_version="nlp-mvp-v1",
                                    content_type="text/plain; charset=utf-8", message=message["id"])
            return old + saved["entries"]
        # An update extraction contains only the CURRENT source fragment. The new entry
        # version combines old evidence with that fragment and links the new extraction.
        inp = self.repo.record_input(workflow["intake_session_id"], "TEXT", text.encode("utf-8"),
                                     payload=payload, content_type="text/plain; charset=utf-8", message=message["id"])
        attempt = self.repo.record_extraction(inp["id"], provider, "nlp-mvp-v1", extraction(meds))
        remaining = list(meds)
        for index, patch in updates.items():
            prior = old[index]
            self.assert_latest(prior)
            merged = deepcopy(prior["medication_fields"])
            changed = patch.model_dump(exclude_none=True)
            for key, value in changed.items():
                if key == "evidence_text" or value == []:
                    continue
                merged[key] = value
            merged["evidence_text"] = merged["evidence_text"] + "\n" + patch.evidence_text
            old[index] = self.repo.correct_entry(prior["id"], merged, source_extraction=attempt["id"])
            remaining.remove(patch)
        old.extend(self.repo.create_item(attempt["id"], n, fields(m)) for n, m in enumerate(remaining, 1))
        return old
