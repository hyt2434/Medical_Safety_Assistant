"""Application service for local Tesseract OCR."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import uuid
import time
from datetime import datetime, timezone
from pathlib import Path

from .parser import extract_printed_prescription
from .parser_models import Extraction
from .schemas import OcrResponse
from .mapping import build_response
from .region_retry import retry_schedules
from .receipt_retry import retry_receipt
from .image_input import SUFFIXES, DESCRIPTION, prepare_image


class OcrError(RuntimeError):
    """A safe, user-presentable OCR failure."""


class LocalOcrService:
    allowed_suffixes = SUFFIXES

    def __init__(self, timeout_seconds: int = 180) -> None:
        self.timeout_seconds = timeout_seconds
        self.script = Path(__file__).parent / "node" / "local_ocr.cjs"

    def extract(self, image_path: str | Path) -> OcrResponse:
        started_at = datetime.now(timezone.utc)
        deadline = time.monotonic() + self.timeout_seconds
        image = Path(image_path)
        if image.suffix.casefold() not in self.allowed_suffixes:
            raise OcrError(f"Chỉ hỗ trợ {DESCRIPTION}")
        if not image.is_file():
            raise OcrError("Không tìm thấy tệp ảnh")
        if shutil.which("node") is None:
            raise OcrError("Backend chưa cài Node.js để chạy Tesseract")
        dependencies = self.script.parent / "ocr" / "node_modules" / "tesseract.js"
        if not dependencies.exists():
            raise OcrError("Chưa cài thư viện OCR; chạy npm install trong thư mục node/ocr")

        with tempfile.TemporaryDirectory(prefix="msa-ocr-") as temporary_directory:
            normalized = Path(temporary_directory) / 'normalized.png'
            try:
                input_metadata = prepare_image(image, normalized)
            except ValueError as error:
                raise OcrError(str(error)) from error
            image = normalized
            evidence_path = Path(temporary_directory) / "evidence.json"
            try:
                process = subprocess.run(
                    ["node", str(self.script), str(image), str(evidence_path)],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=self.timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired as error:
                raise OcrError("OCR quá thời gian xử lý cho phép") from error
            if process.returncode != 0:
                detail = process.stderr.strip().splitlines()[-1] if process.stderr.strip() else "unknown error"
                raise OcrError(f"Tesseract không xử lý được ảnh: {detail}")
            try:
                raw = json.loads(evidence_path.read_text(encoding="utf-8"))
                raw['image_input'] = input_metadata
                extraction = Extraction.model_validate(extract_printed_prescription(raw))
            except (OSError, json.JSONDecodeError, ValueError) as error:
                raise OcrError(str(error)) from error
            retry_schedules(image, self.script, Path(temporary_directory), extraction, deadline)
            if extraction.document_type == 'PHARMACY_RECEIPT':
                retry_receipt(image, self.script, Path(temporary_directory), extraction, deadline)

        return build_response(raw, extraction, uuid.uuid4(), started_at, datetime.now(timezone.utc))
