import asyncio
from contextlib import contextmanager, nullcontext
import json
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException, Request
from psycopg.pq import TransactionStatus

from apps.backend.api.app import http_error
from module4_hcp.service import HcpService
from shared.db.domain_repository import DomainRepository


class Connection:
    autocommit = True

    def __init__(self):
        self.info = SimpleNamespace(transaction_status=TransactionStatus.IDLE)
        self.execute = Mock()

    @contextmanager
    def transaction(self):
        previous = self.info.transaction_status
        self.info.transaction_status = TransactionStatus.INTRANS
        try:
            yield
        finally:
            self.info.transaction_status = previous


def test_domain_composition_does_not_relax_inherited_core_transaction_guard():
    repo = DomainRepository(Connection(), authenticated_actor=uuid4())
    repo._insert = Mock(return_value={'id': 'cabinet'})
    with repo.domain_transaction():
        assert repo.add_cabinet_item('Synthetic box') == {'id': 'cabinet'}
        with pytest.raises(RuntimeError, match='outer transaction'):
            repo.create_conversation()
        with pytest.raises(RuntimeError, match='outer transaction'):
            with repo.transaction():
                pytest.fail('Strict transaction unexpectedly nested')
    assert repo._domain_transaction_depth == 0
    assert repo.create_conversation() == {'id': 'cabinet'}


@pytest.mark.parametrize('outer', ['connection', 'strict'])
def test_domain_methods_cannot_join_arbitrary_outer_transactions(outer):
    repo = DomainRepository(Connection(), authenticated_actor=uuid4())
    context = repo.db.transaction() if outer == 'connection' else repo.transaction()
    with context:
        with pytest.raises(RuntimeError, match='outer transaction'):
            repo.add_cabinet_item('Forbidden nested write')
    assert repo._domain_transaction_depth == 0


def test_domain_transaction_depth_resets_after_nested_failure():
    repo = DomainRepository(Connection(), authenticated_actor=uuid4())
    with pytest.raises(ValueError):
        with repo.domain_transaction():
            with repo.domain_transaction():
                raise ValueError('rollback')
    assert repo._domain_transaction_depth == 0
    with repo.transaction():
        assert repo.db.info.transaction_status == TransactionStatus.INTRANS


def test_structured_http_error_without_message_keeps_error_response():
    response = asyncio.run(http_error(Request({'type': 'http'}),
        HTTPException(409, detail={'code': 'HCP_REVIEW_REQUIRED'})))
    assert response.status_code == 409
    body = json.loads(response.body)
    assert body['detail'] == body['error']['message'] == 'Request failed'
    assert body['error']['code'] == 'HCP_REVIEW_REQUIRED'


@pytest.mark.parametrize('status', ['RUNNING', 'FAILED', None])
def test_safety_case_rejects_incomplete_or_missing_assessment(status):
    repo = Mock()
    repo.domain_transaction = nullcontext
    repo._owned.return_value = {'execution_status': status}
    service = HcpService(repo)
    service.providers = Mock(return_value=[{'id': 'hcp'}])
    with pytest.raises(ValueError, match='completed assessment'):
        service.create('SAFETY', 'hcp', True, assessment_id='assessment' if status else None)
    repo.create_case.assert_not_called()
    repo.grant_case_access.assert_not_called()


def test_safety_case_accepts_completed_owned_assessment():
    repo = Mock()
    repo.domain_transaction = nullcontext
    repo._owned.return_value = {'execution_status': 'COMPLETED'}
    repo.create_case.return_value = {'id': 'case'}
    service = HcpService(repo)
    service.providers = Mock(return_value=[{'id': 'hcp'}])
    service.create('SAFETY', 'hcp', True, assessment_id='assessment')
    repo._owned.assert_called_once_with('safety_assessments', 'assessment')
    repo.create_case.assert_called_once_with('SAFETY', assessment='assessment', schedule=None)
    repo.assign_case.assert_called_once_with('case', 'hcp')
