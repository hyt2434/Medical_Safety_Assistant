"""Authenticated owner-only API over the existing Core V4 application service."""
import os
import tempfile
from pathlib import Path
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict, ValidationError, Field

from apps.backend.api.deps import require_permission, current_session
from shared.auth.core_owner import core_owner
from shared.auth.settings import core_database_dsn
from shared.auth.db import transaction
from shared.auth.sessions import audit
from shared.db import CoreRepository
from shared.intake_contracts import Medication
from module1_intake.nlp.interfaces.application import (
    ApplicationService, TurnRequest, ConfirmationRequest, WorkflowActionRequest,
    VoiceRequest, VoiceEditRequest, VoiceSubmitRequest, VoiceDraftRequest, ManualInputRequest, ManualEditRequest, EntryEditRequest,
)
from module1_intake.nlp.models import Intent
from module1_intake.nlp.understanding.providers import OllamaProvider
from module1_intake.ocr.application import intake as ocr_intake
from module1_intake.ocr.application.service import OcrError
from module1_intake.ocr.imaging.input import CONTENT_TYPES
from module1_intake.ocr.imaging.regions import ImageRegion
from module3_interactions.official_ddinter.dataset import OfficialDataset

router = APIRouter(prefix='/api/v1/intake', tags=['Core V4 intake'])

# HTTP JSON carries UUID strings; retain the application's strict Python DTOs.
class HttpTurn(TurnRequest):
    model_config = ConfigDict(extra='forbid', strict=False)
class HttpConfirmation(ConfirmationRequest):
    model_config = ConfigDict(extra='forbid', strict=False)
class HttpAction(WorkflowActionRequest):
    model_config = ConfigDict(extra='forbid', strict=False)
class HttpManual(ManualInputRequest):
    model_config = ConfigDict(extra='forbid', strict=False)
class HttpManualEdit(ManualEditRequest):
    model_config = ConfigDict(extra='forbid', strict=False)
class HttpVoice(VoiceRequest):
    model_config = ConfigDict(extra='forbid', strict=False)
class HttpVoiceEdit(VoiceEditRequest):
    model_config = ConfigDict(extra='forbid', strict=False)
class HttpVoiceSubmit(VoiceSubmitRequest):
    model_config = ConfigDict(extra='forbid', strict=False)
class HttpVoiceDraft(VoiceDraftRequest):
    model_config = ConfigDict(extra='forbid', strict=False)
class HttpEntryEdit(EntryEditRequest):
    model_config = ConfigDict(extra='forbid', strict=False)


@router.get('/capabilities')
def capabilities(session=Depends(current_session)):
    linked = False
    dsn = core_database_dsn()
    try:
        owner = core_owner(session['account']['id'])
        if dsn:
            with psycopg.connect(dsn, autocommit=True, connect_timeout=3) as connection:
                linked = bool(connection.execute('SELECT 1 FROM identity.users WHERE id=%s', (owner,)).fetchone())
    except (PermissionError, ValueError, TypeError, psycopg.Error):
        pass
    return {'persistent_intake': bool(linked and dsn and
        os.environ.get('CORE_REFERENCE_BUILD') and 'patient.workspace' in session['contextPermissions'])}


def _deny_missing_core_link(session):
    # Commit to Auth before raising: this denial creates no Core resource and
    # must survive the request/Core connection unwinding. No body data is used.
    account_id = session['account']['id']
    with transaction() as db:
        audit(db, account_id, 'intake.denied.core_link_missing',
              target_type='account', target=account_id, success=False)


def current_application(session=Depends(require_permission('patient.workspace'))):
    try:
        owner = core_owner(session['account']['id'])
    except PermissionError:
        _deny_missing_core_link(session)
        raise HTTPException(403, 'Tài khoản chưa được liên kết với hồ sơ Core') from None
    except (ValueError, TypeError):
        raise HTTPException(503, 'Cấu hình liên kết tài khoản Core không hợp lệ') from None
    dsn, build = core_database_dsn(), os.environ.get('CORE_REFERENCE_BUILD')
    if not dsn or not build:
        raise HTTPException(503, 'Chưa cấu hình PostgreSQL Core và phiên bản danh mục')
    try:
        with psycopg.connect(dsn, autocommit=True) as connection:
            if not connection.execute('SELECT 1 FROM identity.users WHERE id=%s', (owner,)).fetchone():
                _deny_missing_core_link(session)
                raise HTTPException(403, 'Liên kết Core chưa được cấp phát')
            repo = CoreRepository(connection, authenticated_owner=owner)
            # Reference snapshots are optional for intake persistence. Missing/corrupt
            # DDInter must disable assessment, not prevent saving an OCR/manual draft.
            try:
                dataset = OfficialDataset()
            except (OSError, ValueError, KeyError):
                dataset = None
            yield ApplicationService(repo, OllamaProvider(os.environ.get('NLP_OLLAMA_MODEL', 'qwen3.5:9b')),
                dataset_build=build, dataset=dataset,
                data_context=os.environ.get('CORE_DATA_CONTEXT', 'PATIENT'))
    except PermissionError:
        raise HTTPException(404, 'Không tìm thấy tài nguyên của tài khoản') from None
    except (ValueError, OcrError) as error:
        raise HTTPException(409, str(error)) from None
    except psycopg.Error:
        raise HTTPException(503, 'Core hiện chưa sẵn sàng') from None


class StartRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')


@router.post('/workflows')
def start(request: StartRequest | None = None, app=Depends(current_application)):
    return app.start(task=Intent.ADD_MEDICATION)


@router.get('/workflows/{workflow_id}')
def resume(workflow_id: UUID, app=Depends(current_application)):
    return app.resume(workflow_id)


@router.post('/messages')
def message(request: HttpTurn, app=Depends(current_application)):
    return app.send(request)


@router.get('/workflows/{workflow_id}/details')
def details(workflow_id: UUID, app=Depends(current_application)):
    return app.details(workflow_id)


class RevisionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    revision: int = Field(ge=1)


@router.post('/workflows/{workflow_id}/revise')
def revise(workflow_id: UUID, request: RevisionRequest, app=Depends(current_application)):
    return app.revise(workflow_id, expected_revision=request.revision)


@router.post('/entries/edit')
def edit_entry(request: HttpEntryEdit, app=Depends(current_application)):
    return app.edit_entry(request)


@router.get('/workflows/{workflow_id}/voice')
def voice_draft(workflow_id: UUID, app=Depends(current_application)):
    return app.resume_voice(workflow_id)


@router.post('/voice/discard')
def discard_voice(request: HttpVoiceDraft, app=Depends(current_application)):
    return app.discard_voice(request)


@router.post('/manual')
def manual(request: HttpManual, app=Depends(current_application)):
    return app.save_manual(request)


@router.post('/manual/edit')
def edit_manual(request: HttpManualEdit, app=Depends(current_application)):
    return app.save_manual(request)


@router.post('/voice')
def voice(request: HttpVoice, app=Depends(current_application)):
    return app.preview_voice(request)


@router.post('/voice/edit')
def edit_voice(request: HttpVoiceEdit, app=Depends(current_application)):
    return app.edit_voice(request)


@router.post('/voice/submit')
def submit_voice(request: HttpVoiceSubmit, app=Depends(current_application)):
    return app.submit_voice(request)


@router.post('/confirm')
def confirm(request: HttpConfirmation, app=Depends(current_application)):
    return app.confirm(request)


@router.post('/actions')
def execute(request: HttpAction, app=Depends(current_application)):
    return app.execute(request)


@router.post('/workflows/{workflow_id}/ocr')
def ocr(workflow_id: UUID, revision: int = Form(ge=1), file: UploadFile = File(...),
        region: str | None = Form(default=None, max_length=512), app=Depends(current_application),
        _session=Depends(require_permission('intake.ocr'))):
    if file.content_type not in CONTENT_TYPES:
        raise HTTPException(415, 'Chỉ hỗ trợ ảnh JPG, PNG hoặc WebP')
    suffix = Path(file.filename or 'image.png').suffix.lower()
    try:
        selected = ImageRegion.model_validate_json(region) if region else None
    except ValidationError:
        raise HTTPException(422, 'Vùng ảnh không hợp lệ') from None
    data = file.file.read(10 * 1024 * 1024 + 1)
    file.file.close()
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(413, 'Ảnh vượt quá giới hạn 10 MB')
    with tempfile.TemporaryDirectory(prefix='msa-core-ocr-') as temporary:
        image = Path(temporary) / ('upload' + suffix)
        image.write_bytes(data)
        return ocr_intake.preview(app, workflow_id, revision, image, region=selected)


class OcrReviewRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    workflow_id: UUID
    revision: int = Field(ge=1)
    entry_version_id: UUID
    medication: Medication


@router.post('/ocr/edit')
def edit_ocr(request: OcrReviewRequest, app=Depends(current_application)):
    return ocr_intake.edit(app, request.workflow_id, request.revision, request.entry_version_id, request.medication)
