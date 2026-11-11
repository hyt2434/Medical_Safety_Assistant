"""A confirmed-input DTO consumed by Module 2's existing identification adapter."""
from uuid import UUID
from shared.db.intake_adapter import build_confirmed_handoff

from ..models import ConfirmedEntry, Module2Handoff
from .persistence import CoreStore, medication


def build_handoff(store: CoreStore, workflow: dict) -> Module2Handoff:
    return build_confirmed_handoff(store.repo, workflow['id'])


def identify_confirmed(repo, handoff: Module2Handoff, *, dataset_build: str) -> list[tuple]:
    """Explicit application call, not automatically run by the chatbot.

    The adapter owns identity verification. Re-read owner, latest version, digest,
    and confirmation; never trust a deserialized DTO as authorization.
    """
    from module2_medications import identify_confirmed as identify_medications
    return identify_medications(repo, handoff, dataset_build=dataset_build)


def create_safety_snapshot(repo, matches, *, data_context='PATIENT'):
    """Create the existing Core snapshot from explicitly identified handoff targets."""
    entries = [(match['entry_version_id'], match['id']) for match, result in matches]
    if len(entries) < 2:
        raise ValueError('Two non-negated confirmed targets are required')
    return repo.create_snapshot(entries, data_context=data_context)


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
