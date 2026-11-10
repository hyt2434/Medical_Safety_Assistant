"""Shared raw-evidence, handoff and entry-view contracts; no clinical authority."""
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


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


class Administration(StrictModel):
    timing_raw: str | None = None
    dose_raw: str | None = None
    timing_slots_raw: list[str] = Field(default_factory=list, description=(
        "Backend-derived exact source timing spans within timing_raw. For sáng và tối use [sáng, tối] "
        "while preserving timing_raw. Alternatives/ranges stay combined; never invent clock times."))


class Medication(StrictModel):
    name_raw: str | None = None
    strength_raw: str | None = None
    dosage_form_raw: str | None = None
    dose_raw: str | None = None
    route_raw: str | None = None
    frequency_raw: str | None = None
    duration_raw: str | None = Field(default=None, description=(
        "Exact explicit treatment duration in the CURRENT message, including its source prefix, "
        "e.g. trong 7 ngày. Extract it even in save requests and alongside name/form/dose/timing. "
        "Null only when no duration is stated; never infer a duration."))
    quantity_raw: str | None = None
    instructions_raw: str | None = None
    negation_raw: str | None = None
    uncertainty_raw: str | None = None
    evidence_text: str = Field(min_length=1)
    administrations: list[Administration] = Field(default_factory=list)
    uncertain_fields: list[str] = Field(default_factory=list)


class Understanding(StrictModel):
    intents: list[IntentCandidate] = Field(default_factory=list)
    medications: list[Medication] = Field(default_factory=list, max_length=32)
    ambiguous: bool = False
    dialogue_act: DialogueAct = DialogueAct.UNKNOWN


class ConfirmedEntry(StrictModel):
    entry_version_id: UUID
    content_digest: str
    medication: Medication
    identity_status: Literal["NOT_ATTEMPTED"] = "NOT_ATTEMPTED"


class Module2Handoff(StrictModel):
    conversation_id: UUID
    intake_id: UUID
    entries: list[ConfirmedEntry] = Field(min_length=1)
    requested_workflows: list[str]
    limitations: list[str] = Field(default_factory=lambda: [
        "User confirmation verifies transcription only; identity and safety are not assessed.",
        "Missing interaction coverage never establishes safety.",
    ])


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
