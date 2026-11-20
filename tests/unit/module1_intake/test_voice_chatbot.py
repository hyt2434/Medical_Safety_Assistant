"""Voice review lifecycle over the real application; repository and ASR are spies."""
from copy import deepcopy
import hashlib
from uuid import uuid4

import pytest

from module1_intake import api
from module1_intake.voice import ASRResult, VoiceInputError
from module1_intake.nlp.interfaces.application import (
    ApplicationService, ConfirmationRequest, TurnRequest, VoiceRequest,
    VoiceEditRequest, VoiceSubmitRequest, VoiceDraftRequest,
)
from module1_intake.nlp.interfaces.application_cli import run_application
from module1_intake.nlp.models import Intent
from module1_intake.nlp.understanding.providers import MockProvider, InferenceError
from tests.unit.test_nlp import FakeCore


TEXT = 'Tôi đang uống Panadol 500mg, dạng viên nén, mỗi sáng 1 viên.'
CORRECTION = 'sửa thuốc 1 thành Panadol 500mg, dạng viên nén, mỗi sáng 2 viên.'


class VoiceCore(FakeCore):
    def record_input(self, intake, modality, original_bytes, **kw):
        assert modality in {'TEXT', 'AUDIO'}
        self._owned('intake_sessions', intake)
        return self.put('intake_inputs', session_id=intake, modality=modality,
                        input_digest=hashlib.sha256(original_bytes).hexdigest(), **kw)


class Speech:
    def transcribe(self, audio, language):
        if audio == b'fail':
            raise VoiceInputError('ASR_UNAVAILABLE', 'test failure')
        if audio == b'no speech':
            return ASRResult(' ', None)
        return ASRResult(TEXT, 0.9)


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setattr(api, '_asr', Speech())
    repo = VoiceCore()
    service = ApplicationService(repo, MockProvider())
    return repo, service, service.start(task=Intent.ADD_MEDICATION)


def preview(service, current, audio=b'speech'):
    return service.preview_voice(VoiceRequest(workflow_id=current.workflow_id,
        revision=current.revision, audio_payload=audio))


def draft_args(view):
    return dict(workflow_id=view.workflow_id, revision=view.revision, draft_id=view.draft.draft_id)


def submit(service, view):
    return service.submit_voice(VoiceSubmitRequest(**draft_args(view), explicit_confirmation=True))


def test_voice_and_typing_share_extraction_session_and_review(app):
    repo, service, initial = app
    typed = service.send(TurnRequest(workflow_id=initial.workflow_id, revision=initial.revision, text=TEXT))
    voice_start = service.start(conversation_id=service.bot.store.workflow(initial.workflow_id)['conversation_id'], task=Intent.ADD_MEDICATION)
    before_calls = service.bot.provider.calls
    view = preview(service, voice_start)
    assert service.bot.provider.calls == before_calls
    assert service.resume(voice_start.workflow_id).entries == []
    assert view.draft.raw_transcript == view.draft.text == TEXT
    voiced = submit(service, view)
    assert voiced.workflow_id == voice_start.workflow_id
    assert voiced.entries[0].medication == typed.entries[0].medication
    assert voiced.state == 'AWAITING_CONFIRMATION' and not voiced.action_authorized
    assert not voiced.entries[0].confirmed
    assert service.resume_voice(voiced.workflow_id).draft is None
    messages = list(repo.tables['conversation_messages'].values())
    voice_message = next(row for row in messages if (row.get('metadata') or {}).get('input_source') == 'VOICE')
    assert voice_message['conversation_id'] == service.bot.store.workflow(voice_start.workflow_id)['conversation_id']
    inputs = list(repo.tables['intake_inputs'].values())
    interpreted = next(row for row in inputs if row['modality'] == 'TEXT' and 'voice' in row['payload'])
    assert interpreted['payload']['voice']['audio_input_id'] == str(view.draft.audio_input_id)
    assert interpreted['payload']['text'] == TEXT
    original = repo._owned('intake_inputs', view.draft.audio_input_id)
    assert original['modality'] == 'TEXT'
    assert original['input_digest'] == hashlib.sha256(TEXT.encode('utf-8')).hexdigest()
    assert original['payload']['audio_sha256'] == hashlib.sha256(b'speech').hexdigest()
    assert original['payload']['audio_retained'] is False
    assert 'object_locator' not in original['payload']


def test_edit_review_then_correct_medication_before_confirmation(app):
    repo, service, initial = app
    view = preview(service, initial)
    edited_text = TEXT.replace('1 viên', '2 viên')
    view = service.edit_voice(VoiceEditRequest(**draft_args(view), text=edited_text))
    assert view.draft.raw_transcript == TEXT and view.draft.text == edited_text
    resumed = ApplicationService(repo, service.bot.provider)
    assert resumed.resume_voice(view.workflow_id) == view
    result = submit(resumed, view)
    assert result.entries[0].medication.dose_raw == '2 viên'
    assert not result.entries[0].confirmed
    # A normal typed follow-up then uses the existing correction/version path.
    result = resumed.send(TurnRequest(workflow_id=result.workflow_id, revision=result.revision,
        text=CORRECTION.replace('2 viên', '1 viên')))
    assert result.entries[0].medication.dose_raw == '1 viên'
    assert not result.entries[0].confirmed
    result = resumed.confirm(ConfirmationRequest(workflow_id=result.workflow_id, revision=result.revision,
        request_key=uuid4(), explicit_confirmation=True))
    assert result.entries[0].confirmed and result.authorization_scope == 'TRANSCRIPTION_ONLY'


@pytest.mark.parametrize('audio,code', [(b'', 'INVALID_AUDIO'), (b'fail', 'ASR_UNAVAILABLE'), (b'no speech', 'NO_SPEECH_DETECTED')])
def test_failed_retry_preserves_edited_draft_and_existing_medication_review(app, audio, code):
    repo, service, initial = app
    current = service.send(TurnRequest(workflow_id=initial.workflow_id, revision=initial.revision, text=TEXT))
    view = preview(service, current)
    view = service.edit_voice(VoiceEditRequest(**draft_args(view), text=CORRECTION))
    before = deepcopy(repo.tables)
    failed = preview(service, view, audio)
    assert failed.error_code == code and failed.retry_allowed
    assert failed.draft == view.draft and failed.revision == view.revision
    assert repo.tables == before
    retried = preview(service, failed)
    assert retried.draft.draft_id != view.draft.draft_id
    with pytest.raises(ValueError):
        submit(service, view)


def test_pending_draft_blocks_implicit_send_confirmation_and_stale_access(app):
    repo, service, initial = app
    view = preview(service, initial)
    for call in [
        lambda: service.send(TurnRequest(workflow_id=view.workflow_id, revision=view.revision, text=TEXT)),
        lambda: service.confirm(ConfirmationRequest(workflow_id=view.workflow_id, revision=view.revision,
            request_key=uuid4(), explicit_confirmation=True)),
        lambda: service.submit_voice(VoiceSubmitRequest(**draft_args(view), explicit_confirmation=False)),
        lambda: preview(service, initial),
        lambda: service.edit_voice(VoiceEditRequest(**draft_args(view), text=' ')),
    ]:
        with pytest.raises(ValueError):
            call()
    owner = repo.owner
    repo.owner = uuid4()
    with pytest.raises(PermissionError):
        service.resume_voice(view.workflow_id)
    repo.owner = owner
    discarded = service.discard_voice(VoiceDraftRequest(**draft_args(view)))
    assert discarded.draft is None
    current = service.resume(view.workflow_id)
    assert service.send(TurnRequest(workflow_id=current.workflow_id, revision=current.revision, text=TEXT)).entries


def test_nlp_failure_retains_voice_draft_for_edit_and_retry(app):
    _, service, initial = app
    service.bot.provider = MockProvider([InferenceError('test failure')] * 2)
    view = preview(service, initial)
    result = submit(service, view)
    assert result.error_code
    assert service.resume_voice(view.workflow_id).draft == view.draft
    assert not result.entries and not result.action_authorized
    service.bot.provider = MockProvider()
    assert submit(service, service.resume_voice(view.workflow_id)).entries


def test_spoken_unknown_slot_uses_normal_dialogue_without_leaving_draft(app, monkeypatch):
    _, service, initial = app
    current = service.send(TurnRequest(workflow_id=initial.workflow_id, revision=initial.revision,
        text='Tôi đang uống Panadol'))
    class UnknownSpeech:
        def transcribe(self, audio, language):
            return ASRResult('không rõ', 0.9)
    monkeypatch.setattr(api, '_asr', UnknownSpeech())
    result = submit(service, preview(service, current))
    assert service.resume_voice(result.workflow_id).draft is None
    assert result.state == 'AWAITING_CONFIRMATION'


def test_cli_displays_draft_edits_and_submission(app, tmp_path):
    _, service, initial = app
    audio = tmp_path / 'speech.wav'
    audio.write_bytes(b'speech')
    commands = iter([f'/voice "{audio}"', '/voice-edit ' + TEXT.replace('1 viên', '2 viên'),
                     '/voice-send', 'xác nhận', '/exit'])
    output = []
    run_application(service, initial, read=lambda _: next(commands), write=output.append)
    assert any('ASR gốc:' in line for line in output)
    assert any('Bản nháp để gửi:' in line and '2 viên' in line for line in output)
    current = service.resume(initial.workflow_id)
    assert current.state == 'COMPLETED' and current.entries[0].medication.dose_raw == '2 viên'


def test_cli_never_sends_a_new_draft_the_user_has_not_seen(app, tmp_path):
    _, service, initial = app
    audio = tmp_path / 'speech.wav'
    audio.write_bytes(b'speech')
    commands = iter([f'/voice "{audio}"', '/voice-send', '/exit'])
    replacement = []
    def read(_):
        command = next(commands)
        if command == '/voice-send':
            live = service.resume(initial.workflow_id)
            replacement.append(preview(service, live))
        return command
    output = []
    run_application(service, initial, read=read, write=output.append)
    assert service.bot.provider.calls == 0
    assert not service.resume(initial.workflow_id).entries
    assert service.resume_voice(initial.workflow_id).draft == replacement[0].draft
    assert any('Request rejected' in line for line in output)
