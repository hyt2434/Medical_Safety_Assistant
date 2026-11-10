"""Frontend-ready services over the existing chatbot/CoreRepository, not a DB layer.

The host constructs CoreRepository with its authenticated identity. No request DTO
accepts an owner/user ID. CLI identity selection is development-only.
"""
import json
from typing import Literal
from uuid import UUID

from pydantic import Field

from ..dialogue_management.manager import Chatbot
from ..integration.handoff import (
    assessment_query, assess_confirmed_snapshot, build_handoff,
    create_safety_snapshot, identify_confirmed,
)
from ..qa_pipeline.pipeline import Answer, GroundedComposer, HybridQA
from ..models import EntryView, DialogueAct, Intent, Medication, Reply, StrictModel
from ..integration.persistence import medication
from ..understanding.providers import OllamaProvider
from ..qa_pipeline.structured import CoreRecords, entry_view, CoreAssessmentRetriever, CoreReferenceRetriever, EvidenceRef, RetrievalResult, VerifiedFact
from ..understanding.validation import fold




class TurnRequest(StrictModel):
    workflow_id: UUID
    revision: int = Field(ge=1)
    text: str = Field(min_length=1, max_length=12000)




class ConfirmationRequest(StrictModel):
    workflow_id: UUID
    revision: int = Field(ge=1)
    request_key: UUID
    explicit_confirmation: bool


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
        return create_safety_snapshot(self.repo, matches)

    def assess_snapshot(self, workflow_id, snapshot_id, dataset, *, request_key):
        handoff = self.handoff(workflow_id)  # Owner/latest/version/confirmation guards.
        return assess_confirmed_snapshot(self.repo, handoff, snapshot_id, dataset, request_key=request_key)

    def answer_assessment(self, workflow_id, assessment_id, question):
        handoff = self.handoff(workflow_id)
        return self.qa.answer(Intent.CHECK_INTERACTION,
            assessment_query(self.repo, handoff, assessment_id, question))
