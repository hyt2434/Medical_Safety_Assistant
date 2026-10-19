"""Existing Module 1 extraction contract; no new NLP/Voice behavior."""
from pydantic import BaseModel, Field

class Administration(BaseModel):
    timing_raw: str | None = Field(description="Literal timing span, e.g. Sáng, or null")
    dose_raw: str | None = Field(description="Literal dose paired with this timing, or null")


class Medication(BaseModel):
    name_raw: str | None = Field(description="Medication name exactly as printed, or null")
    strength_raw: str | None = Field(description="Strength, e.g. '500 mg', exactly as printed, or null")
    dose_raw: str | None = Field(description="Dose per administration as printed, or null")
    route_raw: str | None = Field(description="Administration route as printed, or null")
    frequency_raw: str | None = Field(description="Frequency/timing as printed, or null")
    duration_raw: str | None = Field(description="Duration as printed, or null")
    quantity_raw: str | None = Field(description="Dispensed quantity and unit as printed, excluding the SL heading, or null")
    instructions_raw: str | None = Field(description="Complete literal medication instruction line(s), including Ghi chú when printed, or null")
    administrations: list[Administration] = Field(description="Timing/dose pairs transcribed from each explicit schedule; empty if not printed")
    evidence_text: str | None = Field(description="Short literal quotation supporting this entry, or null")
    uncertain_fields: list[str] = Field(description="Names of fields that are ambiguous or unreadable")


class Extraction(BaseModel):
    medications: list[Medication]
    document_instructions_raw: list[str] = Field(description="Literal document-level advice/return-visit instructions, excluding empty headings, dates and identifiers")
    warnings: list[str] = Field(description="Any unreadable, ambiguous, or conflicting information")
    requires_user_review: bool = Field(description="Always true: patient must verify before downstream use")


