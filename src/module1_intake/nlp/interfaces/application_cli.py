"""Development terminal client of application DTOs; no separate dialogue engine."""
from uuid import UUID, uuid4
from pathlib import Path

from .application import (TurnRequest, WorkflowActionRequest, VoiceRequest,
                          VoiceEditRequest, VoiceSubmitRequest, VoiceDraftRequest)


def run_application(service, initial, *, dataset_build=None, dataset=None, read=input, write=print):
    current = initial
    voice_view = None
    assessment_id = current.assessment_id
    if dataset_build:
        service.dataset_build = dataset_build
    if dataset is not None:
        service.dataset = dataset
    write('NLP CHATBOT V2 — persisted development dialogue, trusted development owner')
    write('Confirmation verifies transcription only. Q&A uses attributed facts; missing coverage is not safety.')
    write('/exit /new /resume UUID /revise /handoff /identify /assess /safety-answer /json')
    write('/voice WAV /voice-draft /voice-edit TEXT /voice-send /voice-cancel')
    write('Voice: xem/sửa bản nháp rồi /voice-send; kiểm tra dữ liệu trích xuất trước khi gõ xác nhận.')

    def display(response):
        for answer in response.qa_results:
            if answer.text not in response.assistant_message:
                write(answer.text)
        write(response.assistant_message)
        write(f'workflow={response.workflow_id} revision={response.revision} state={response.state} next={response.next_action}')

    display(current)
    try:
        while True:
            text = read('app> ').strip()
            if text in {'/exit', '/quit'}:
                break
            if not text:
                continue
            try:
                if text.startswith('/voice ') or text in {'/voice-draft', '/voice-send', '/voice-cancel'} or text.startswith('/voice-edit '):
                    if text.startswith('/voice '):
                        audio = Path(text.split(maxsplit=1)[1].strip('"')).read_bytes()
                        preview = service.preview_voice(VoiceRequest(workflow_id=current.workflow_id,
                            revision=current.revision, audio_payload=audio))
                    elif text == '/voice-draft':
                        preview = service.resume_voice(current.workflow_id)
                    else:
                        if voice_view is None or voice_view.workflow_id != current.workflow_id or voice_view.draft is None:
                            write('Dùng /voice-draft để xem bản nháp hiện tại hoặc /voice WAV để thu lại.')
                            continue
                        preview = voice_view
                        values = dict(workflow_id=current.workflow_id, revision=preview.revision,
                                      draft_id=preview.draft.draft_id)
                        if text.startswith('/voice-edit '):
                            preview = service.edit_voice(VoiceEditRequest(**values, text=text.split(maxsplit=1)[1]))
                        elif text == '/voice-cancel':
                            preview = service.discard_voice(VoiceDraftRequest(**values))
                        else:
                            current = service.submit_voice(VoiceSubmitRequest(**values, explicit_confirmation=True))
                            voice_view = None
                            display(current)
                            continue
                    voice_view = preview
                    if preview.error_code:
                        write(f'Voice: {preview.error_code}. Có thể thử lại; bản nháp trước được giữ nguyên.')
                    if preview.draft:
                        write(f'ASR gốc: {preview.draft.raw_transcript}')
                        write(f'Bản nháp để gửi: {preview.draft.text}')
                        write('/voice-edit TEXT để sửa; /voice-send để đồng ý gửi; /voice-cancel để bỏ bản nháp.')
                    current = service.resume(current.workflow_id)
                    continue
                if text == '/json':
                    write(current.model_dump_json(indent=2))
                    continue
                if text == '/new':
                    workflow = service.bot.store.workflow(current.workflow_id)
                    current = service.start(conversation_id=workflow['conversation_id'])
                    assessment_id = None
                    voice_view = None
                elif text.startswith('/resume '):
                    current = service.resume(UUID(text.split(maxsplit=1)[1]))
                    assessment_id = None
                    voice_view = None
                elif text == '/revise':
                    current = service.revise(current.workflow_id)
                    assessment_id = None
                    voice_view = None
                elif text == '/handoff':
                    write(service.handoff(current.workflow_id).model_dump_json(indent=2))
                    continue
                elif text in {'/identify', '/assess'}:
                    current = service.execute(WorkflowActionRequest(workflow_id=current.workflow_id,
                        revision=current.revision, request_key=uuid4(), explicit_request=True,
                        action='IDENTIFY' if text == '/identify' else 'ASSESS'))
                elif text == '/safety-answer':
                    if assessment_id is None:
                        write('UNAVAILABLE: no authoritative assessment has been performed in this client.')
                    else:
                        write(service.answer_assessment(current.workflow_id, assessment_id, 'Kết quả đánh giá tương tác có nguồn là gì?').text)
                    continue
                elif text.startswith('/'):
                    write('Unknown command. Use /exit to quit.')
                    continue
                else:
                    current = service.send(TurnRequest(workflow_id=current.workflow_id, revision=current.revision, text=text))
                assessment_id = current.assessment_id
                display(current)
            except Exception as error:
                voice_view = None
                # User/DB/model exception bodies may contain patient or connection data.
                write(f'Request rejected ({type(error).__name__}); reload the workflow before retrying.')
                try:
                    current = service.resume(current.workflow_id)
                except Exception:
                    write('Workflow reload unavailable. Use /exit and reconnect with trusted identity.')
    except (EOFError, KeyboardInterrupt):
        pass
    write('Application test ended.')
