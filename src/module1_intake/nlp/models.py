"""Shared raw-evidence, handoff and entry-view contracts; no clinical authority."""
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import Field
from shared.intake_contracts import Administration, Medication, ConfirmedEntry, Module2Handoff, StrictModel


class Intent(str, Enum):
    ADD_MEDICATION = "ADD_MEDICATION"
    CHECK_INTERACTION = "CHECK_INTERACTION"
    MEDICATION_QA = "MEDICATION_QA"
    APP_HELP = "APP_HELP"
    CREATE_REMINDER = "CREATE_REMINDER"
    VIEW_MEDICATIONS = "VIEW_MEDICATIONS"
    GENERATE_PATIENT_SUMMARY = "GENERATE_PATIENT_SUMMARY"
    UNSUPPORTED = "UNSUPPORTED"
    UNKNOWN = "UNKNOWN"


class DialogueAct(str, Enum):
    PROVIDE_INFO = "PROVIDE_INFO"
    REQUEST_ACTION = "REQUEST_ACTION"
    ASK_QUESTION = "ASK_QUESTION"
    CORRECT = "CORRECT"
    CONFIRM = "CONFIRM"
    CANCEL = "CANCEL"
    UNKNOWN = "UNKNOWN"


class IntentCandidate(StrictModel):
    intent: Intent
    evidence_text: str = Field(min_length=1)
    record_request_raw: str | None = Field(default=None, description=(
        "Exact explicit add/save request prefix, e.g. Vui lòng lưu. Null for medication reports. "
        "ADD_MEDICATION means intake candidate, never authorization to save/confirm."))


class Understanding(StrictModel):
    intents: list[IntentCandidate] = Field(default_factory=list)
    medications: list[Medication] = Field(default_factory=list, max_length=32)
    ambiguous: bool = False
    dialogue_act: DialogueAct = DialogueAct.UNKNOWN


class Reply(StrictModel):
    text: str
    workflow_id: UUID
    revision: int
    state: str
    handoff: Module2Handoff | None = None


class EntryView(StrictModel):
    entry_version_id: UUID
    item_id: UUID
    content_digest: str
    confirmed: bool
    medication: Medication
    slot_status: dict[str, str]
    identity_status: Literal['NOT_ASSESSED'] = 'NOT_ASSESSED'
