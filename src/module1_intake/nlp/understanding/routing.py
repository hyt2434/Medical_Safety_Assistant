"""Vietnamese routing cues never authorize sensitive actions."""
import re

from ..models import DialogueAct, Intent, IntentCandidate, Understanding
from .validation import fold, record_request_marker


CUES = {
    Intent.ADD_MEDICATION: r"\b(?:dang (?:uong|dung)|duoc ke|bac si ke|them thuoc|ghi (?:thuoc|nhan)|nhap thuoc)\b",
    Intent.CHECK_INTERACTION: r"\b(?:tuong tac|trung hoat chat|uong chung|dung chung|an toan|kiem tra (?:hai|2) thuoc)\b",
    Intent.MEDICATION_QA: r"\b(?:hoat chat|thanh phan|ham luong|dang bao che|tra cuu|nhan dien|dinh danh|xac dinh thuoc)\b",
    Intent.APP_HELP: r"\b(?:cach (?:them|nhap|xac nhan)|lam sao|huong dan su dung (?:app|ung dung)|tro giup)\b",
    Intent.CREATE_REMINDER: r"\b(?:nhac (?:toi|uong)|nhac nho)\b",
    Intent.VIEW_MEDICATIONS: r"\b(?:(?:xem|danh sach) thuoc|(?:xem )?lich su (?:dung )?thuoc)\b",
    Intent.GENERATE_PATIENT_SUMMARY: r"\b(?:tom tat|gui bac si)\b",
    Intent.UNSUPPORTED: r"\b(?:trieu chung|chan doan|dau dau|sot|cap cuu|so cuu|het han|so sanh don|ngung thuoc|doi lieu|ke don)\b",
}
WORKFLOWS = {Intent.ADD_MEDICATION: "MEDICATION_INTAKE", Intent.CHECK_INTERACTION: "SAFETY_REQUEST",
             Intent.MEDICATION_QA: "Q_AND_A", Intent.APP_HELP: "Q_AND_A"}


def detect(text: str, understanding: Understanding) -> list[Intent]:
    result = [intent for intent, cue in CUES.items() if re.search(cue, fold(text))]
    if record_request_marker(text) and Intent.ADD_MEDICATION not in result:
        result.append(Intent.ADD_MEDICATION)
    if (Intent.APP_HELP in result and Intent.ADD_MEDICATION in result and
            not re.search(r"\b(?:dang (?:uong|dung)|duoc ke|bac si ke|ghi (?:thuoc|nhan))\b", fold(text)) and
            not record_request_marker(text)):
        result.remove(Intent.ADD_MEDICATION)
    for candidate in understanding.intents:
        if candidate.intent not in result:
            result.append(candidate.intent)
    if understanding.medications and not result:
        result.append(Intent.ADD_MEDICATION)
    return [i for i in result if i != Intent.UNKNOWN] or [Intent.UNKNOWN]


def complete_intents(text: str, understanding: Understanding) -> Understanding:
    """Expose the same grounded intake/routing semantics to CLI and chatbot.

    Call only after schema/source validation. ADD_MEDICATION covers reported or
    prescribed medication data as well as explicit record requests. The latter
    get a source-backed prefix; neither is authorization to persist or confirm.
    """
    marker = record_request_marker(text)
    existing = {candidate.intent: candidate for candidate in understanding.intents}
    candidates = []
    for intent in detect(text, understanding):
        if intent == Intent.UNKNOWN:
            continue
        candidate = existing.get(intent) or IntentCandidate(intent=intent, evidence_text=text)
        if intent == Intent.ADD_MEDICATION:
            candidate = candidate.model_copy(update={
                "record_request_raw": marker,
                "evidence_text": text if marker else candidate.evidence_text,
            })
        candidates.append(candidate)
    result = understanding.model_copy(update={"intents": candidates})
    return result.model_copy(update={"dialogue_act": dialogue_act(text, result)})


def clarification_required(intents: list[Intent], understanding: Understanding) -> bool:
    return understanding.ambiguous or intents == [Intent.UNKNOWN]


def requested_workflows(intents: list[Intent]) -> list[str]:
    return [name for name in ("MEDICATION_INTAKE", "SAFETY_REQUEST", "Q_AND_A")
            if name in {WORKFLOWS.get(i) for i in intents}]


def explicit_backend_action(text: str) -> str | None:
    """Bounded user request for the confirmed list; an LLM intent is not authority.

    Questions, negations, embedded commands and separately named drug targets do
    not authorize execution. Other wordings can use the explicit action DTO/CLI.
    """
    value = fold(text.strip().rstrip('.!?'))
    prefix = r'(?:(?:vui long|hay|toi muon|yeu cau|xin)\s+)?'
    target = r'(?:\s+(?:cac thuoc|thuoc|danh sach thuoc|danh sach)(?:\s+(?:nay|da xac nhan))?)?'
    if re.fullmatch(prefix + r'(?:nhan dien|dinh danh|xac dinh thuoc)' + target, value):
        return 'IDENTIFY'
    if re.fullmatch(prefix + r'(?:kiem tra tuong tac|danh gia tuong tac|danh gia an toan)' + target, value):
        return 'ASSESS'
    return None


def dialogue_act(text: str, value: Understanding) -> DialogueAct:
    normalized = fold(text.strip().rstrip('.!'))
    intents = {item.intent for item in value.intents}
    if normalized in {'xac nhan', 'toi xac nhan'}:
        return DialogueAct.CONFIRM
    if normalized in {'huy', 'huy yeu cau'}:
        return DialogueAct.CANCEL
    if re.search(r'\b(?:sua|dinh chinh|thay lai)\b', normalized):
        return DialogueAct.CORRECT
    if record_request_marker(text):
        return DialogueAct.REQUEST_ACTION
    if intents & {Intent.MEDICATION_QA, Intent.APP_HELP, Intent.CHECK_INTERACTION}:
        return DialogueAct.ASK_QUESTION
    if intents & {Intent.CREATE_REMINDER, Intent.VIEW_MEDICATIONS, Intent.GENERATE_PATIENT_SUMMARY}:
        return DialogueAct.REQUEST_ACTION
    return DialogueAct.PROVIDE_INFO if value.medications else DialogueAct.UNKNOWN
