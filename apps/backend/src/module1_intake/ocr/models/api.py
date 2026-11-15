"""Draft Module 1 records matching the 35-table ERD.
Context IDs remain null until authentication/intake/persistence supplies them.
Status defaults are application choices; the ERD does not enumerate values.
"""
from datetime import date, datetime
from typing import Any
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class ErdRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MedicationIntake(ErdRecord):
    intake_id: UUID | None = None
    patient_user_id: UUID | None = None
    submitted_by_user_id: UUID | None = None
    input_method: str = "OCR"
    raw_text: str | None = None
    document_manifest: dict[str, Any] = Field(default_factory=dict)
    source_filename: str | None = None
    storage_uri: str | None = None
    checksum_sha256: str | None = None
    mime_type: str | None = None
    status: str = "PENDING"
    submitted_at: datetime | None = None
    updated_at: datetime | None = None


class ExtractionRun(ErdRecord):
    extraction_run_id: UUID
    intake_id: UUID | None = None
    created_by_user_id: UUID | None = None
    engine_name: str
    engine_version: str | None = None
    input_manifest: dict[str, Any] = Field(default_factory=dict)
    status: str = "COMPLETED"
    raw_output: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime | None = None


class MedicationEntry(ErdRecord):
    entry_id: UUID | None = None
    intake_id: UUID | None = None
    patient_user_id: UUID | None = None
    extraction_run_id: UUID | None = None
    prescription_group_id: UUID | None = None
    ordinal: int = Field(ge=1)
    raw_text: str | None = None
    extracted_name: str | None = None
    extracted_strength: str | None = None
    extracted_form: str | None = None
    extracted_route: str | None = None
    dosage_instructions: str | None = None
    prescription_number: str | None = None
    prescriber_name: str | None = None
    prescription_date: date | None = None
    confirmation_status: str = "PENDING"
    confirmed_data: dict[str, Any] | None = None
    confirmed_by_user_id: UUID | None = None
    confirmed_at: datetime | None = None
    status: str = "DRAFT"
    created_at: datetime | None = None
    updated_at: datetime | None = None


class OcrResponse(BaseModel):
    """API envelope containing draft ERD records, not a database transaction."""
    extraction_run: ExtractionRun
    medication_entries: list[MedicationEntry]
