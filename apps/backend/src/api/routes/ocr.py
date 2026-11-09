"""Module 1 OCR endpoints."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from module1_intake.ocr.schemas import OcrResponse
from module1_intake.ocr.service import LocalOcrService, OcrError
from module1_intake.ocr.image_input import CONTENT_TYPES, DESCRIPTION

router = APIRouter(prefix="/api/v1/ocr", tags=["Module 1 - OCR"])
service = LocalOcrService()
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_CONTENT_TYPES = CONTENT_TYPES


@router.post("/extractions", response_model=OcrResponse)
def create_extraction(file: UploadFile = File(...)) -> OcrResponse:
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, f"Chỉ hỗ trợ {DESCRIPTION}")

    suffix = Path(file.filename or "upload.jpg").suffix.casefold() or ".jpg"
    with tempfile.TemporaryDirectory(prefix="msa-upload-") as temporary_directory:
        image_path = Path(temporary_directory) / f"prescription{suffix}"
        with image_path.open("wb") as destination:
            shutil.copyfileobj(file.file, destination)
        if image_path.stat().st_size > MAX_UPLOAD_BYTES:
            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Ảnh vượt quá giới hạn 10 MB")
        try:
            return service.extract(image_path)
        except OcrError as error:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error
        finally:
            file.file.close()
