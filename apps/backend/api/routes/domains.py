"""Shared authenticated connection and error boundary for domain APIs."""
import psycopg
from sqlalchemy.exc import ArgumentError
from fastapi import Depends, HTTPException
from apps.backend.api.deps import current_session
from shared.auth.core_owner import core_owner
from shared.auth.settings import core_database_dsn
from shared.db.domain_repository import DomainRepository


def domain_repository(session=Depends(current_session)):
    permissions = session['contextPermissions']
    if not {'patient.workspace', 'clinical.case_review'}.intersection(permissions):
        raise HTTPException(403, 'Workspace permission required')
    try:
        owner = core_owner(session['account']['id'])
        dsn = core_database_dsn()
    except PermissionError:
        raise HTTPException(403, 'Resource access denied') from None
    except (ValueError, TypeError, ArgumentError, psycopg.Error):
        raise HTTPException(503, 'Core database configuration is invalid') from None
    if not dsn:
        raise HTTPException(503, 'Core database is not configured')
    try:
        with psycopg.connect(dsn, autocommit=True, connect_timeout=5) as connection:
            if not connection.execute('SELECT id FROM identity.users WHERE id=%s', (owner,)).fetchone():
                raise HTTPException(403, 'Core account link required')
            yield DomainRepository(connection, authenticated_actor=owner, permissions=permissions)
    except PermissionError:
        raise HTTPException(403, 'Resource access denied') from None
    except ValueError as error:
        raise HTTPException(409, str(error)) from None
    except psycopg.Error as error:
        message = error.diag.message_primary or ''
        if 'HCP approval' in message:
            raise HTTPException(409, {'code': 'HCP_REVIEW_REQUIRED', 'message': 'This schedule needs HCP approval'}) from None
        if error.sqlstate and (error.sqlstate.startswith('23') or error.sqlstate in ('P0001', 'P0002')):
            raise HTTPException(409, 'Operation conflicts with the current record or its verification requirements') from None
        raise HTTPException(503, 'Core database is unavailable') from None
