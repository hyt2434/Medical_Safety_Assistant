from unittest.mock import Mock
from uuid import uuid4
from zoneinfo import ZoneInfoNotFoundError

import psycopg
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.exc import ArgumentError
from shared.db.errors import DomainConflict

from apps.backend.api.routes import domains, reminders


@pytest.mark.parametrize('error', [OSError, ValueError, ZoneInfoNotFoundError])
def test_timezone_lookup_failure_is_validation_error(monkeypatch, error):
    monkeypatch.setattr(reminders, 'ZoneInfo', Mock(side_effect=error('bad zone')))
    with pytest.raises(ValidationError, match='IANA timezone required'):
        reminders.ScheduleRequest(
            entry_version_id=uuid4(), times=['08:00'], dose_raw='one',
            timezone='bad-zone', confirm=True,
        )


@pytest.fixture
def domain_setup(monkeypatch):
    monkeypatch.setattr(domains, 'core_owner', Mock(return_value=uuid4()))
    monkeypatch.setattr(domains, 'core_database_dsn', Mock(return_value='configured'))
    connect = Mock()
    monkeypatch.setattr(domains.psycopg, 'connect', connect)
    return {'contextPermissions': ['patient.workspace'], 'account': {'id': str(uuid4())}}, connect


@pytest.mark.parametrize('source', ['core_owner', 'core_database_dsn'])
@pytest.mark.parametrize('error', [ValueError, TypeError, ArgumentError, psycopg.ProgrammingError])
def test_configuration_failure_is_503(monkeypatch, domain_setup, source, error):
    session, connect = domain_setup
    monkeypatch.setattr(domains, source, Mock(side_effect=error('private config')))
    with pytest.raises(HTTPException) as caught:
        next(domains.domain_repository(session))
    assert caught.value.status_code == 503
    assert 'private config' not in caught.value.detail
    connect.assert_not_called()


def test_unlinked_owner_remains_403(monkeypatch, domain_setup):
    session, connect = domain_setup
    monkeypatch.setattr(domains, 'core_owner', Mock(side_effect=PermissionError))
    with pytest.raises(HTTPException) as caught:
        next(domains.domain_repository(session))
    assert caught.value.status_code == 403
    connect.assert_not_called()


def test_domain_conflict_remains_409(monkeypatch, domain_setup):
    from unittest.mock import MagicMock
    session, connect = domain_setup
    connect.return_value = MagicMock()
    monkeypatch.setattr(domains, 'DomainRepository', Mock())
    dependency = domains.domain_repository(session)
    next(dependency)
    with pytest.raises(HTTPException) as caught:
        dependency.throw(DomainConflict('Domain conflict'))
    assert caught.value.status_code == 409
    assert caught.value.detail == 'Domain conflict'


def test_unexpected_value_error_is_500_without_leaking_details(monkeypatch, domain_setup):
    from unittest.mock import MagicMock
    session, connect = domain_setup
    connect.return_value = MagicMock()
    monkeypatch.setattr(domains, 'DomainRepository', Mock())
    dependency = domains.domain_repository(session)
    next(dependency)
    with pytest.raises(HTTPException) as caught:
        dependency.throw(ValueError('private implementation detail'))
    assert caught.value.status_code == 500
    assert caught.value.detail == 'Internal server error'
