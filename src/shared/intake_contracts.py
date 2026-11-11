"""Source-independent confirmed medication DTOs, re-exported by NLP for compatibility.

These are the existing NLP/Core handoff schemas, moved without schema changes.
Raw input/extractor/locator metadata belongs to Core intake records, not identity
fields. Constructing a DTO does not confirm or authorize a medication entry.
"""
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


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
