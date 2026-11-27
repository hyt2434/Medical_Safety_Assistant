from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator
from apps.backend.api.deps import require_permission, current_session
from apps.backend.api.routes.domains import domain_repository
from module4_hcp.service import HcpService

router = APIRouter(prefix='/api/v1/hcp', tags=['HCP collaboration'])
patient = Depends(require_permission('patient.workspace'))
clinician = Depends(require_permission('clinical.case_review'))


@router.get('/capabilities')
def capabilities(session=Depends(current_session)):
    import os
    from shared.auth.settings import core_database_dsn
    # An explicitly unconfigured development Core is preview mode. A failed
    # request to a configured Core must never silently display synthetic data.
    return {'preview': not core_database_dsn() and os.environ.get('AUTH_ENV') != 'production'}


class CaseRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: Literal['SAFETY', 'SCHEDULE']
    assessment_id: UUID | None = None
    schedule_id: UUID | None = None
    hcp_id: UUID
    consent: Literal[True]

    @field_validator('consent', mode='before')
    @classmethod
    def explicit_consent(cls, value):
        if value is not True:
            raise ValueError('Explicit consent required')
        return value

    @model_validator(mode='after')
    def context(self):
        if self.kind == 'SAFETY' and (not self.assessment_id or self.schedule_id):
            raise ValueError('Safety case requires assessment only')
        if self.kind == 'SCHEDULE' and not self.schedule_id:
            raise ValueError('Schedule case requires a schedule')
        return self


class MessageRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    text: str = Field(min_length=1, max_length=5000)


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    decision: Literal['APPROVED', 'CHANGES_REQUESTED', 'REJECTED']
    notes: str = Field(min_length=1, max_length=5000)


@router.get('/providers', dependencies=[patient])
def providers(repo=Depends(domain_repository)):
    return HcpService(repo).providers()


@router.post('/cases', dependencies=[patient], status_code=201)
def create(body: CaseRequest, repo=Depends(domain_repository)):
    return HcpService(repo).create(**body.model_dump())


@router.get('/cases/mine', dependencies=[patient])
def mine(repo=Depends(domain_repository)):
    return HcpService(repo).cases(mine=True)


@router.get('/cases', dependencies=[clinician])
def queue(repo=Depends(domain_repository)):
    return HcpService(repo).cases()


@router.get('/cases/{case_id}')
def detail(case_id: UUID, repo=Depends(domain_repository)):
    return HcpService(repo).detail(case_id)


@router.post('/cases/{case_id}/messages', status_code=201)
def message(case_id: UUID, body: MessageRequest, repo=Depends(domain_repository)):
    return HcpService(repo).message(case_id, body.text)
