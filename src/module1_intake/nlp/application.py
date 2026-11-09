"""Frontend-ready services over the existing chatbot/CoreRepository, not a DB layer.

The host constructs CoreRepository with its authenticated identity. No request DTO
accepts an owner/user ID. CLI identity selection is development-only.
"""
import json
from typing import Literal
from uuid import UUID

from pydantic import Field

from .dialogue import Chatbot
from .handoff import build_handoff, identify_confirmed
from .hybrid_qa import Answer, GroundedComposer, HybridQA
from .models import DialogueAct, Intent, Medication, Reply, StrictModel
from .persistence import medication
from .providers import OllamaProvider
from .retrieval import CoreAssessmentRetriever, CoreReferenceRetriever, EvidenceRef, RetrievalResult, VerifiedFact


class TurnRequest(StrictModel):
    workflow_id: UUID
    revision: int = Field(ge=1)
    text: str = Field(min_length=1, max_length=12000)


class ConfirmationRequest(StrictModel):
    workflow_id: UUID
    revision: int = Field(ge=1)
    request_key: UUID
    explicit_confirmation: bool


class EntryView(StrictModel):
    entry_version_id: UUID
    item_id: UUID
    content_digest: str
    confirmed: bool
    medication: Medication
    slot_status: dict[str, str]
    identity_status: Literal['NOT_ASSESSED'] = 'NOT_ASSESSED'


class ApplicationResponse(StrictModel):
    assistant_message: str
    workflow_id: UUID
    revision: int
    state: str
    next_action: str
    dialogue_act: DialogueAct
    active_intents: list[Intent]
    missing_blockers: list[dict] = Field(default_factory=list)
    entries: list[EntryView] = Field(default_factory=list)
    capability_status: dict[str, str]
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    qa_results: list[Answer] = Field(default_factory=list)
    action_authorized: bool = False  # Transcription confirmation only; never product/safety authority.
    authorization_scope: Literal['NONE', 'TRANSCRIPTION_ONLY'] = 'NONE'
    error_code: str | None = None


def entry_view(row):
    med = medication(row)
    statuses = {}
    for name in Medication.model_fields:
        if name.endswith('_raw'):
            statuses[name] = ('AMBIGUOUS' if name in med.uncertain_fields else 'MISSING' if getattr(med, name) is None
                              else 'USER_CONFIRMED' if row['confirmed_at'] else 'PRESENT_RAW')
    return EntryView(entry_version_id=row['id'], item_id=row['item_id'], content_digest=row['content_digest'],
                     confirmed=row['confirmed_at'] is not None, medication=med, slot_status=statuses)


class CoreRecords:
    def __init__(self, repo):
        self.repo = repo

    def list(self, *, history=False, limit=100):
        if not 1 <= limit <= 100:
            raise ValueError('Record limit must be between 1 and 100')
        query = ('SELECT * FROM msa.medication_entry_versions WHERE user_id=%s ORDER BY created_at DESC,id LIMIT %s'
                 if history else 'SELECT * FROM (SELECT DISTINCT ON (item_id) * FROM msa.medication_entry_versions '
                 'WHERE user_id=%s ORDER BY item_id,version_no DESC) latest ORDER BY created_at DESC,id LIMIT %s')
        return [entry_view(row) for row in self.repo._all(query, (self.repo.owner, limit))]

    def retrieve(self, query):
        entries = self.list()
        facts = [VerifiedFact(fact_id=str(entry.entry_version_id),
            text=('Đã xác nhận bản chép: ' if entry.confirmed else 'Bản nháp chưa xác nhận: ')
                 + entry.medication.model_dump_json(),
            source=EvidenceRef(source_id=str(entry.entry_version_id), locator='msa.medication_entry_versions/' + str(entry.entry_version_id),
                               sha256=entry.content_digest,
                               scope='Authenticated owner transcription record, not product verification or safety')) for entry in entries[:16]]
        return RetrievalResult(status='WORKING', coverage='OWNER_SCOPED_RECORDS', facts=facts,
            limitations=['Records are bounded to the latest 100 items. Confirmation verifies transcription only.'])


class ApplicationService:
    def __init__(self, repo, provider, *, reference=None, medication_retriever=None, composer=None):
        self.repo = repo
        self.records = CoreRecords(repo)
        self.qa = HybridQA(medication=medication_retriever or (CoreReferenceRetriever(reference) if reference else None),
            safety=CoreAssessmentRetriever(repo), records=self.records,
            composer=composer or GroundedComposer(provider if isinstance(provider, OllamaProvider) else None))
        self.bot = Chatbot(repo, provider, reference=reference, qa=self.qa)

    def capabilities(self):
        return {'extraction': 'WORKING', 'dialogue': 'WORKING', 'application_help': 'WORKING',
                'medication_reference': 'PARTIAL' if self.qa.medication else 'UNAVAILABLE',
                'safety': 'PARTIAL', 'owner_records': 'WORKING', 'reminders': 'UNAVAILABLE', 'document_rag': 'UNAVAILABLE'}

    def _response(self, reply):
        workflow = self.bot.store.workflow(reply.workflow_id)
        ctx = workflow['context']
        rows = self.bot.store.entries(workflow)
        answers = [Answer.model_validate(a) for a in ctx.get('qa_results', [])]
        return ApplicationResponse(assistant_message=reply.text, workflow_id=reply.workflow_id,
            revision=reply.revision, state=reply.state,
            next_action=ctx.get('next_action', 'SHOW_REVIEW' if reply.state == 'AWAITING_CONFIRMATION' else 'ASK_CLARIFICATION'),
            dialogue_act=DialogueAct(ctx.get('dialogue_act', 'UNKNOWN')),
            active_intents=[Intent(i) for i in ctx.get('active_intents', [])],
            missing_blockers=ctx.get('pending_questions', []), entries=[entry_view(row) for row in rows],
            capability_status=self.capabilities(), qa_results=answers,
            evidence_refs=[ref for answer in answers for ref in answer.evidence_refs],
            action_authorized=reply.state == 'COMPLETED' and bool(rows) and all(r['confirmed_at'] is not None for r in rows),
            authorization_scope='TRANSCRIPTION_ONLY' if reply.state == 'COMPLETED' and rows and all(r['confirmed_at'] is not None for r in rows) else 'NONE',
            error_code=ctx.get('error_code'))

    def start(self, *, conversation_id=None, task=None):
        return self._response(self.bot.start(conversation_id=conversation_id, task=task))

    def send(self, request: TurnRequest):
        return self._response(self.bot.send(request.workflow_id, request.text, expected_revision=request.revision))

    def resume(self, workflow_id):
        workflow = self.bot.store.workflow(workflow_id)
        ctx = workflow['context']
        text = ctx.get('assistant_message', 'Đã khôi phục workflow; hãy kiểm tra trạng thái và revision trước khi tiếp tục.')
        if workflow['state'] == 'AWAITING_CONFIRMATION':
            draft = ctx.get('draft') or {}
            if draft.get('display_message_id'):
                text = self.repo._owned('conversation_messages', draft['display_message_id'])['text_content']
        return self._response(Reply(text=text, workflow_id=workflow['id'], revision=workflow['revision'], state=workflow['state']))

    def confirm(self, request: ConfirmationRequest):
        return self._response(self.bot.confirm(request.workflow_id, expected_revision=request.revision,
            request_key=request.request_key, explicit_confirmation=request.explicit_confirmation))

    def revise(self, workflow_id):
        return self._response(self.bot.revise(workflow_id))

    def handoff(self, workflow_id):
        return build_handoff(self.bot.store, self.bot.store.workflow(workflow_id))

    def identify(self, workflow_id, *, dataset_build):
        return identify_confirmed(self.repo, self.handoff(workflow_id), dataset_build=dataset_build)

    def prepare_safety_snapshot(self, workflow_id, *, dataset_build):
        """Explicit server call; never triggered by an LLM intent or candidate IDs."""
        matches = self.identify(workflow_id, dataset_build=dataset_build)
        entries = [(match['entry_version_id'], match['id']) for match, result in matches]
        if len(entries) < 2:
            raise ValueError('Two non-negated confirmed targets are required')
        return self.repo.create_snapshot(entries)

    def assess_snapshot(self, workflow_id, snapshot_id, dataset, *, request_key):
        from shared.db.safety_adapter import run_safety
        handoff = self.handoff(workflow_id)  # Owner/latest/version/confirmation guards.
        expected = {entry.entry_version_id for entry in handoff.entries if not entry.medication.negation_raw}
        rows = self.repo.snapshot_context(snapshot_id)
        if len(expected) < 2 or expected != {r['entry_version_id'] for r in rows}:
            raise ValueError('Snapshot must match the exact confirmed, non-negated targets')
        for entry in handoff.entries:
            self.bot.store.assert_latest(self.repo._owned('medication_entry_versions', entry.entry_version_id))
        return run_safety(self.repo, snapshot_id, dataset, request_key=request_key)

    def answer_assessment(self, workflow_id, assessment_id, question):
        from .retrieval import RetrievalQuery
        handoff = self.handoff(workflow_id)
        for entry in handoff.entries:
            self.bot.store.assert_latest(self.repo._owned('medication_entry_versions', entry.entry_version_id))
        return self.qa.answer(Intent.CHECK_INTERACTION, RetrievalQuery(question=question, kind='safety',
            entry_ids=tuple(e.entry_version_id for e in handoff.entries if not e.medication.negation_raw),
            assessment_id=UUID(str(assessment_id))))
