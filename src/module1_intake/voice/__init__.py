"""Voice input: decode audio and return an editable raw transcript."""

from .asr import (
    ASREngine, ASRResult, VoiceInputError, WhisperASR,
    confidence_from_segments, transcribe_voice, whisper_language,
)

__all__ = [
    'ASREngine', 'ASRResult', 'VoiceInputError', 'WhisperASR',
    'confidence_from_segments', 'transcribe_voice', 'whisper_language',
]
