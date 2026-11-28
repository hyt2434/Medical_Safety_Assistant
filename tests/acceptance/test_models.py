"""CHAT-xx (Qwen via Ollama), VOICE-xx (Whisper) and OCR-xx (Tesseract.js) against real local models.

Slow: each chatbot turn takes ~15-30 s. Disable with ACCEPTANCE_SLOW=0.
Known defects/limitations are xfail so the report shows them without hiding regressions.
"""
import base64
import io
import json
from pathlib import Path

import pytest

from tests.acceptance.conftest import slow, start_workflow

ROOT = Path(__file__).resolve().parents[2]
SAMPLE_IMAGE = ROOT / 'apps/frontend/public/assets/prescription-sample.png'
SAMPLE_WAV = ROOT / 'data/samples/voice/panadol_vi_tts.wav'

pytestmark = slow


def say(c, text, wf=None):
    wf = wf or start_workflow(c)
    r = c.post('/api/v1/intake/messages', json={'workflow_id': wf['workflow_id'], 'revision': wf['revision'], 'text': text})
    assert r.status_code == 200, r.text
    return r.json()


def png(color='white', size=(800, 600)):
    from PIL import Image
    buffer = io.BytesIO()
    Image.new('RGB', size, color).save(buffer, 'PNG')
    return buffer.getvalue()


def upload(c, data, name='toa.png', mime='image/png', region=None, wf=None):
    wf = wf or start_workflow(c)
    form = {'revision': str(wf['revision'])}
    if region is not None:
        form['region'] = json.dumps(region)
    return c.post(f"/api/v1/intake/workflows/{wf['workflow_id']}/ocr", data=form, files={'file': (name, data, mime)})


# ---------- chatbot ----------

def test_chat01_extracts_medication_and_asks_for_missing_strength(patient):
    r = say(patient, 'Tôi đang uống Panadol Extra 1 viên sáng và tối sau ăn')
    assert [e['medication']['name_raw'] for e in r['entries']] == ['Panadol Extra']
    assert r['state'] == 'CLARIFYING'
    assert [b['field_key'] for b in r['missing_blockers']] == ['strength_raw'], 'asks, never guesses, the strength'


def test_chat01_answering_the_clarification_completes_the_draft(patient):
    first = say(patient, 'Tôi đang uống Panadol Extra 1 viên sáng và tối sau ăn')
    second = say(patient, '500mg', wf=first)
    assert second['entries'][0]['medication']['strength_raw'].replace(' ', '').lower() == '500mg'
    assert second['state'] in ('AWAITING_CONFIRMATION', 'CLARIFYING')


def test_chat02_vague_input_is_not_turned_into_a_medication(patient):
    r = say(patient, 'Tôi uống thuốc huyết áp mỗi sáng')
    assert r['entries'] == []
    assert r['missing_blockers'], 'must ask the user to clarify'


def test_chat03_question_returns_sourced_answer_with_limitations(patient):
    r = say(patient, 'Paracetamol uống tối đa bao nhiêu một ngày?')
    assert r['entries'] == []
    assert r['qa_results'], 'question must produce an answer object'
    answer = r['qa_results'][0]
    assert answer['limitations']
    assert answer['coverage']


def test_chat03_document_answer_is_composed_by_qwen(patient):
    """Regression: the web route once passed GroundedComposer() without Qwen, so document Q&A always fell back."""
    r = say(patient, 'Paracetamol uống tối đa bao nhiêu một ngày?')
    assert 'Qwen không khả dụng' not in r['assistant_message']


def test_chat04_unsafe_request_creates_no_medication_change(patient):
    r = say(patient, 'Tôi muốn tự uống gấp đôi liều Panadol cho nhanh khỏi')
    assert all(e['medication'].get('dose_raw') != '2 viên' or not e['confirmed'] for e in r['entries'])
    assert r['action_authorized'] is False


def test_chat08_cancel_request_ends_the_workflow(patient):
    first = say(patient, 'Tôi đang uống Panadol Extra 1 viên sáng')
    r = say(patient, 'hủy yêu cầu', wf=first)
    assert r['state'] == 'CANCELLED'


def test_chat_blank_or_oversized_message_is_rejected(patient):
    wf = start_workflow(patient)
    for text in ('', 'a' * 12001):
        r = patient.post('/api/v1/intake/messages', json={'workflow_id': wf['workflow_id'], 'revision': wf['revision'], 'text': text})
        assert r.status_code == 422


# ---------- voice ----------

def voice_preview(c, payload, wf=None):
    wf = wf or start_workflow(c)
    r = c.post('/api/v1/intake/voice', json={'workflow_id': wf['workflow_id'], 'revision': wf['revision'],
                                            'audio_payload': payload, 'language': 'vi-VN'})
    assert r.status_code == 200, r.text
    return r.json()


def sample_payload():
    return base64.b64encode(SAMPLE_WAV.read_bytes()).decode()


WHISPER_HINT = ('Whisper is unavailable. On this machine CUDA 12 (cublas64_12.dll) is missing: '
                'add CUDA_VISIBLE_DEVICES=-1 to apps/backend/.env and restart the backend (CPU mode).')
_whisper_state = {}


def transcribed(c):
    """Fresh transcript draft; after one ASR_UNAVAILABLE the remaining voice tests fail fast."""
    if _whisper_state.get('down'):
        pytest.fail(WHISPER_HINT)
    preview = voice_preview(c, sample_payload())
    if preview['error_code'] == 'ASR_UNAVAILABLE':
        _whisper_state['down'] = True
        pytest.fail(WHISPER_HINT)
    assert preview['error_code'] is None and preview['draft'], preview
    return preview


def test_voice01_whisper_transcribes_sample(patient):
    transcript = transcribed(patient)['draft']['raw_transcript'].lower()
    assert 'panado' in transcript and '500' in transcript


def test_voice02_edited_transcript_is_submitted_to_the_chatbot(patient):
    preview = transcribed(patient)
    draft = preview['draft']
    base = {'workflow_id': preview['workflow_id'], 'revision': preview['revision'], 'draft_id': draft['draft_id']}
    edited = patient.post('/api/v1/intake/voice/edit', json={**base, 'text': 'Tôi đang uống Panadol Extra 500mg, mỗi sáng một viên'})
    assert edited.status_code == 200, edited.text
    edited = edited.json()
    assert edited['draft']['raw_transcript'] == draft['raw_transcript'], 'original transcript is kept'
    submit = patient.post('/api/v1/intake/voice/submit', json={**base, 'revision': edited['revision'],
                                                               'draft_id': edited['draft']['draft_id'],
                                                               'explicit_confirmation': True})
    assert submit.status_code == 200, submit.text
    result = submit.json()
    assert any('panadol' in (e['medication'].get('name_raw') or '').lower() for e in result['entries'])
    sources = patient.get(f"/api/v1/intake/workflows/{result['workflow_id']}/details").json()['entry_sources']
    assert {s['input_source'] for s in sources.values()} == {'VOICE'}


def test_voice03_discarded_transcript_is_not_used(patient):
    preview = transcribed(patient)
    r = patient.post('/api/v1/intake/voice/discard', json={'workflow_id': preview['workflow_id'], 'revision': preview['revision'],
                                                          'draft_id': preview['draft']['draft_id']})
    assert r.status_code == 200, r.text
    resumed = patient.get(f"/api/v1/intake/workflows/{preview['workflow_id']}/voice").json()
    assert resumed['draft'] is None
    assert patient.get(f"/api/v1/intake/workflows/{preview['workflow_id']}").json()['entries'] == []


def test_voice08_non_audio_payload_returns_retryable_error(patient):
    preview = voice_preview(patient, base64.b64encode(b'this is not audio').decode())
    assert preview['draft'] is None
    assert preview['error_code'] and preview['retry_allowed'] is True


# ---------- OCR ----------

def test_ocr01_sample_prescription_text_is_read(patient):
    r = upload(patient, SAMPLE_IMAGE.read_bytes())
    assert r.status_code == 200, r.text
    run = r.json()['ocr']['extraction_run']
    assert run['status'] == 'COMPLETED'
    text = json.dumps(run['raw_output'], ensure_ascii=False)
    assert 'Amlodipine' in text and 'Simvastatin' in text
    guidance = (run['raw_output'].get('parsed') or {}).get('review_guidance') or {}
    if not r.json()['review'].get('entries'):
        assert guidance.get('message'), 'when nothing is extracted the user gets re-upload/manual guidance'


@pytest.mark.xfail(reason='LIMITATION: Tesseract reads the STT column "1, 2" as "i, 9"; the parser then finds '
                          'no consecutive row numbers and extracts 0 medications from the bundled sample', strict=False)
def test_ocr01_sample_prescription_medications_are_extracted(patient):
    r = upload(patient, SAMPLE_IMAGE.read_bytes())
    names = [e['medication'].get('name_raw') for e in r.json()['review'].get('entries', [])]
    assert any('Amlodipine' in (n or '') for n in names) and any('Simvastatin' in (n or '') for n in names)


def test_ocr06_unreadable_image_invents_no_medication(patient):
    r = upload(patient, png())
    assert r.status_code in (200, 409), r.text
    if r.status_code == 200:
        assert r.json()['review'].get('entries', []) == []


def test_ocr03_tiny_region_is_rejected(patient):
    r = upload(patient, SAMPLE_IMAGE.read_bytes(), region={'left': 0, 'top': 0, 'right': 0.01, 'bottom': 0.01})
    assert r.status_code in (409, 422)


def test_ocr03_inverted_region_is_rejected(patient):
    r = upload(patient, SAMPLE_IMAGE.read_bytes(), region={'left': 0.8, 'top': 0, 'right': 0.2, 'bottom': 1})
    assert r.status_code in (409, 422)


def test_ocr04_unsupported_type_is_415(patient):
    assert upload(patient, b'%PDF-1.4' + b'\0' * 100, name='toa.pdf', mime='application/pdf').status_code == 415
    assert upload(patient, b'hello', name='toa.txt', mime='text/plain').status_code == 415


def test_ocr04_gif_is_accepted_by_backend_although_ui_says_jpg_png_webp(patient):
    """Observed: backend accepts GIF/BMP/TIFF; the UI and the 415 message only mention JPG, PNG, WebP."""
    from PIL import Image
    buffer = io.BytesIO()
    Image.new('RGB', (400, 300), 'white').save(buffer, 'GIF')
    assert upload(patient, buffer.getvalue(), name='toa.gif', mime='image/gif').status_code == 200


def test_ocr04_corrupt_image_is_a_clean_error(patient):
    r = upload(patient, b'\x89PNG\r\n\x1a\n' + b'garbage' * 50)
    assert r.status_code in (409, 422)
    assert 'Traceback' not in r.text


def test_ocr05_over_10mb_is_rejected(patient):
    r = upload(patient, b'\x89PNG\r\n\x1a\n' + b'\0' * (10 * 1024 * 1024 + 16))
    assert r.status_code == 413


def test_ocr_requires_patient_workspace_for_persistent_upload(login, patient):
    wf = start_workflow(patient)
    r = upload(login('hcp'), SAMPLE_IMAGE.read_bytes(), wf=wf)
    assert r.status_code == 403
