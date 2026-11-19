"""Real Qwen and optional real Vietnamese WAV, with explicit measurement limits.

Repository is a test spy. No patient database, synthetic ASR transcript or scripted
extraction is substituted for a missing Vietnamese recording.
"""
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest

from module1_intake import api
from module1_intake.voice import WhisperASR
from module1_intake.nlp.interfaces.application import (
    ApplicationService, ConfirmationRequest, TurnRequest, VoiceRequest,
    VoiceSubmitRequest, VoiceEditRequest,
)
from module1_intake.nlp.models import Intent, Understanding
from module1_intake.nlp.understanding.providers import OllamaProvider
from module1_intake.nlp.understanding.validation import validate_understanding, EvidenceError
from tests.unit.module1_intake.test_voice_chatbot import VoiceCore, draft_args


ROOT = Path(__file__).resolve().parents[3]
SPOKEN = 'Tôi đang uống Panadol năm trăm miligam, dạng viên nén, mỗi sáng một viên'
NUMERIC = 'Tôi đang uống Panadol 500mg, dạng viên nén, mỗi sáng một viên'
CORRECTION = 'sửa thuốc 1 thành Panadol 500mg, dạng viên nén, mỗi sáng hai viên'
pytestmark = pytest.mark.skipif(os.environ.get('VOICE_RUN_REAL_CHATBOT') != '1', reason='Opt-in real local Qwen')


class ObservedOllama(OllamaProvider):
    """Capture actual responses for synthetic test evidence; never change inference."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.outputs = []

    def infer(self, text, context):
        raw = super().infer(text, context)
        self.outputs.append(raw)
        return raw


def service():
    return ApplicationService(VoiceCore(), ObservedOllama(
        os.environ.get('NLP_OLLAMA_MODEL', 'qwen3.5:9b'),
        timeout=float(os.environ.get('NLP_OLLAMA_TIMEOUT', '60'))))


def trace(response):
    return {'workflow_id': str(response.workflow_id), 'state': response.state,
        'error_code': response.error_code, 'confirmed': response.action_authorized,
        'extracted': [entry.medication.model_dump(mode='json') for entry in response.entries]}


def save(name, report):
    output = ROOT / 'artifacts/voice_manual_input' / name
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('\nVietnamese real chatbot:', json.dumps(report, ensure_ascii=False))


def test_real_qwen_vietnamese_typed_and_user_correction():
    reports = []
    for text in (SPOKEN, NUMERIC):
        app = service()
        initial = app.start(task=Intent.ADD_MEDICATION)
        result = app.send(TurnRequest(workflow_id=initial.workflow_id, revision=initial.revision, text=text))
        attempts = []
        for raw in app.bot.provider.outputs:
            value = Understanding.model_validate_json(raw)
            try:
                validate_understanding(value, text)
                error = None
            except EvidenceError as rejected:
                error = str(rejected)
            attempts.append({'raw_medications': [med.model_dump(mode='json') for med in value.medications],
                             'validation_error': error})
        reports.append({'original': text, 'input_path': 'TYPED', 'transcript': None,
                        'actual_inference_attempts': attempts, **trace(result)})
        assert not result.action_authorized
        assert result.state == 'AWAITING_CONFIRMATION' and not result.error_code
        assert result.entries[0].medication.strength_raw == ('năm trăm miligam' if text == SPOKEN else '500mg')
        assert result.entries[0].medication.dose_raw == 'một viên'
        if text == NUMERIC:
            assert result.entries and not result.error_code
            med = result.entries[0].medication
            assert (med.name_raw, med.strength_raw, med.dose_raw) == ('Panadol', '500mg', 'một viên')
            corrected = app.send(TurnRequest(workflow_id=result.workflow_id, revision=result.revision, text=CORRECTION))
            reports.append({'original': CORRECTION, 'input_path': 'TYPED_CORRECTION', 'transcript': None, **trace(corrected)})
            assert corrected.entries[0].medication.dose_raw == 'hai viên' and not corrected.action_authorized
            confirmed = app.confirm(ConfirmationRequest(workflow_id=corrected.workflow_id,
                revision=corrected.revision, request_key=uuid4(), explicit_confirmation=True))
            assert confirmed.entries[0].confirmed
            reports.append({'input_path': 'EXPLICIT_FINAL_CONFIRMATION', **trace(confirmed)})
    save('vietnamese_typed_trace.json', {'provider': 'real Ollama Qwen', 'repository': 'test spy',
        'traces': reports, 'voice_verified': False,
        'voice_note': 'A separate opt-in WAV test is required; typed results do not validate Vietnamese ASR.'})


def test_real_qwen_dose_only_followup_keeps_strength_unknown():
    app = service()
    current = app.start(task=Intent.ADD_MEDICATION)
    first = 'Tôi đang uống Panadol, dạng viên nén'
    current = app.send(TurnRequest(workflow_id=current.workflow_id, revision=current.revision, text=first))
    assert current.entries and current.entries[0].medication.strength_raw is None
    followup = 'mỗi sáng một viên'
    current = app.send(TurnRequest(workflow_id=current.workflow_id, revision=current.revision, text=followup))
    save('vietnamese_dose_only_trace.json', {'original': first, 'followup': followup,
        'provider': 'real Ollama Qwen', 'repository': 'test spy', **trace(current)})
    assert current.error_code is None and current.state == 'CLARIFYING'
    assert current.entries[0].medication.strength_raw is None
    assert current.entries[0].medication.dose_raw == 'một viên'
    assert not current.action_authorized


def test_same_vietnamese_sentence_typed_and_real_whisper_wav(monkeypatch):
    path = os.environ.get('VOICE_VI_WAV')
    if not path:
        pytest.skip('No Vietnamese WAV with verified original; set VOICE_VI_WAV and VOICE_VI_TEXT')
    audio = Path(path).resolve()
    assert audio.is_relative_to(ROOT), 'Keep the test audio inside this repository'
    original = os.environ.get('VOICE_VI_TEXT', SPOKEN)
    monkeypatch.setattr(api, '_asr', WhisperASR(
        model_size=os.environ.get('WHISPER_MODEL_SIZE', 'small'), device='cpu', compute_type='int8'))
    app = service()
    typed = app.start(task=Intent.ADD_MEDICATION)
    typed = app.send(TurnRequest(workflow_id=typed.workflow_id, revision=typed.revision, text=original))
    voice = app.start(task=Intent.ADD_MEDICATION)
    preview = app.preview_voice(VoiceRequest(workflow_id=voice.workflow_id, revision=voice.revision,
        audio_payload=audio.read_bytes(), language='vi-VN'))
    assert not preview.error_code and preview.draft
    result = app.submit_voice(VoiceSubmitRequest(**draft_args(preview), explicit_confirmation=True))
    report = {'original': original, 'audio': str(audio.relative_to(ROOT)),
        'synthetic_voice': os.environ.get('VOICE_VI_SYNTHETIC') == '1', 'repository': 'test spy',
        'provider': 'real Ollama Qwen', 'asr': 'real Whisper CPU/int8',
        'transcript': preview.draft.raw_transcript, 'confidence_score': preview.draft.confidence_score,
        'typed': trace(typed), 'voice': trace(result)}
    assert not result.action_authorized
    pending = app.resume_voice(voice.workflow_id)
    if pending.draft:
        edited = app.edit_voice(VoiceEditRequest(**draft_args(pending), text=NUMERIC.replace('một viên', 'hai viên')))
        corrected = app.submit_voice(VoiceSubmitRequest(**draft_args(edited), explicit_confirmation=True))
    else:
        corrected = app.send(TurnRequest(workflow_id=result.workflow_id, revision=result.revision, text=CORRECTION))
    report['user_correction'] = trace(corrected)
    save('vietnamese_voice_trace.json', report)
    assert corrected.entries and not corrected.error_code
    assert corrected.entries[0].medication.dose_raw == 'hai viên'
    assert not corrected.entries[0].confirmed
    final = app.confirm(ConfirmationRequest(workflow_id=corrected.workflow_id, revision=corrected.revision,
        request_key=uuid4(), explicit_confirmation=True))
    assert final.entries[0].confirmed
