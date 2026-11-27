from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastapi import APIRouter, Depends, Query
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StrictBool, field_validator
from apps.backend.api.deps import require_permission
from apps.backend.api.routes.domains import domain_repository
from module5_reminders.service import ReminderService

router = APIRouter(prefix='/api/v1/reminders', tags=['Medication reminders'],
                   dependencies=[Depends(require_permission('patient.workspace'))])


class ScheduleRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    entry_version_id: UUID
    times: list[str] = Field(min_length=1, max_length=24)
    dose_raw: str = Field(min_length=1, max_length=500)
    timezone: str
    confirm: Literal[True]

    @field_validator('confirm', mode='before')
    @classmethod
    def explicit_confirmation(cls, value):
        if value is not True:
            raise ValueError('Explicit confirmation required')
        return value

    @field_validator('times')
    @classmethod
    def valid_times(cls, values):
        import re
        if len(set(values)) != len(values) or any(not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', t) for t in values):
            raise ValueError('Unique HH:MM times required')
        return sorted(values)

    @field_validator('timezone')
    @classmethod
    def valid_zone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError('IANA timezone required') from None
        return value


class ReminderRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    enabled: StrictBool


class DoseRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    schedule_id: UUID
    scheduled_for: AwareDatetime
    status: Literal['TAKEN', 'MISSED', 'SKIPPED']
    supersedes: UUID | None = None


@router.get('/entries')
def entries(repo=Depends(domain_repository)):
    return ReminderService(repo).entries()


@router.post('/schedules', status_code=201)
def create(body: ScheduleRequest, repo=Depends(domain_repository)):
    return ReminderService(repo).create(**body.model_dump())


@router.get('/schedules')
def schedules(repo=Depends(domain_repository)):
    return ReminderService(repo).schedules()


@router.put('/schedules/{schedule_id}/reminder')
def reminder(schedule_id: UUID, body: ReminderRequest, repo=Depends(domain_repository)):
    return ReminderService(repo).reminder(schedule_id, body.enabled)


@router.post('/schedules/{schedule_id}/activate')
def activate(schedule_id: UUID, repo=Depends(domain_repository)):
    return ReminderService(repo).activate(schedule_id)


@router.get('/today')
def today(repo=Depends(domain_repository)):
    return ReminderService(repo).today()


@router.get('/history')
def history(days: int = Query(7, ge=1, le=366), repo=Depends(domain_repository)):
    return ReminderService(repo).history(days)


@router.get('/adherence')
def adherence(days: int = Query(7, ge=1, le=366), repo=Depends(domain_repository)):
    return ReminderService(repo).adherence(days)


@router.post('/doses', status_code=201)
def dose(body: DoseRequest, repo=Depends(domain_repository)):
    return ReminderService(repo).dose(**body.model_dump())
