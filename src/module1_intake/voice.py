"""Voice input: audio -> raw_transcript + confidence_score (chỉ STT, không bóc tách).
"""
from __future__ import annotations

import base64
import binascii
import io
import logging
import math
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger(__name__)

MAX_DURATION_S = 30.0
MAX_AUDIO_BYTES = 15 * 1024 * 1024
SAMPLE_RATE = 16000
_SILENCE_RMS = 1e-4


class VoiceInputError(Exception):
    """code: INVALID_AUDIO | AUDIO_TOO_LONG | NO_SPEECH_DETECTED | ASR_UNAVAILABLE"""

    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ASRResult:
    text: str
    confidence: float | None  # 0.0 - 1.0; None nếu engine không cung cấp


class ASREngine(Protocol):
    def transcribe(self, audio: bytes, language: str) -> ASRResult: ...


def whisper_language(language: str) -> str:
    """'vi-VN' -> 'vi'."""
    return language.split("-")[0].strip().lower()


def confidence_from_segments(segments) -> float | None:
    """exp(avg_logprob) trung bình có trọng số theo độ dài đoạn, kẹp vào [0, 1]."""
    total = weighted = 0.0
    for s in segments:
        w = max(float(s.end) - float(s.start), 1e-3)
        weighted += float(s.avg_logprob) * w
        total += w
    if total == 0:
        return None
    return round(min(1.0, max(0.0, math.exp(weighted / total))), 4)


class WhisperASR:
    """faster-whisper chạy local. Import và nạp model lười (lần gọi đầu tiên)."""

    def __init__(self, model_size: str = "small", device: str = "auto",
                 compute_type: str = "int8", max_duration_s: float = MAX_DURATION_S,
                 model=None):
        self.model_size, self.device, self.compute_type = model_size, device, compute_type
        self.max_duration_s = max_duration_s
        self._model = model

    def _get_model(self):
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError as e:
                raise VoiceInputError("ASR_UNAVAILABLE", "chưa cài faster-whisper (pip install faster-whisper)") from e
            try:
                self._model = WhisperModel(self.model_size, device=self.device, compute_type=self.compute_type)
            except Exception as e:  # lần đầu cần mạng để tải model; lỗi thiếu RAM/GPU, v.v.
                logger.exception("Không nạp được model Whisper")
                raise VoiceInputError("ASR_UNAVAILABLE", f"không nạp được model '{self.model_size}' ({type(e).__name__})") from e
        return self._model

    @staticmethod
    def _decode(audio: bytes):
        try:
            from faster_whisper.audio import decode_audio
        except ImportError as e:
            raise VoiceInputError("ASR_UNAVAILABLE", "chưa cài faster-whisper (pip install faster-whisper)") from e
        return decode_audio(io.BytesIO(audio), sampling_rate=SAMPLE_RATE)

    def transcribe(self, audio: bytes, language: str) -> ASRResult:
        try:
            samples = self._decode(audio)
        except VoiceInputError:
            raise
        except Exception as e:  # PyAV ném nhiều loại lỗi khác nhau với dữ liệu hỏng
            logger.exception("Không giải mã được âm thanh")
            raise VoiceInputError(
                "INVALID_AUDIO",
                f"không giải mã được âm thanh, cần WAV/WebM hợp lệ ({type(e).__name__}: {str(e)[:120]})",
            ) from e

        duration = len(samples) / SAMPLE_RATE
        if duration > self.max_duration_s:
            raise VoiceInputError("AUDIO_TOO_LONG", f"{duration:.1f}s > {self.max_duration_s:.0f}s")
        if duration == 0 or float((samples ** 2).mean() ** 0.5) < _SILENCE_RMS:
            raise VoiceInputError("NO_SPEECH_DETECTED", "không có tiếng nói")

        segments, _ = self._get_model().transcribe(
            samples, language=whisper_language(language), vad_filter=True,
            beam_size=5, condition_on_previous_text=False,
        )
        segs = [s for s in segments if s.text.strip()]
        text = " ".join(s.text.strip() for s in segs)
        if not text:
            raise VoiceInputError("NO_SPEECH_DETECTED", "không nhận diện được lời nói")
        return ASRResult(text=text, confidence=confidence_from_segments(segs))


def _to_bytes(audio_payload: bytes | str) -> bytes:
    if isinstance(audio_payload, str):
        data = audio_payload.strip()
        if data.startswith("data:") and "," in data:  # data URI từ trình duyệt
            data = data.split(",", 1)[1]
        try:
            audio = base64.b64decode(data, validate=True)
        except (binascii.Error, ValueError) as e:
            raise VoiceInputError("INVALID_AUDIO", "base64 không hợp lệ") from e
    elif isinstance(audio_payload, (bytes, bytearray)):
        audio = bytes(audio_payload)
    else:
        raise VoiceInputError("INVALID_AUDIO", "audio_payload phải là bytes hoặc chuỗi base64")
    if not audio:
        raise VoiceInputError("INVALID_AUDIO", "audio rỗng")
    if len(audio) > MAX_AUDIO_BYTES:
        raise VoiceInputError("INVALID_AUDIO", f"audio vượt quá {MAX_AUDIO_BYTES // (1024 * 1024)} MB")
    return audio


# core function
def transcribe_voice(audio_payload: bytes | str, language: str = "vi-VN",
                     engine: ASREngine | None = None) -> dict:
    """audio (bytes hoặc base64, <= 30s) -> {"raw_transcript": str, "confidence_score": float | None}."""
    if not isinstance(language, str) or not language.strip():
        raise VoiceInputError("INVALID_AUDIO", "language không hợp lệ")
    audio = _to_bytes(audio_payload)
    result = (engine or WhisperASR()).transcribe(audio, language)
    text = result.text.strip()
    if not text:
        raise VoiceInputError("NO_SPEECH_DETECTED", "không nhận diện được lời nói")
    return {"raw_transcript": text, "confidence_score": result.confidence}
