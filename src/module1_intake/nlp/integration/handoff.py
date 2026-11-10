"""A confirmed-input DTO consumed by Module 2's existing identification adapter."""
from uuid import UUID

from ..models import ConfirmedEntry, Module2Handoff
from .persistence import CoreStore, medication


def build_handoff(store: CoreStore, workflow: dict) -> Module2Handoff:
    rows = store.entries(workflow)
    if not rows or workflow["state"] != "COMPLETED":
        raise ValueError("Completed owner confirmation required")
    for row in rows:
        store.assert_latest(row)
        if row["confirmed_at"] is None:
            raise ValueError("Unconfirmed entry cannot leave Module 1")
    return Module2Handoff(
        conversation_id=UUID(str(workflow["conversation_id"])),
        intake_id=UUID(str(workflow["intake_session_id"])),
        entries=[ConfirmedEntry(entry_version_id=UUID(str(row["id"])), content_digest=row["content_digest"],
                                medication=medication(row)) for row in rows],
        requested_workflows=workflow["context"].get("requested_workflows", ["MEDICATION_INTAKE"]))


def identify_confirmed(repo, handoff: Module2Handoff, *, dataset_build: str) -> list[tuple]:
    """Explicit application call, not automatically run by the chatbot.

    The adapter owns identity verification. Re-read owner, latest version, digest,
    and confirmation; never trust a deserialized DTO as authorization.
    """
    from shared.db.identification_adapter import run_identification

    store = CoreStore(repo)
    intake = repo._owned("intake_sessions", handoff.intake_id)
    if str(intake["conversation_id"]) != str(handoff.conversation_id):
        raise ValueError("Handoff conversation differs from its owned intake")
    results = []
    for item in handoff.entries:
        row = repo._owned("medication_entry_versions", item.entry_version_id)
        sources = repo._all("""SELECT p.session_id FROM msa.intake_items i
            JOIN msa.intake_extractions x ON x.id=i.extraction_id
            JOIN msa.intake_inputs p ON p.id=x.input_id WHERE i.id=%s AND i.user_id=%s""",
            (row["item_id"], repo.owner))
        if not sources or str(sources[0]["session_id"]) != str(handoff.intake_id):
            raise ValueError("Handoff entry belongs to a different intake")
        store.assert_latest(row)
        if row["confirmed_at"] is None or row["content_digest"] != item.content_digest:
            raise ValueError("Handoff is stale or unconfirmed")
        if medication(row) != item.medication:
            raise ValueError("Handoff fields differ from confirmed Core version")
    for item in handoff.entries:
        # Preserve negated entries in the DTO; never submit them as current exposure.
        if item.medication.negation_raw:
            continue
        results.append(run_identification(repo, item.entry_version_id, dataset_build=dataset_build))
    return results


def create_safety_snapshot(repo, matches):
    """Create the existing Core snapshot from explicitly identified handoff targets."""
    entries = [(match['entry_version_id'], match['id']) for match, result in matches]
    if len(entries) < 2:
        raise ValueError('Two non-negated confirmed targets are required')
    return repo.create_snapshot(entries)


def assess_confirmed_snapshot(repo, handoff, snapshot_id, dataset, *, request_key):
    """Preserve exact-target/latest/owner guards before the existing Module 3 call."""
    from shared.db.safety_adapter import run_safety
    store = CoreStore(repo)
    expected = {entry.entry_version_id for entry in handoff.entries if not entry.medication.negation_raw}
    rows = repo.snapshot_context(snapshot_id)
    if len(expected) < 2 or expected != {r['entry_version_id'] for r in rows}:
        raise ValueError('Snapshot must match the exact confirmed, non-negated targets')
    for entry in handoff.entries:
        store.assert_latest(repo._owned('medication_entry_versions', entry.entry_version_id))
    return run_safety(repo, snapshot_id, dataset, request_key=request_key)


def assessment_query(repo, handoff, assessment_id, question):
    """Bind read-only safety Q&A to current confirmed entry versions."""
    from ..qa_pipeline.contracts import RetrievalQuery
    store = CoreStore(repo)
    for entry in handoff.entries:
        store.assert_latest(repo._owned('medication_entry_versions', entry.entry_version_id))
    return RetrievalQuery(question=question, kind='safety',
        entry_ids=tuple(e.entry_version_id for e in handoff.entries if not e.medication.negation_raw),
        assessment_id=UUID(str(assessment_id)))
