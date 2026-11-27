"""Map parser output into ERD drafts without inventing patient identity."""
from datetime import datetime
from uuid import UUID
from module1_intake.ocr.models.extraction import Extraction
from module1_intake.ocr.models.api import ExtractionRun, MedicationEntry, OcrResponse


def build_response(raw: dict, extraction: Extraction, run_id: UUID,
                   started_at: datetime, completed_at: datetime) -> OcrResponse:
    entries = [MedicationEntry(
        extraction_run_id=run_id, ordinal=ordinal,
        raw_text=item.evidence_text or item.product_raw,
        extracted_name=None if 'product_structure' in item.uncertain_fields else item.name_raw,
        extracted_strength=item.strength_raw,
        extracted_form=item.dosage_form_raw,
        extracted_route=item.route_raw,
        dosage_instructions=item.instructions_raw,
    ) for ordinal, item in enumerate(extraction.medications, 1)]
    return OcrResponse(
        extraction_run=ExtractionRun(
            extraction_run_id=run_id,
            engine_name=raw.get('provider', 'Tesseract.js'),
            engine_version=raw.get('version'),
            started_at=started_at, completed_at=completed_at, created_at=started_at,
            raw_output={'ocr': raw, 'parsed': extraction.model_dump()},
        ), medication_entries=entries,
    )
