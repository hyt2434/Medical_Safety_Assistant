"""Deterministic dialogue with immutable Core versions and exact displayed review."""
from copy import deepcopy
import json
import re
from uuid import UUID, uuid5

from .handoff import build_handoff
from .fsm import check_transition
from .models import DialogueAct, Intent, Medication, Reply, Understanding
from .persistence import CoreStore, Repository, medication
from .providers import InferenceError, Provider, understand
from .qa import APP_HELP, DEFERRED, SAFETY, Reference, reference_answer
from .routing import clarification_required, detect, requested_workflows
from .validation import fold
from .policy import dialogue_act, first_intake_blocker
from .hybrid_qa import HybridQA, question_kind
from .retrieval import CoreReferenceRetriever, RetrievalQuery


TERMINAL = {"COMPLETED", "CANCELLED", "FAILED"}
CONFIRM = {"xac nhan", "toi xac nhan"}
UNKNOWN_FIELDS = {"khong ro", "khong biet", "khong nho"}


class Chatbot:
    """Use a trusted server-owned repository/connection per request, never an LLM owner."""
    def __init__(self, repo: Repository, provider: Provider, *, reference: Reference | None = None, qa: HybridQA | None = None):
        self.store, self.repo, self.provider, self.reference = CoreStore(repo), repo, provider, reference
        self.qa = qa or HybridQA(medication=CoreReferenceRetriever(reference) if reference else None)

    def start(self, *, conversation_id=None, task=Intent.ADD_MEDICATION) -> Reply:
        if task not in (None, Intent.ADD_MEDICATION):
            raise ValueError('Start generic dialogue or an explicitly selected medication intake; other tasks are selected by a turn')
        chat = self.repo._owned("conversation_sessions", conversation_id) if conversation_id else self.repo.create_conversation()
        intake = self.repo.create_intake(chat["id"])
        workflow = self.repo.create_workflow(chat["id"], "MEDICATION_INTAKE", intake=intake["id"])
        if task is None:
            ctx = deepcopy(workflow['context'])
            ctx['awaiting_purpose'] = True
            workflow = self._transition(workflow, 'COLLECTING', ctx)
        return self._reply(workflow, "Bạn muốn nhập thuốc, tra cứu tham chiếu hay hỏi cách sử dụng?", transition=False)

    def _check(self, identity, revision: int) -> dict:
        workflow = self.store.workflow(identity)
        if workflow["revision"] != revision:
            raise ValueError("Stale workflow revision; reload current review")
        return workflow

    def _transition(self, workflow: dict, state: str, context: dict) -> dict:
        check_transition(workflow["state"], state)
        return self.repo.transition_workflow(workflow["id"], state,
                    expected_revision=workflow["revision"], context=context)

    def _reply(self, workflow: dict, text: str, *, state=None, context=None, transition=True) -> Reply:
        self.repo.append_message(workflow["conversation_id"], "ASSISTANT", text)
        if transition:
            ctx = deepcopy(context if context is not None else workflow['context'])
            ctx['assistant_message'] = text
            workflow = self._transition(workflow, state or workflow["state"], ctx)
        return Reply(text=text, workflow_id=UUID(str(workflow["id"])), revision=workflow["revision"], state=workflow["state"])

    def _questions(self, workflow: dict, text: str, *, context=None, field_key='clarification', target_id=None, blocker_key=None) -> Reply:
        ctx = deepcopy(context if context is not None else workflow["context"])
        key = blocker_key or field_key
        history = ctx.setdefault('question_attempts', {})
        count = history.get(key, 0) + 1
        history[key] = min(count, 3)
        if count > 3:  # Initial question, then at most two retries for this blocker.
            ctx['pending_questions'] = []
            ctx['pending_confirmation'] = None
            ctx['exhausted_blocker'] = key
            if field_key in {'name_raw', 'strength_raw', 'dosage_form_raw'} and ctx.get('entry_version_ids'):
                ctx['allow_missing'] = True
                return self._display(workflow, ctx)
            ctx['next_action'] = 'DEFERRED'
            return self._reply(workflow, 'Chưa giải quyết được thông tin đang thiếu. Giữ trạng thái chưa rõ; bạn có thể nhập thủ công hoặc chọn tác vụ khác.',
                               state='CLARIFYING', context=ctx)
        question = {"field_key": field_key, "question": text, 'attempt': count, 'blocker_key': key}
        if target_id is not None:
            question['target_id'] = str(target_id)
        ctx["pending_questions"] = [question]
        ctx["pending_confirmation"] = None
        ctx['next_action'] = 'ASK_CLARIFICATION'
        if workflow['state'] == 'AWAITING_CONFIRMATION' and field_key in {'interaction_target', 'medication_target'}:
            return self._display(workflow, ctx, question=text)
        return self._reply(workflow, text, state="CLARIFYING", context=ctx)

    def _display(self, workflow: dict, context: dict, *, question=None) -> Reply:
        rows = [self.repo._owned("medication_entry_versions", i) for i in context["entry_version_ids"]]
        rendered = [f"{n}. " + json.dumps(row["medication_fields"], ensure_ascii=False, sort_keys=True)
                    for n, row in enumerate(rows, 1)]
        text = "\n".join(rendered) + ("\nMục null là chưa rõ; tên thuốc chưa được xác minh. "
               "Kiểm tra từng mục, gõ 'xác nhận' để xác nhận đúng bản này, "
               "hoặc 'sửa thuốc 1 ...' để sửa. Đây không phải xác nhận an toàn.")
        if question:
            text += '\n' + question
        display = self.repo.append_message(workflow["conversation_id"], "ASSISTANT", text)
        revision = workflow["revision"] + 1
        entries = [{"id": str(r["id"]), "content_digest": r["content_digest"]} for r in rows]
        ctx = deepcopy(context)
        if not question:
            ctx["pending_questions"] = []
        ctx['next_action'] = 'ASK_CLARIFICATION' if question else 'SHOW_REVIEW'
        ctx['assistant_message'] = text
        ctx["draft"] = {"draft_revision": revision, "display_message_id": str(display["id"]), "entries": entries}
        ctx["pending_confirmation"] = {"draft_revision": revision, "display_message_id": str(display["id"]),
            "payload_digest": self.repo.digest(entries), "entry_version_ids": [r["id"] for r in entries]}
        workflow = self._transition(workflow, "AWAITING_CONFIRMATION", ctx)
        return Reply(text=text, workflow_id=UUID(str(workflow["id"])), revision=workflow["revision"], state=workflow["state"])

    def _intake_progress(self, workflow, ctx, rows):
        if ctx.get('awaiting_purpose'):
            return self._questions(workflow, 'Bạn muốn lưu thông tin thuốc này, kiểm tra tương tác, hay hỏi thông tin?',
                                   context=ctx, field_key='purpose')
        blocker = first_intake_blocker(rows)
        if blocker and not ctx.get('allow_missing'):
            field, target, key, question = blocker
            return self._questions(workflow, question + " Gõ 'không rõ' nếu chưa biết.", context=ctx,
                                   field_key=field, target_id=target, blocker_key=key)
        return self._display(workflow, ctx)

    def _targets(self, text: str, meds: list[Medication], rows: list[dict], *, pending_target=None) -> dict[int, Medication]:
        explicit = re.search(r"\bthuoc\s+(\d+)\b", fold(text))
        correcting = re.search(r"\b(?:sua|dinh chinh|thay lai)\b", fold(text)) is not None
        updates = {}
        for med in meds:
            named = [i for i, row in enumerate(rows) if med.name_raw and
                     fold(med.name_raw) == fold(row["medication_fields"].get("name_raw") or "")]
            if explicit:
                if len(meds) != 1 or not 1 <= int(explicit.group(1)) <= len(rows):
                    raise ValueError("Ambiguous correction target")
                index = int(explicit.group(1)) - 1
            elif pending_target and not correcting and not med.name_raw and len(meds) == 1:
                matches = [i for i, row in enumerate(rows) if str(row['id']) == str(pending_target)]
                if len(matches) != 1:
                    raise ValueError('Pending question target changed')
                index = matches[0]
            elif len(named) == 1 and re.search(r"\bthem thuoc\b", fold(text)):
                continue  # Explicitly adding another strength/form is not a correction.
            elif len(named) == 1:
                index = named[0]
            elif len(named) > 1 and not re.search(r"\bthem thuoc\b", fold(text)):
                raise ValueError("Repeated name requires an explicit medication number")
            elif rows and (not med.name_raw or correcting):
                if len(rows) != 1 or len(meds) != 1:
                    raise ValueError("Specify medication number for this correction")
                index = 0
            else:
                continue
            if index in updates:
                raise ValueError("Multiple corrections target one medication")
            updates[index] = med
        return updates

    def send(self, identity, text: str, *, expected_revision: int) -> Reply:
        if not text.strip() or len(text) > 12000:
            raise ValueError("Message must contain 1–12000 characters")
        if fold(text.strip().rstrip(".!")) in CONFIRM:
            return self.confirm(identity, expected_revision=expected_revision,
                                request_key=uuid5(UUID(str(identity)), f"confirm:{expected_revision}"),
                                explicit_confirmation=True)
        with self.store.turn(identity):
            workflow = self._check(identity, expected_revision)
            if workflow["state"] in TERMINAL:
                raise ValueError("Terminal workflow; start a new intake or call revise()")
            message = self.repo.append_message(workflow["conversation_id"], "USER", text)
            if fold(text.strip()) in {"huy", "huy yeu cau"}:
                cancel_ctx = deepcopy(workflow['context'])
                cancel_ctx.update(dialogue_act='CANCEL', next_action='DEFERRED', pending_questions=[])
                return self._reply(workflow, "Đã hủy yêu cầu; lịch sử được giữ lại.", state="CANCELLED", context=cancel_ctx)
            rows = self.store.entries(workflow)
            ctx = deepcopy(workflow["context"])
            ctx['qa_results'] = []
            pending = ctx.get('pending_questions', [])
            if fold(text.strip()) in UNKNOWN_FIELDS and pending and pending[0]['field_key'] in {'purpose','interaction_target','medication_target'}:
                ctx['pending_questions'] = []
                ctx['next_action'] = 'UNAVAILABLE'
                return self._reply(workflow, 'Giữ thông tin là chưa rõ. Chưa thực hiện tác vụ; bạn có thể chọn yêu cầu khác hoặc nhập thủ công.', context=ctx)
            if rows and fold(text.strip()) in UNKNOWN_FIELDS:
                ctx["allow_missing"] = True
                return self._display(workflow, ctx)
            try:
                # Basic application help remains available even when Ollama is down.
                value = Understanding() if detect(text, Understanding()) == [Intent.APP_HELP] else understand(
                    self.provider, text, {"entries": [medication(r).model_dump() for r in rows] or ctx.get('qa_targets', []),
                                          'pending_question': pending[:1]})
            except InferenceError as error:
                inp = self.repo.record_input(workflow["intake_session_id"], "TEXT", text.encode("utf-8"),
                    payload={"schema": "input.v4", "digest_basis": "ORIGINAL_BYTES", "text": text}, message=message["id"])
                self.repo.record_extraction(inp["id"], self.provider.name, "nlp-mvp-v1",
                    {"schema": "extraction.v4", "medications": [], "warnings": ["Inference rejected"], "document_instructions_raw": []},
                    status="FAILED", errors={"schema": "error.v4", "code": "UNTRUSTED_INFERENCE",
                                             "message": "Extraction unavailable or rejected by validation", "details": {'category': error.category.value}})
                ctx['error_code'] = error.category.value
                return self._questions(workflow, "Chưa trích xuất tin cậy. Nhập lại tên thuốc và nội dung trên nhãn/đơn, hoặc dùng nhập thủ công.", context=ctx, field_key='inference')
            intents = detect(text, value)
            ctx.pop('error_code', None)
            ctx.pop('exhausted_blocker', None)
            if pending and pending[0]['field_key'] in {'interaction_target', 'medication_target'} and not any(
                    c.record_request_raw for c in value.intents):
                target_intent = Intent.CHECK_INTERACTION if pending[0]['field_key'] == 'interaction_target' else Intent.MEDICATION_QA
                if intents == [Intent.ADD_MEDICATION]:
                    intents = [target_intent]
            if rows and value.medications and (re.search(r"\b(?:sua|dinh chinh)\b", fold(text)) or
                    (all(m.name_raw is None for m in value.medications) and not (pending and pending[0]['field_key'] in {'interaction_target','medication_target'}))):
                intents = [i for i in intents if i != Intent.MEDICATION_QA]
                if Intent.ADD_MEDICATION not in intents:
                    intents.append(Intent.ADD_MEDICATION)
            ctx['dialogue_act'] = dialogue_act(text, value).value
            ctx['active_intents'] = [i.value for i in intents]
            if any(c.record_request_raw for c in value.intents):
                ctx['awaiting_purpose'] = False
            routes = requested_workflows(intents)
            ctx["requested_workflows"] = list(dict.fromkeys(ctx.get("requested_workflows", []) + routes))
            self.repo.append_message(workflow["conversation_id"], "SYSTEM", "NLP routing",
                {"schema": "message.v4", "content_refs": [], "intent_candidates": [i.value for i in intents]})
            # Read-only side questions preserve the pending intake review unchanged.
            side = []
            qa_intents = [i for i in intents if i != Intent.ADD_MEDICATION and i != Intent.UNKNOWN]
            targets = [m.model_dump(mode='json') for m in value.medications]
            selector = re.search(r'\bthuoc\s+(\d+)\b', fold(text))
            if Intent.MEDICATION_QA in qa_intents and selector and 1 <= int(selector.group(1)) <= len(rows):
                targets = [medication(rows[int(selector.group(1)) - 1]).model_dump(mode='json')]
            if pending and pending[0]['field_key'] == 'interaction_target':
                targets = ctx.get('qa_targets', []) + targets
            if not targets:
                targets = [medication(r).model_dump(mode='json') for r in rows if not medication(r).negation_raw]
                if Intent.CHECK_INTERACTION in qa_intents and not targets:
                    targets = ctx.get('qa_targets', [])
            # QA targets are retained in Core workflow context, not added to a personal list.
            if Intent.CHECK_INTERACTION in qa_intents and len(targets) < 2:
                if Intent.ADD_MEDICATION in intents and value.medications:
                    try:
                        updates = self._targets(text, value.medications, rows)
                    except ValueError:
                        return self._questions(workflow, 'Bạn muốn sửa thuốc số mấy?', context=ctx, field_key='target_entry')
                    saved = self.store.save(workflow, text, message, value.medications, updates, self.provider.name)
                    ctx['entry_version_ids'] = [str(row['id']) for row in saved]
                    ctx['resume_intake_after_qa'] = True
                ctx['qa_targets'] = targets
                ctx['qa_question'], ctx['qa_kind'] = text, question_kind(text)
                return self._questions(workflow, 'Bạn muốn kiểm tra tương tác với thuốc nào khác?' if targets else
                    'Bạn muốn kiểm tra tương tác giữa những thuốc nào?', context=ctx, field_key='interaction_target')
            if Intent.MEDICATION_QA in qa_intents and len(targets) != 1:
                ctx['qa_question'], ctx['qa_kind'] = text, question_kind(text)
                return self._questions(workflow, 'Bạn muốn hỏi thông tin về thuốc nào?', context=ctx, field_key='medication_target')
            if qa_intents:
                if pending and pending[0]['field_key'] in {'interaction_target','medication_target'}:
                    ctx['pending_questions'] = []
                if Intent.CHECK_INTERACTION in qa_intents:
                    ctx['qa_targets'] = targets
            for intent in qa_intents:
                following_qa = pending and pending[0]['field_key'] in {'interaction_target','medication_target'}
                answer = self.qa.answer(intent, RetrievalQuery(question=ctx.get('qa_question', text) if following_qa else text,
                    kind=ctx.get('qa_kind', question_kind(text)) if following_qa else question_kind(text),
                    medication=targets[0] if len(targets) == 1 else {},
                    entry_ids=tuple(UUID(str(r['id'])) for r in rows),
                    assessment_id=UUID(ctx['assessment_id']) if ctx.get('assessment_id') else None))
                ctx['qa_results'].append(answer.model_dump(mode='json'))
                side.append(answer.text)
                ctx['next_action'] = ('SHOW_CANDIDATES' if answer.candidates else 'SHOW_ANSWER' if answer.status in {'WORKING','PARTIAL'}
                                      else answer.status)
            if side:
                # Side workflows use only existing enum values; no unsupported action is run.
                side_type = "SAFETY_REQUEST" if Intent.CHECK_INTERACTION in intents else "Q_AND_A"
                side_w = self.repo.create_workflow(workflow["conversation_id"], side_type,
                    intake=workflow["intake_session_id"], origin_message=message["id"])
                self._transition(side_w, "SUSPENDED",
                    {"schema": "workflow.v4", "pending_questions": [], "draft": None,
                     "pending_confirmation": None, "disposition": "READ_ONLY_OR_DEFERRED", "intents": [i.value for i in intents]})
                if Intent.ADD_MEDICATION not in intents:
                    if ctx.pop('resume_intake_after_qa', False) and rows:
                        return self._intake_progress(workflow, ctx, rows)
                    if workflow["state"] == "AWAITING_CONFIRMATION":
                        self.repo.append_message(workflow["conversation_id"], "ASSISTANT", "\n".join(side))
                        return self._display(workflow, ctx)
                    return self._reply(workflow, "\n".join(side), context=ctx)
                self.repo.append_message(workflow["conversation_id"], "ASSISTANT", "\n".join(side))
            if clarification_required(intents, value):
                return self._questions(workflow, "Bạn muốn nhập thuốc, tra cứu hay yêu cầu kiểm tra tương tác? Hãy nói rõ yêu cầu.", context=ctx, field_key='task_intent')
            if not value.medications:
                if rows and any(candidate.record_request_raw for candidate in value.intents):
                    return self._intake_progress(workflow, ctx, rows)
                return self._questions(workflow, "Hãy cung cấp tên thuốc và nội dung trên nhãn/đơn. Chưa có dữ liệu để xác nhận.", context=ctx)
            try:
                pending_target = (pending[0].get('target_id') if pending and pending[0]['field_key'] in
                                  {'name_raw','strength_raw','dosage_form_raw'} else None)
                updates = self._targets(text, value.medications, rows, pending_target=pending_target)
            except ValueError:
                return self._questions(workflow, "Bạn muốn sửa thuốc số mấy? Gửi lại 'sửa thuốc 1 ...' với thông tin cần sửa.", context=ctx, field_key='target_entry')
            saved = self.store.save(workflow, text, message, value.medications, updates, self.provider.name)
            ctx["entry_version_ids"] = [str(r["id"]) for r in saved]
            ctx["pending_confirmation"] = None
            return self._intake_progress(workflow, ctx, saved)

    def confirm(self, identity, *, expected_revision: int, request_key: UUID,
                explicit_confirmation: bool) -> Reply:
        if explicit_confirmation is not True:
            raise ValueError("Explicit authenticated-owner confirmation required")
        with self.store.turn(identity):
            workflow = self.store.workflow(identity)
            if workflow["state"] == "COMPLETED" and workflow["context"].get("confirmation_request_key") == str(request_key):
                return Reply(text="Đã xác nhận nội dung; chưa đánh giá an toàn.", workflow_id=UUID(str(identity)),
                    revision=workflow["revision"], state=workflow["state"], handoff=build_handoff(self.store, workflow))
            workflow = self._check(identity, expected_revision)
            ctx = deepcopy(workflow["context"])
            pending, draft = ctx.get("pending_confirmation"), ctx.get("draft")
            if workflow["state"] != "AWAITING_CONFIRMATION" or not pending or not draft:
                raise ValueError("Display a review before confirming")
            rows = self.store.entries(workflow)
            actual = [{"id": str(r["id"]), "content_digest": r["content_digest"]} for r in rows]
            if (actual != draft["entries"] or self.repo.digest(actual) != pending["payload_digest"] or
                    pending["draft_revision"] != expected_revision):
                raise ValueError("Displayed confirmation is stale")
            for row in rows:
                self.store.assert_latest(row)
            self.repo.append_message(workflow["conversation_id"], "USER", "xác nhận",
                {"schema": "message.v4", "content_refs": [], "confirmation_request_key": str(request_key)})
            for row in rows:
                if row["confirmed_at"] is not None:
                    # An unchanged item in a revised multi-drug workflow keeps its
                    # immutable earlier confirmation; Core forbids confirming it again.
                    continue
                # Stable per-entry keys allow retry after a partially completed Core operation.
                self.repo.confirm_entry(row["id"], row["content_digest"],
                    uuid5(UUID(str(identity)), "entry:" + str(row["id"])), explicit_confirmation=True)
            ctx["confirmation_request_key"] = str(request_key)
            ctx['next_action'] = 'SHOW_ANSWER'
            ctx['dialogue_act'] = DialogueAct.CONFIRM.value
            workflow = self._transition(workflow, "COMPLETED", ctx)
            result = self._reply(workflow, "Đã xác nhận nội dung để chuyển Module 2. Chưa xác minh danh tính thuốc hoặc đánh giá tương tác.", transition=False)
            return result.model_copy(update={"handoff": build_handoff(self.store, workflow)})

    def revise(self, identity) -> Reply:
        """Start a fresh workflow over the same items; future changes append versions."""
        with self.store.turn(identity):
            old = self.store.workflow(identity)
            if old["state"] != "COMPLETED":
                raise ValueError("revise() requires a completed intake")
            workflow = self.repo.create_workflow(old["conversation_id"], "MEDICATION_INTAKE", intake=old["intake_session_id"])
            ctx = deepcopy(old["context"])
            ctx.update(draft=None, pending_confirmation=None)
            ctx.pop("confirmation_request_key", None)
            return self._reply(workflow, "Nhập 'sửa thuốc 1 ...'. Bản đã xác nhận được giữ nguyên trong lịch sử.", context=ctx)
