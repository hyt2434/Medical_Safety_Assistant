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

from module1_intake.ocr.parsing.dispatcher import extract_printed_prescription
from module1_intake.ocr.models.extraction import Extraction
from module1_intake.ocr.models.api import OcrResponse
from module1_intake.ocr.application.mapping import build_response
from module1_intake.ocr.rechecks.schedules import retry_schedules
from module1_intake.ocr.rechecks.receipts import retry_receipt
from module1_intake.ocr.rechecks.products import retry_products
from module1_intake.ocr.imaging.input import SUFFIXES, DESCRIPTION, prepare_image
from module1_intake.ocr.imaging.preprocessing import preprocess_document
from module1_intake.ocr.application.selection import extraction_quality, cv_selection_blockers


class OcrError(RuntimeError):
    """A safe, user-presentable OCR failure."""


class LocalOcrService:
    allowed_suffixes = SUFFIXES

    def __init__(self, timeout_seconds: int = 180) -> None:
        self.timeout_seconds = timeout_seconds
        self.script = Path(__file__).parent.parent / "node" / "local_ocr.cjs"

    def extract(self, image_path: str | Path) -> OcrResponse:
        started_at = datetime.now(timezone.utc)
        deadline = time.monotonic() + self.timeout_seconds
        run_id = uuid.uuid4()
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
            processed = Path(temporary_directory) / 'preprocessed.png'
            cv_metadata = preprocess_document(normalized, processed)
            artifact_dir = Path(__file__).resolve().parents[6] / 'data/local/module1/runs' / str(run_id)
            artifact_dir.mkdir(parents=True, exist_ok=False)
            shutil.copyfile(image, artifact_dir / ('original' + image.suffix.lower()))
            shutil.copyfile(normalized, artifact_dir / 'normalized.png')
            shutil.copyfile(processed, artifact_dir / 'preprocessed.png')
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
                raise OcrError("Tesseract không xử lý được ảnh. Hãy thử ảnh rõ hơn hoặc nhập thủ công.")
            baseline = json.loads(evidence_path.read_text(encoding='utf-8'))
            results = []
            errors = []
            for label, candidate_image, candidate_raw in [('normalized', normalized, baseline), ('preprocessed', processed, None)]:
                try:
                    if candidate_raw is None:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise ValueError('CV comparison time budget exhausted')
                        output = Path(temporary_directory) / 'cv-evidence.json'
                        proc = subprocess.run(['node', str(self.script), str(candidate_image), str(output)],
                            capture_output=True, text=True, encoding='utf-8', timeout=remaining, check=False)
                        if proc.returncode:
                            raise ValueError('CV OCR failed')
                        candidate_raw = json.loads(output.read_text(encoding='utf-8'))
                    (artifact_dir / f'{label}-ocr.json').write_text(json.dumps(candidate_raw, ensure_ascii=False), encoding='utf-8')
                    parsed = Extraction.model_validate(extract_printed_prescription(candidate_raw))
                    results.append((label, candidate_image, candidate_raw, parsed))
                except (OSError, ValueError, subprocess.TimeoutExpired) as error:
                    errors.append({'variant': label, 'error': str(error)})
            if not results:
                # OCR succeeded, but structure is unsupported or unreadable. Preserve evidence.
                results.append(('normalized', normalized, baseline, Extraction(
                    review_guidance={'action': 'REUPLOAD_OR_MANUAL_REVIEW',
                        'reason': 'STRUCTURE_NOT_RECOGNIZED',
                        'message': 'Chưa tách được danh sách thuốc. Hãy chụp gần, đủ sáng, thẳng trang và rõ chữ; hoặc kiểm tra thủ công. Chưa thể kết luận ảnh mờ hay bố cục chưa hỗ trợ.'},
                    warnings=list(dict.fromkeys(e['error'] for e in errors)))))
            # On ties keep baseline. More detected rows alone is not enough to switch:
            # differing counts or document types require review.
            chosen = results[0]
            selection_blockers = []
            if len(results) == 2:
                first, second = results
                q1, q2 = extraction_quality(first[3]), extraction_quality(second[3])
                selection_blockers = cv_selection_blockers(first[3], second[3])
                if not selection_blockers and q2[1] > q1[1]:
                    chosen = second
            label, image, raw, extraction = chosen
            if len(results) == 2:
                original_parsed, cv_parsed = results[0][3], results[1][3]
                for original_item, cv_item in zip(original_parsed.medications, cv_parsed.medications):
                    if original_item.name_raw != cv_item.name_raw:
                        extraction.warnings.append('Tên thuốc khác giữa ảnh gốc và ảnh CV; cần đối chiếu hai phiên bản trước khi xác nhận.')
                        break
            raw['image_input'] = {**input_metadata, 'selected_variant': label,
                'coordinate_space': 'preprocessed_image' if label == 'preprocessed' else 'normalized_image',
                'ocr_size': cv_metadata['output_size'] if label == 'preprocessed' else input_metadata['ocr_size']}
            raw['preprocessing'] = {**cv_metadata, 'selected_variant': label,
                'selection_policy': 'preserve_existing_fields_and_schedules_before_quality_gain',
                'selection_blockers': selection_blockers,
                'artifacts': f'data/local/module1/runs/{run_id}', 'errors': errors,
                'comparisons': [{'variant': r[0], 'quality': extraction_quality(r[3]),
                                 'parsed': r[3].model_dump()} for r in results]}
            (artifact_dir / 'preprocessing.json').write_text(json.dumps(raw['preprocessing'], ensure_ascii=False, indent=2), encoding='utf-8')
            if extraction.medications or extraction.receipt_items:
                selected_description = 'ảnh xử lý CV' if label == 'preprocessed' else 'ảnh chuẩn hóa'
                extraction.warnings.append(
                    f'Đang dùng kết quả từ {selected_description}; các trường trích xuất vẫn cần đối chiếu và xác nhận.')
            retry_schedules(image, self.script, Path(temporary_directory), extraction, deadline)
            retry_products(image, self.script, Path(temporary_directory), extraction, deadline)
            if extraction.medications and not extraction.review_guidance:
                unresolved = [i+1 for i, m in enumerate(extraction.medications)
                              if 'product_structure' in m.uncertain_fields or not m.name_raw]
                extraction.review_guidance = {
                    'action': 'REUPLOAD_OR_MANUAL_REVIEW' if len(unresolved) > len(extraction.medications)/2 else 'CONFIRM_FIELDS',
                    'unresolved_ordinals': unresolved,
                    'message': 'Đối chiếu tên, hàm lượng và liều với ảnh. Nếu chữ không rõ, tải ảnh rõ hơn; không tự chọn ứng viên OCR.'}
            if extraction.document_type == 'PHARMACY_RECEIPT':
                retry_receipt(image, self.script, Path(temporary_directory), extraction, deadline)

        return build_response(raw, extraction, run_id, started_at, datetime.now(timezone.utc))
