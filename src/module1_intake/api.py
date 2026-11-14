"""2 hàm public của Module I (Manual Input + Voice Input).

Cấu hình qua biến môi trường:
  MEDICATION_DATA_DIR   thư mục chứa các file CSV (mặc định: ./data)
  WHISPER_MODEL_SIZE    tiny | base | small | medium ... (mặc định: small)
"""
from __future__ import annotations

import os
import threading

from .dictionary import load_dictionary
from .suggest import MedicationSuggester
from .voice import ASREngine, WhisperASR, transcribe_voice as _transcribe_voice

_lock = threading.Lock()
_suggester: MedicationSuggester | None = None
_asr: ASREngine | None = None


def init_suggester(data_dir: str | None = None) -> None:
    """Nạp từ điển + dựng index. Gọi lúc khởi động để lần gõ đầu tiên không bị trễ."""
    global _suggester
    with _lock:
        _suggester = MedicationSuggester(
            load_dictionary(data_dir or os.environ.get("MEDICATION_DATA_DIR", "data"))
        )


def set_asr_engine(engine: ASREngine | None) -> None:
    """Thay engine STT (ví dụ engine khác Whisper, hoặc FakeASR khi test)."""
    global _asr
    _asr = engine


def suggest_medication_names(query: str, limit: int = 5) -> list[dict]:
    """Autocomplete tên thuốc. Trả về tối đa `limit` gợi ý, mỗi gợi ý là dict:
    brand_name, active_ingredient (list | None), strength, dosage_form, match_type, medication_id.
    Chỉ là gợi ý nhập liệu, không tự xác nhận thuốc.
    """
    if _suggester is None:
        init_suggester()
    return [s.to_dict() for s in _suggester.suggest(query, limit)]  # type: ignore[union-attr]


def transcribe_voice(audio_payload: bytes | str, language: str = "vi-VN") -> dict:
    """audio -> {"raw_transcript": str, "confidence_score": float | None}.
    Ném VoiceInputError (code: INVALID_AUDIO, AUDIO_TOO_LONG, NO_SPEECH_DETECTED, ASR_UNAVAILABLE).
    """
    global _asr
    if _asr is None:
        _asr = WhisperASR(model_size=os.environ.get("WHISPER_MODEL_SIZE", "small"))
    return _transcribe_voice(audio_payload, language, engine=_asr)
