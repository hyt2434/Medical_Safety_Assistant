"""API-safe contracts for literal OCR output.

These models intentionally keep the ``*_raw`` suffix. OCR is transcription,
not medical normalization, and every result must be confirmed by a user.
"""

from pydantic import BaseModel, Field


class Administration(BaseModel):
    timing_raw: str | None = None
    dose_raw: str | None = None
    phase_raw: str | None = None
    source_text: str | None = None
    issue: str | None = None


class Medication(BaseModel):
    product_raw: str | None = None
    name_raw: str | None = None
    strength_raw: str | None = None
    package_size_raw: str | None = None
    ingredient_raw: str | None = None
    dosage_form_raw: str | None = None
    dose_raw: str | None = None
    route_raw: str | None = None
    frequency_raw: str | None = None
    duration_raw: str | None = None
    quantity_raw: str | None = None
    instructions_raw: str | None = None
    schedule_requires_review: bool = True
    administrations: list[Administration] = Field(default_factory=list)
    schedule_region: dict[str, int] | None = None
    schedule_rechecks: list[dict] = Field(default_factory=list)
    evidence_text: str | None = None
    uncertain_fields: list[str] = Field(default_factory=list)


class Extraction(BaseModel):
    document_type: str = 'PRESCRIPTION'
    receipt_items: list[dict] = Field(default_factory=list)
    receipt_total_raw: str | None = None
    medications: list[Medication] = Field(default_factory=list)
    document_instructions_raw: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    requires_user_review: bool = True


