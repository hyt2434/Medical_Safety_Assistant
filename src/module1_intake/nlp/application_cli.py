"""Development terminal client of application DTOs; no separate dialogue engine."""
from uuid import UUID

from .application import TurnRequest


def run_application(service, initial, *, dataset_build=None, dataset=None, read=input, write=print):
    current = initial
    assessment_id = None
    write('MODULE 1 APPLICATION MVP — persisted development dialogue, trusted development owner')
    write('Confirmation verifies transcription only. Q&A uses attributed facts; missing coverage is not safety.')
    write('/exit /new /resume UUID /revise /handoff /identify /assess /safety-answer /json')

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
                if text == '/json':
                    write(current.model_dump_json(indent=2))
                    continue
                if text == '/new':
                    workflow = service.bot.store.workflow(current.workflow_id)
                    current = service.start(conversation_id=workflow['conversation_id'])
                    assessment_id = None
                elif text.startswith('/resume '):
                    current = service.resume(UUID(text.split(maxsplit=1)[1]))
                    assessment_id = None
                elif text == '/revise':
                    current = service.revise(current.workflow_id)
                    assessment_id = None
                elif text == '/handoff':
                    write(service.handoff(current.workflow_id).model_dump_json(indent=2))
                    continue
                elif text == '/identify':
                    if not dataset_build:
                        write('UNAVAILABLE: configure a published Core reference build first.')
                    else:
                        results = service.identify(current.workflow_id, dataset_build=dataset_build)
                        write(str([{'outcome': row['match_status'], 'entry_version_id': str(row['entry_version_id'])} for row, result in results]))
                    continue
                elif text == '/assess':
                    if not dataset_build or dataset is None:
                        write('UNAVAILABLE: published reference build and an existing verified Module 3 index are required.')
                    else:
                        from uuid import uuid4
                        snapshot = service.prepare_safety_snapshot(current.workflow_id, dataset_build=dataset_build)
                        assessment, result = service.assess_snapshot(current.workflow_id, snapshot['id'], dataset, request_key=uuid4())
                        assessment_id = assessment['id']
                        write(f"Module 3 execution={assessment['execution_status']}; assessment={assessment_id}; no general safety conclusion.")
                    continue
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
                display(current)
            except Exception as error:
                # User/DB/model exception bodies may contain patient or connection data.
                write(f'Request rejected ({type(error).__name__}); reload the workflow before retrying.')
                try:
                    current = service.resume(current.workflow_id)
                except Exception:
                    write('Workflow reload unavailable. Use /exit and reconnect with trusted identity.')
    except (EOFError, KeyboardInterrupt):
        pass
    write('Application test ended.')
