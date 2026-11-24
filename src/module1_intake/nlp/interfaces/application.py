"""Frontend-ready services over the existing chatbot/CoreRepository, not a DB layer.

The host constructs CoreRepository with its authenticated identity. No request DTO
accepts an owner/user ID. CLI identity selection is development-only.
"""
from copy import deepcopy
import hashlib
import json
import re
from typing import Literal
from uuid import UUID, uuid4

from pydantic import Field

from ..dialogue_management.manager import Chatbot
from ..integration.handoff import (
    assessment_query, assess_confirmed_snapshot, build_handoff,
    create_safety_snapshot, identify_confirmed,
)
from ..qa_pipeline.pipeline import Answer, GroundedComposer, HybridQA, document_question
from ..qa_pipeline.rag.documents import LocalDocumentRetriever
from ..qa_pipeline.contracts import RetrievalQuery
from ..models import EntryView, DialogueAct, Intent, Medication, Reply, StrictModel, Understanding
from ..integration.persistence import medication, message_metadata, extraction, fields
from ..integration.persistence import manual_selection
from ..understanding.providers import OllamaProvider
from ..understanding.providers import InferenceError, understand
from ..understanding.routing import detect, explicit_backend_action
from ..qa_pipeline.structured import CoreRecords, entry_view, CoreAssessmentRetriever, CoreReferenceRetriever, EvidenceRef, RetrievalResult, VerifiedFact, identification_result
from ..understanding.validation import fold


__all__ = [
    'ApplicationService', 'ApplicationResponse', 'TurnRequest', 'ConfirmationRequest',
    'WorkflowActionRequest', 'ManualInputRequest', 'ManualEditRequest', 'EntryEditRequest',
    'VoiceRequest', 'VoiceDraftRequest', 'VoiceEditRequest', 'VoiceSubmitRequest',
    'VoiceDraft', 'VoicePreview', 'EntryView',
]




class TurnRequest(StrictModel):
    workflow_id: UUID
    revision: int = Field(ge=1)
    text: str = Field(min_length=1, max_length=12000)




class ConfirmationRequest(StrictModel):
    workflow_id: UUID
    revision: int = Field(ge=1)
    request_key: UUID
    explicit_confirmation: bool


class VoiceRequest(StrictModel):
    workflow_id: UUID
    revision: int = Field(ge=1)
    audio_payload: bytes | str
    language: str = 'vi-VN'


class VoiceDraftRequest(StrictModel):
    workflow_id: UUID
    revision: int = Field(ge=1)
    draft_id: UUID


class VoiceEditRequest(VoiceDraftRequest):
    text: str = Field(min_length=1, max_length=12000)


class VoiceSubmitRequest(VoiceDraftRequest):
    explicit_confirmation: bool


class ManualInputRequest(StrictModel):
    workflow_id: UUID
    revision: int = Field(ge=1)
    source_medication_id: str = Field(min_length=1, max_length=120)
    dataset_build: str | None = Field(default=None, pattern='^[0-9a-f]{64}$')
    medication: Medication


class ManualEditRequest(ManualInputRequest):
    entry_version_id: UUID


class EntryEditRequest(StrictModel):
    workflow_id: UUID
    revision: int = Field(ge=1)
    entry_version_id: UUID
    medication: Medication
    source_medication_id: str | None = Field(default=None, min_length=1, max_length=120)
    dataset_build: str | None = Field(default=None, pattern='^[0-9a-f]{64}$')


class VoiceDraft(StrictModel):
    draft_id: UUID
    audio_input_id: UUID
    raw_transcript: str
    text: str = Field(min_length=1, max_length=12000)
    confidence_score: float | None = Field(default=None, ge=0, le=1)
    language: str


class VoicePreview(StrictModel):
    workflow_id: UUID
    revision: int
    draft: VoiceDraft | None
    error_code: str | None = None
    retry_allowed: bool = True
    next_action: str = 'REVIEW_VOICE_DRAFT'


class WorkflowActionRequest(StrictModel):
    workflow_id: UUID
    revision: int = Field(ge=1)
    request_key: UUID
    action: Literal['IDENTIFY', 'ASSESS']
    explicit_request: bool


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
    identification_results: list[dict] = Field(default_factory=list)
    assessment_id: UUID | None = None
    snapshot_id: UUID | None = None
    executed_action: Literal['IDENTIFY', 'ASSESS'] | None = None


class ApplicationService:
    def __init__(self, repo, provider, *, reference=None, medication_retriever=None, composer=None,
                 dataset_build=None, dataset=None, data_context='PATIENT', documents=None):
        self.repo = repo
        self.dataset_build = dataset_build or getattr(reference, 'build', None)
        self.dataset = dataset
        if data_context not in {'PATIENT', 'SYNTHETIC_TEST'}:
            raise ValueError('Unsupported snapshot data context')
        self.data_context = data_context
        self.records = CoreRecords(repo)
        composer = composer or GroundedComposer(provider if isinstance(provider, OllamaProvider) else None)
        self.qa = HybridQA(medication=medication_retriever or (CoreReferenceRetriever(reference) if reference else None),
            safety=CoreAssessmentRetriever(repo), records=self.records,
            composer=composer, documents=documents if documents is not None else LocalDocumentRetriever(provider=composer.provider))
        self.bot = Chatbot(repo, provider, reference=reference, qa=self.qa)

    def capabilities(self):
        return {'extraction': 'WORKING', 'dialogue': 'WORKING', 'application_help': 'WORKING',
                'medication_identification': 'PARTIAL' if self.dataset_build else 'UNAVAILABLE',
                'medication_reference': 'PARTIAL' if self.qa.medication else 'UNAVAILABLE',
                'safety': 'PARTIAL', 'owner_records': 'WORKING', 'reminders': 'UNAVAILABLE', 'document_rag': 'PARTIAL'}

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

    def send(self, request: TurnRequest, *, _voice=None):
        if not request.text.strip():
            raise ValueError('Message must contain 1–12000 characters')
        workflow = self.bot._check(request.workflow_id, request.revision)
        if workflow['context'].get('voice_draft') and _voice is None:
            raise ValueError('Review, edit, submit or discard the pending voice draft first')
        if document_question(request.text):
            return self._document_turn(request, _voice=_voice)
        if workflow['state'] == 'COMPLETED' and fold(request.text.strip().rstrip('.!')) not in {'xac nhan', 'toi xac nhan'}:
            workflow = self.bot._check(request.workflow_id, request.revision)
            return self._completed_turn(request, workflow)
        return self._response(self.bot.send(request.workflow_id, request.text, expected_revision=request.revision, _voice=_voice))

    def resume_voice(self, workflow_id):
        workflow = self.bot.store.workflow(workflow_id)
        raw = workflow['context'].get('voice_draft')
        return VoicePreview(workflow_id=workflow['id'], revision=workflow['revision'],
            draft=VoiceDraft.model_validate_json(json.dumps(raw)) if raw else None,
            retry_allowed=workflow['state'] not in {'COMPLETED', 'CANCELLED', 'FAILED'},
            next_action='REVIEW_VOICE_DRAFT' if raw else 'TYPE_OR_RECORD')

    def _save_voice_draft(self, workflow, draft):
        ctx = deepcopy(workflow['context'])
        if draft is None:
            ctx.pop('voice_draft', None)
        else:
            ctx['voice_draft'] = draft.model_dump(mode='json')
        if workflow['state'] == 'AWAITING_CONFIRMATION':
            # Refresh the existing medication review/digest at the new revision.
            question = (ctx.get('pending_questions') or [{}])[0].get('question')
            self.bot._display(workflow, ctx, question=question)
        else:
            self.bot._transition(workflow, workflow['state'], ctx)
        return self.resume_voice(workflow['id'])

    def preview_voice(self, request: VoiceRequest):
        from ... import api as intake_api
        from ...voice.asr import VoiceInputError, _to_bytes

        with self.bot.store.turn(request.workflow_id):
            workflow = self.bot._check(request.workflow_id, request.revision)
            if workflow['state'] in {'COMPLETED', 'CANCELLED', 'FAILED'}:
                raise ValueError('Start or revise an active workflow before voice input')
            try:
                audio = _to_bytes(request.audio_payload)
                result = intake_api.transcribe_voice(audio, request.language)
                if len(result['raw_transcript']) > 12000:
                    raise VoiceInputError('INVALID_AUDIO', 'Transcript exceeds the message limit')
            except VoiceInputError as error:
                return self.resume_voice(request.workflow_id).model_copy(update={'error_code': error.code})
            # The current adapter does not retain audio objects. Core AUDIO requires
            # a real retained object; record the ASR text as TEXT instead of inventing
            # a locator. Keep the source-byte digest as separate provenance.
            inp = self.repo.record_input(workflow['intake_session_id'], 'TEXT',
                result['raw_transcript'].encode('utf-8'), content_type='text/plain; charset=utf-8',
                payload={'schema': 'input.v4', 'digest_basis': 'ORIGINAL_BYTES',
                         'text': result['raw_transcript'], 'input_source': 'VOICE',
                         'audio_retained': False, 'audio_sha256': hashlib.sha256(audio).hexdigest(),
                         'language': request.language, 'confidence_score': result['confidence_score']})
            draft = VoiceDraft(draft_id=uuid4(), audio_input_id=inp['id'],
                raw_transcript=result['raw_transcript'], text=result['raw_transcript'],
                confidence_score=result['confidence_score'], language=request.language)
            return self._save_voice_draft(workflow, draft)

    def _voice_draft(self, request):
        workflow = self.bot._check(request.workflow_id, request.revision)
        draft = workflow['context'].get('voice_draft')
        if not draft or draft['draft_id'] != str(request.draft_id):
            raise ValueError('Voice draft changed; reload and review it')
        return workflow, VoiceDraft.model_validate_json(json.dumps(draft))

    def edit_voice(self, request: VoiceEditRequest):
        with self.bot.store.turn(request.workflow_id):
            workflow, draft = self._voice_draft(request)
            if not request.text.strip():
                raise ValueError('Voice draft must contain text')
            return self._save_voice_draft(workflow, draft.model_copy(update={'text': request.text}))

    def discard_voice(self, request: VoiceDraftRequest):
        with self.bot.store.turn(request.workflow_id):
            workflow, _ = self._voice_draft(request)
            return self._save_voice_draft(workflow, None)

    def submit_voice(self, request: VoiceSubmitRequest):
        if request.explicit_confirmation is not True:
            raise ValueError('Explicit review of the voice transcript is required')
        with self.bot.store.turn(request.workflow_id):
            _, draft = self._voice_draft(request)
            # The exact reviewed text enters the same turn routing/extraction as typing.
            # NLP failure retains the editable draft; success consumes it.
            return self.send(TurnRequest(workflow_id=request.workflow_id, revision=request.revision,
                text=draft.text), _voice=draft.model_dump(mode='json'))

    def _document_turn(self, request, *, _voice=None):
        """Knowledge questions need no single drug target or medication extraction."""
        with self.bot.store.turn(request.workflow_id):
            workflow = self.bot._check(request.workflow_id, request.revision)
            if workflow['state'] in {'CANCELLED', 'FAILED'}:
                raise ValueError('Terminal workflow; start a new dialogue')
            answer = self.qa.answer(Intent.MEDICATION_QA, RetrievalQuery(request.text, 'document'))
            self.repo.append_message(workflow['conversation_id'], 'USER', request.text, message_metadata(_voice))
            if workflow['state'] == 'COMPLETED':
                saved = self._saved_action(workflow)
                response = (ApplicationResponse.model_validate_json(json.dumps(saved['application_response'])) if saved else
                            self._response(Reply(text='', workflow_id=workflow['id'], revision=workflow['revision'], state=workflow['state'])))
                response.assistant_message, response.qa_results = answer.text, [answer]
                response.evidence_refs, response.executed_action = answer.evidence_refs, None
                response.dialogue_act, response.active_intents = DialogueAct.ASK_QUESTION, [Intent.MEDICATION_QA]
                response.next_action = 'SHOW_ANSWER' if answer.evidence_refs else 'UNAVAILABLE'
                return self._retain_response(workflow, response)
            ctx = deepcopy(workflow['context'])
            if _voice:
                ctx.pop('voice_draft', None)
            ctx.update(qa_results=[answer.model_dump(mode='json')], dialogue_act='ASK_QUESTION',
                       active_intents=[Intent.MEDICATION_QA.value], next_action='SHOW_ANSWER' if answer.evidence_refs else 'UNAVAILABLE')
            ctx.pop('error_code', None)
            if workflow['state'] == 'AWAITING_CONFIRMATION':
                # Use the existing review renderer so a side question cannot make
                # the displayed draft/revision or confirmation digest stale.
                self.repo.append_message(workflow['conversation_id'], 'ASSISTANT', answer.text)
                reply = self.bot._display(workflow, ctx)
            else:
                reply = self.bot._reply(workflow, answer.text, context=ctx)
            return self._response(reply)

    def resume(self, workflow_id):
        workflow = self.bot.store.workflow(workflow_id)
        ctx = workflow['context']
        if workflow['state'] == 'COMPLETED':
            saved = self._saved_action(workflow)
            if saved:
                self.handoff(workflow_id)  # Recheck current target versions before returning retained results.
                response = ApplicationResponse.model_validate_json(json.dumps(saved['application_response']))
                response.capability_status = self.capabilities()
                return response
        text = ctx.get('assistant_message', 'Đã khôi phục workflow; hãy kiểm tra trạng thái và revision trước khi tiếp tục.')
        if workflow['state'] == 'AWAITING_CONFIRMATION':
            draft = ctx.get('draft') or {}
            if draft.get('display_message_id'):
                text = self.repo._owned('conversation_messages', draft['display_message_id'])['text_content']
        return self._response(Reply(text=text, workflow_id=workflow['id'], revision=workflow['revision'], state=workflow['state']))

    def confirm(self, request: ConfirmationRequest):
        return self._response(self.bot.confirm(request.workflow_id, expected_revision=request.revision,
            request_key=request.request_key, explicit_confirmation=request.explicit_confirmation))

    def save_manual(self, request: ManualInputRequest, *, _allow_confirmed=False):
        """Persist an explicit catalog selection/form for review, never identify it."""
        with self.bot.store.turn(request.workflow_id):
            workflow = self.bot._check(request.workflow_id, request.revision)
            if workflow['state'] in {'COMPLETED', 'CANCELLED', 'FAILED'}:
                raise ValueError('Start or revise an active workflow before manual input')
            if workflow['context'].get('voice_draft'):
                raise ValueError('Submit or discard the pending voice draft first')
            if not self.dataset_build or not self.repo._one(
                    'SELECT msa.published(%s) AS ok', (self.dataset_build,))['ok']:
                raise ValueError('Manual selection requires a published Core catalog build')
            if request.dataset_build is not None and request.dataset_build != self.dataset_build:
                raise ValueError('Catalog version changed; search and review the product again')
            products = self.repo._all('''SELECT * FROM msa_ref.medications
                WHERE dataset_build=%s AND source_medication_id=%s''',
                (self.dataset_build, request.source_medication_id))
            if len(products) != 1:
                raise ValueError('Selected catalog ID must resolve to exactly one Core product')
            product = products[0]
            selection = {'dataset_build': self.dataset_build, 'medication_id': str(product['id']),
                'source_medication_id': product['source_medication_id'], 'brand_name': product['brand_name'],
                'dosage_form': product['dosage_form'],
                'registration_token': product['product_details'].get('registration_token')}
            rows = self.bot.store.entries(workflow)
            index = None
            if isinstance(request, ManualEditRequest):
                indexes = [n for n, row in enumerate(rows) if str(row['id']) == str(request.entry_version_id)]
                if len(indexes) != 1:
                    raise ValueError('Manual edit target is not in the current workflow review')
                index = indexes[0]
                self.bot.store.assert_latest(rows[index])
                if rows[index]['confirmed_at'] is not None and not _allow_confirmed:
                    raise ValueError('Revise confirmed medication through the existing correction flow')
            med = request.medication
            if not med.name_raw or fold(med.name_raw) != fold(product['brand_name']):
                raise ValueError('Form name differs from the explicitly selected catalog product')
            form = med.model_dump(mode='json')
            payload = {'schema': 'input.v4', 'digest_basis': 'ORIGINAL_BYTES', 'input_source': 'MANUAL',
                'manual_fields': {'selected_product': selection, 'medication': form}}
            text = json.dumps(payload['manual_fields'], ensure_ascii=False, sort_keys=True)
            message = self.repo.append_message(workflow['conversation_id'], 'USER', text,
                {'schema': 'message.v4', 'content_refs': [], 'input_source': 'MANUAL', 'selected_product': selection})
            inp = self.repo.record_input(workflow['intake_session_id'], 'MANUAL', text.encode('utf-8'),
                payload=payload, content_type='application/json; charset=utf-8', message=message['id'])
            attempt = self.repo.record_extraction(inp['id'], 'manual-form', 'manual-form-v1', extraction([med]))
            if index is None:
                rows.append(self.repo.create_item(attempt['id'], 1, fields(med)))
            else:
                rows[index] = self.repo.correct_entry(rows[index]['id'], fields(med), source_extraction=attempt['id'])
            ctx = deepcopy(workflow['context'])
            ctx.update(entry_version_ids=[str(row['id']) for row in rows], pending_confirmation=None,
                awaiting_purpose=False, active_intents=[Intent.ADD_MEDICATION.value],
                dialogue_act='CORRECT' if index is not None else 'PROVIDE_INFO', qa_results=[])
            ctx.pop('error_code', None)
            return self._response(self.bot._intake_progress(workflow, ctx, rows))

    def revise(self, workflow_id, *, expected_revision=None):
        with self.bot.store.turn(workflow_id):
            if expected_revision is not None:
                self.bot._check(workflow_id, expected_revision)
            return self._response(self.bot.revise(workflow_id))

    def edit_entry(self, request: EntryEditRequest):
        """Explicit form correction; retain the real source and catalog choice."""
        with self.bot.store.turn(request.workflow_id):
            workflow = self.bot._check(request.workflow_id, request.revision)
            if workflow['state'] in {'COMPLETED', 'CANCELLED', 'FAILED'} or workflow['context'].get('voice_draft'):
                raise ValueError('Start an explicit revision or finish transcript review before editing')
            rows = self.bot.store.entries(workflow)
            indexes = [i for i, row in enumerate(rows) if str(row['id']) == str(request.entry_version_id)]
            if len(indexes) != 1:
                raise PermissionError('Entry is outside the current owned review')
            index = indexes[0]
            prior = rows[index]
            self.bot.store.assert_latest(prior)
            if prior['confirmed_at'] is not None:
                previous = workflow['context'].get('revises_workflow_id')
                old = self.bot.store.workflow(previous) if previous else None
                if not old or old['state'] != 'COMPLETED' or str(prior['id']) not in old['context'].get('entry_version_ids', []):
                    raise ValueError('Confirmed entries require an explicit correction workflow')
            selected = manual_selection(self.repo, prior)
            source_id = request.source_medication_id or (selected or {}).get('source_medication_id')
            if source_id:
                return self.save_manual(ManualEditRequest(workflow_id=request.workflow_id, revision=request.revision,
                    entry_version_id=request.entry_version_id, source_medication_id=source_id, medication=request.medication,
                    dataset_build=request.dataset_build or (selected or {}).get('dataset_build')),
                    _allow_confirmed=True)
            attempt = self.repo._owned('intake_extractions', prior['source_extraction_id'])
            inp = self.repo._owned('intake_inputs', attempt['input_id'])
            source = inp['payload_or_locator'].get('input_source', 'TEXT')
            result = extraction([request.medication])
            result.update(original_extraction_id=str(attempt['id']), user_reviewed_fields=request.medication.model_dump(mode='json'))
            correction = self.repo.record_extraction(inp['id'], 'user-form-review', 'intake-ui-v1', result)
            rows[index] = self.repo.correct_entry(prior['id'], fields(request.medication), source_extraction=correction['id'])
            self.repo.append_message(workflow['conversation_id'], 'USER', request.medication.model_dump_json(),
                {'schema': 'message.v4', 'content_refs': [], 'input_source': source + '_REVIEW'})
            ctx = deepcopy(workflow['context'])
            ctx.update(entry_version_ids=[str(row['id']) for row in rows], pending_confirmation=None,
                       active_intents=['ADD_MEDICATION'], dialogue_act='CORRECT', qa_results=[])
            return self._response(self.bot._intake_progress(workflow, ctx, rows))

    def details(self, workflow_id):
        """Owner-only UI projection, never a client-supplied identity or selection."""
        review = self.resume(workflow_id)
        workflow = self.bot.store.workflow(workflow_id)
        sources = {}
        for row in self.bot.store.entries(workflow):
            attempt = self.repo._owned('intake_extractions', row['source_extraction_id'])
            inp = self.repo._owned('intake_inputs', attempt['input_id'])
            sources[str(row['id'])] = {'input_source': inp['payload_or_locator'].get('input_source', 'TEXT'),
                                       'selected_product': manual_selection(self.repo, row)}
        messages = self.repo._all('''SELECT id,role,text_content,metadata,created_at FROM (
            SELECT id,role,text_content,metadata,created_at,sequence_no FROM msa.conversation_messages
            WHERE conversation_id=%s AND user_id=%s ORDER BY sequence_no DESC LIMIT 100
            ) m ORDER BY sequence_no''', (workflow['conversation_id'], self.repo.owner))
        for message in messages:
            source = message['metadata'].get('input_source', 'TEXT')
            if source == 'MANUAL' or source.endswith('_REVIEW'):
                message['text_content'] = 'Đã lưu thông tin người dùng xem/sửa. Xem bản nháp hiện tại bên dưới.'
            message['input_source'] = source
            message.pop('metadata')
        assessment = None
        if review.assessment_id:
            row = self.repo._owned('safety_assessments', review.assessment_id)
            findings = self.repo._all('SELECT finding_type,severity,source_severity,explanation,evidence FROM msa.safety_findings WHERE assessment_id=%s AND user_id=%s ORDER BY recorded_at,id',
                                     (row['id'], self.repo.owner))
            assessment = {'execution_status': row['execution_status'], 'check_results': row['check_results'], 'findings': findings}
        return {'review': review.model_dump(mode='json'), 'conversation_id': workflow['conversation_id'],
                'messages': messages, 'entry_sources': sources, 'assessment': assessment}

    def handoff(self, workflow_id):
        return build_handoff(self.bot.store, self.bot.store.workflow(workflow_id))

    def identify(self, workflow_id, *, dataset_build):
        return identify_confirmed(self.repo, self.handoff(workflow_id), dataset_build=dataset_build)

    def prepare_safety_snapshot(self, workflow_id, *, dataset_build):
        """Explicit server call; never triggered by an LLM intent or candidate IDs."""
        matches = self.identify(workflow_id, dataset_build=dataset_build)
        return create_safety_snapshot(self.repo, matches, data_context=self.data_context)

    def assess_snapshot(self, workflow_id, snapshot_id, dataset, *, request_key):
        handoff = self.handoff(workflow_id)  # Owner/latest/version/confirmation guards.
        return assess_confirmed_snapshot(self.repo, handoff, snapshot_id, dataset, request_key=request_key)

    def answer_assessment(self, workflow_id, assessment_id, question):
        handoff = self.handoff(workflow_id)
        return self.qa.answer(Intent.CHECK_INTERACTION,
            assessment_query(self.repo, handoff, assessment_id, question))

    def _saved_action(self, workflow, request_key=None):
        query = """SELECT metadata FROM msa.conversation_messages
            WHERE conversation_id=%s AND user_id=%s AND role='ASSISTANT'
            AND metadata->>'workflow_id'=%s AND metadata ? 'application_response'"""
        params = (workflow['conversation_id'], self.repo.owner, str(workflow['id']))
        if request_key is not None:
            query += " AND metadata->>'action_request_key'=%s"
            params += (str(request_key),)
        rows = self.repo._all(query + ' ORDER BY sequence_no DESC LIMIT 1', params)
        return rows[0]['metadata'] if rows else None

    def _retain_response(self, workflow, response, **metadata):
        # Completed Core workflows are immutable. Retain results on the existing
        # conversation, rather than changing their terminal state or revision.
        response = ApplicationResponse.model_validate_json(response.model_dump_json())
        self.repo.append_message(workflow['conversation_id'], 'ASSISTANT', response.assistant_message,
            {'schema': 'message.v4', 'content_refs': [], 'workflow_id': str(workflow['id']),
             'application_response': response.model_dump(mode='json'), **metadata})
        return response

    def _identification_blockers(self, matches):
        blockers = []
        for match, result in matches:
            if result['identification_status'] == 'VERIFIED':
                continue  # Mapping applicability requires review, not a guessed transcription correction.
            raw = result['original_medication']
            candidates = result['candidates']
            field = 'name_raw'
            for source, target in [('strength', 'strength_raw'), ('dosage_form', 'dosage_form_raw')]:
                variants = {str(c.get('product', {}).get(source)) for c in candidates}
                if len(variants) > 1 and not raw.get(target):
                    field = target
                    break
            blockers.append({'field_key': field, 'target_id': str(match['entry_version_id']),
                'question': 'Đối chiếu tên đầy đủ, hàm lượng và dạng trên nhãn/đơn; bổ sung hoặc sửa đúng thuốc, rồi xác nhận lại.',
                'attempt': 1, 'blocker_key': f"identity:{match['entry_version_id']}:{field}"})
        return blockers

    def execute(self, request: WorkflowActionRequest):
        """Explicit owner request only; models cannot call this through tool output."""
        if request.explicit_request is not True:
            raise ValueError('Explicit medication identification or assessment request required')
        with self.bot.store.turn(request.workflow_id):
            workflow = self.bot._check(request.workflow_id, request.revision)
            handoff = self.handoff(request.workflow_id)
            configuration = {'build': self.dataset_build, 'data_context': self.data_context,
                             'coverage': deepcopy(self.dataset.coverage) if request.action == 'ASSESS' and self.dataset else None}
            retained = self._saved_action(workflow, request.request_key)
            if retained:
                if retained.get('action_kind') != request.action or retained.get('action_configuration') != configuration:
                    raise ValueError('Action request key reused for different dependencies')
                return ApplicationResponse.model_validate_json(json.dumps(retained['application_response']))
            self.repo.append_message(workflow['conversation_id'], 'USER', request.action,
                {'schema': 'message.v4', 'content_refs': [], 'action_request_key': str(request.request_key)})
            response = self._response(Reply(text='', workflow_id=request.workflow_id,
                                           revision=workflow['revision'], state=workflow['state']))
            matches, answers, snapshot_id, assessment_id = [], [], None, None
            if not self.dataset_build or (request.action == 'ASSESS' and self.dataset is None):
                answers.append(self.qa.composer.compose(request.action, RetrievalResult(
                    limitations=['UNAVAILABLE: a published Core build and, for assessment, an existing Module 3 dataset are required.'])))
            else:
                matches = self.identify(request.workflow_id, dataset_build=self.dataset_build)
                answers.append(self.qa.composer.compose('Nhận diện thuốc đã xác nhận', identification_result(matches)))
                if request.action == 'ASSESS':
                    if len(matches) < 2:
                        answers.append(self.qa.composer.compose('Đánh giá tương tác', RetrievalResult(
                            limitations=['At least two non-negated confirmed medications are required; no assessment was run.'])))
                    else:
                        previous = self.repo._one('SELECT * FROM msa.safety_assessments WHERE user_id=%s AND request_key=%s',
                                                 (self.repo.owner, request.request_key))
                        snapshot_id = previous['snapshot_id'] if previous else create_safety_snapshot(
                            self.repo, matches, data_context=self.data_context)['id']
                        assessment, _ = assess_confirmed_snapshot(self.repo, handoff, snapshot_id, self.dataset,
                                                                 request_key=request.request_key)
                        assessment_id = assessment['id']
                        answers.append(self.answer_assessment(request.workflow_id, assessment_id, 'Kết quả đánh giá tương tác có nguồn là gì?'))
            response.identification_results = [{**result, 'core_match_id': str(match['id']),
                                                'core_match_status': match['match_status']} for match, result in matches]
            response.missing_blockers = self._identification_blockers(matches)
            response.qa_results = answers
            response.evidence_refs = [ref for answer in answers for ref in answer.evidence_refs]
            response.assistant_message = '\n\n'.join(a.text for a in answers)
            response.assessment_id, response.snapshot_id = assessment_id, snapshot_id
            response.executed_action = 'ASSESS' if assessment_id else 'IDENTIFY' if matches else None
            response.dialogue_act = DialogueAct.REQUEST_ACTION
            response.next_action = ('REVISE_AND_RECONFIRM' if response.missing_blockers else 'SHOW_ASSESSMENT'
                                    if assessment_id else 'SHOW_IDENTIFICATION' if matches else 'UNAVAILABLE')
            if response.missing_blockers:
                response.assistant_message += '\n' + response.missing_blockers[0]['question']
            return self._retain_response(workflow, response, action_request_key=str(request.request_key),
                                         action_kind=request.action, action_configuration=configuration)

    def _completed_turn(self, request, workflow):
        normalized = fold(request.text.strip())
        action = explicit_backend_action(request.text)
        retained = self._saved_action(workflow)
        previous = ApplicationResponse.model_validate_json(json.dumps(retained['application_response'])) if retained else None
        blockers = previous.missing_blockers if previous else []
        correction = re.match(r'(?:(?:vui long|toi muon|hay)\s+)?(?:sua|dinh chinh|thay lai)\b', normalized)
        read_intents = detect(request.text, Understanding())
        if correction or (blockers and not action and read_intents == [Intent.UNKNOWN]):
            reply = self.bot.revise(workflow['id'])
            if blockers:
                revised = self.bot.store.workflow(reply.workflow_id)
                ctx = deepcopy(revised['context'])
                ctx['pending_questions'] = blockers[:1]
                revised = self.bot._transition(revised, 'CLARIFYING', ctx)
                reply = Reply(text=reply.text, workflow_id=reply.workflow_id, revision=revised['revision'], state=revised['state'])
            return self._response(self.bot.send(reply.workflow_id, request.text, expected_revision=reply.revision))
        try:
            value = understand(self.bot.provider, request.text,
                               {'entries': [e.medication.model_dump() for e in self.handoff(workflow['id']).entries]})
        except InferenceError:
            value = None
        if action and value is not None and not value.ambiguous and not value.medications:
            intents = detect(request.text, value)
            expected = Intent.MEDICATION_QA if action == 'IDENTIFY' else Intent.CHECK_INTERACTION
            if expected in intents:
                return self.execute(WorkflowActionRequest(workflow_id=request.workflow_id, revision=request.revision,
                    request_key=uuid4(), action=action, explicit_request=True))
        response = previous or self._response(Reply(text='', workflow_id=request.workflow_id,
                                                    revision=request.revision, state=workflow['state']))
        self.handoff(workflow['id'])
        self.repo.append_message(workflow['conversation_id'], 'USER', request.text)
        if value is None or action:
            answer = self.qa.composer.compose(request.text, RetrievalResult(limitations=[
                'Request unclear or inference unavailable; use /identify or /assess for the exact confirmed list, or revise and reconfirm medication details.']))
        else:
            intents = detect(request.text, value)
            if Intent.CHECK_INTERACTION in intents and response.assessment_id:
                if value.medications:
                    answer = self.qa.composer.compose(request.text, RetrievalResult(limitations=[
                        'Use the exact confirmed list for retained safety results; different targets require revision and fresh confirmation.']))
                else:
                    answer = self.answer_assessment(workflow['id'], response.assessment_id, request.text)
            elif Intent.MEDICATION_QA in intents and response.identification_results and not value.medications:
                matches = [({'id': r['core_match_id'], 'match_status': r['core_match_status']}, r)
                           for r in response.identification_results]
                answer = self.qa.composer.compose(request.text, identification_result(matches))
            else:
                intent = next((i for i in intents if i in {Intent.APP_HELP, Intent.VIEW_MEDICATIONS}), Intent.MEDICATION_QA)
                answer = self.qa.answer(intent, RetrievalQuery(request.text, 'general'))
        response.assistant_message, response.qa_results = answer.text, [answer]
        response.evidence_refs, response.executed_action = answer.evidence_refs, None
        response.next_action = 'SHOW_ANSWER'
        return self._retain_response(workflow, response)
