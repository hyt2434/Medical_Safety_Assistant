"""Application-level argument contracts and dialogue acts; never a DB enum or authority."""
from dataclasses import dataclass
import re

from .models import DialogueAct, Intent, Understanding
from .validation import fold, record_request_marker


@dataclass(frozen=True)
class SlotContract:
    required: tuple[str, ...] = ()
    conditional: tuple[str, ...] = ()
    optional: tuple[str, ...] = ()


CONTRACTS = {
    Intent.ADD_MEDICATION: SlotContract(('drug_evidence',), ('name_raw', 'strength_raw', 'dosage_form_raw'),
        ('dose_raw', 'administrations', 'duration_raw', 'quantity_raw', 'route_raw', 'frequency_raw')),
    Intent.CHECK_INTERACTION: SlotContract(('two_targets',), ('identity', 'confirmation', 'assessment_coverage')),
    Intent.MEDICATION_QA: SlotContract(('question_type',), ('medication_target',)),
    Intent.APP_HELP: SlotContract(),
    Intent.VIEW_MEDICATIONS: SlotContract(('trusted_owner',)),
    Intent.CREATE_REMINDER: SlotContract(('confirmed_instruction', 'module5_service'), ('safety_gate',)),
}

SLOT_QUESTIONS = {
    'name_raw': 'Tên thuốc số {number} trên nhãn hoặc đơn là gì?',
    'strength_raw': 'Hàm lượng thuốc số {number} trên nhãn hoặc đơn là bao nhiêu?',
    'dosage_form_raw': 'Dạng thuốc số {number} trên nhãn hoặc đơn là gì?',
}


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


def first_intake_blocker(rows, waived=()):
    """One conditional transcription slot at a time, scoped to an exact entry."""
    for number, row in enumerate(rows, 1):
        for field in CONTRACTS[Intent.ADD_MEDICATION].conditional:
            if not row['medication_fields'].get(field) and field not in waived:
                return field, row['id'], f"slot:{row['item_id']}:{field}", SLOT_QUESTIONS[field].format(number=number)
    return None
