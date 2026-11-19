"""Opt-in real Whisper speech transcription through the common Module 1 API.

This smoke test verifies actual inference, not word-error-rate or clinical accuracy.
"""
import base64
import os
from pathlib import Path

import pytest

from module1_intake import api
from module1_intake.voice import WhisperASR


ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.skipif(os.environ.get('VOICE_RUN_REAL_ASR') != '1', reason='Opt-in real Whisper model and speech sample')
def test_real_sample_through_shared_api(monkeypatch):
    audio = (ROOT / 'data/samples/voice/sample3.wav').read_bytes()
    engine = WhisperASR(model_size=os.environ.get('WHISPER_MODEL_SIZE', 'small'),
                        device='cpu', compute_type='int8')
    monkeypatch.setattr(api, '_asr', engine)
    result = api.transcribe_voice(audio, language='en-US')
    print('\nReal Whisper sample3.wav:', result)
    assert result['raw_transcript'].strip()
    assert result['confidence_score'] is None or 0 <= result['confidence_score'] <= 1
    encoded = 'data:audio/wav;base64,' + base64.b64encode(audio).decode('ascii')
    assert api.transcribe_voice(encoded, language='en-US') == result
