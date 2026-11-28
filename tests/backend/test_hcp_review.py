"""Review HTTP contract with real Auth; service atomicity with isolated storage.

These tests do not claim PostgreSQL permits HCP case closure. The existing
marked-database integration test covers that contract when configured.
"""
from contextlib import contextmanager
from copy import deepcopy
from hashlib import sha256
from unittest.mock import Mock
from uuid import uuid4

import pytest

from apps.backend.api.app import app
from apps.backend.api.routes.domains import domain_repository
from module4_hcp.service import HcpService
from tests.backend.test_rbac import client, login


@pytest.fixture
def repo_override():
    repo = object()
    app.dependency_overrides[domain_repository] = lambda: repo
    try:
        yield repo
    finally:
        app.dependency_overrides.pop(domain_repository, None)


def test_review_route_dispatches_validated_request(client, repo_override, monkeypatch):
    case_id, outcome_id = uuid4(), uuid4()
    review = Mock(return_value={'id': str(outcome_id), 'decision': 'APPROVED'})
    monkeypatch.setattr(HcpService, 'review', review)
    assert login(client, 'multi', 'Multi-role-2026').status_code == 200
    assert client.post('/api/auth/switch-context', json={'context': 'hcp'}).status_code == 200
    response = client.post(f'/api/v1/hcp/cases/{case_id}/review', json={
        'decision': 'APPROVED', 'notes': '  Reviewed exact schedule  ',
    })
    assert response.status_code == 201
    assert response.json() == {'id': str(outcome_id), 'decision': 'APPROVED'}
    review.assert_called_once_with(case_id, 'APPROVED', 'Reviewed exact schedule')


def test_review_denies_anonymous_and_patient_before_service(client, repo_override, monkeypatch):
    review = Mock()
    monkeypatch.setattr(HcpService, 'review', review)
    path = f'/api/v1/hcp/cases/{uuid4()}/review'
    body = {'decision': 'APPROVED', 'notes': 'Not a clinician'}
    assert client.post(path, json=body).status_code == 401
    assert login(client).status_code == 200
    assert client.post(path, json=body).status_code == 403
    review.assert_not_called()


@pytest.mark.parametrize('body', [
    {'decision': 'UNASSESSED', 'notes': 'Unsupported decision'},
    {'decision': 'APPROVED', 'notes': '   '},
    {'decision': 'APPROVED', 'notes': 'Review', 'reviewer_id': str(uuid4())},
])
def test_review_rejects_invalid_body(client, repo_override, monkeypatch, body):
    review = Mock()
    monkeypatch.setattr(HcpService, 'review', review)
    login(client, 'multi', 'Multi-role-2026')
    client.post('/api/auth/switch-context', json={'context': 'hcp'})
    assert client.post(f'/api/v1/hcp/cases/{uuid4()}/review', json=body).status_code == 422
    review.assert_not_called()


class ReviewStorage:
    """Transactional storage double that exposes a partially committed outcome."""
    def __init__(self, failure=None):
        self.owner = uuid4()
        self.outcomes = []
        self.status = 'OPEN'
        self.active = False
        self.failure = failure

    @contextmanager
    def transaction(self):
        before = deepcopy(self.outcomes), self.status
        self.active = True
        try:
            yield
        except Exception:
            self.outcomes, self.status = before
            raise
        finally:
            self.active = False

    def record_review(self, case, decision, evidence, *, notes):
        assert self.active
        row = {'id': uuid4(), 'case_id': case, 'decision': decision,
               'evidence': evidence, 'notes': notes}
        self.outcomes.append(row)
        return row

    def _one(self, query, params):
        assert self.active and len(self.outcomes) == 1
        assert params == (self.outcomes[0]['case_id'], self.owner)
        assert "status='CLOSED'" in query and 'closed_at=clock_timestamp()' in query
        if self.failure == 'guard':
            raise PermissionError('Existing owner-only database guard')
        if self.failure == 'missing':
            return None
        self.status = 'CLOSED'
        return {'id': params[0]}


def test_service_records_review_evidence_and_closes_in_one_transaction():
    repo, case_id = ReviewStorage(), uuid4()
    result = HcpService(repo).review(case_id, 'APPROVED', 'Exact schedule reviewed')
    assert repo.status == 'CLOSED' and repo.outcomes == [result]
    assert result['evidence']['schema'] == 'review-evidence.v1'
    assert result['evidence']['sources'][0]['sha256'] == sha256(
        b'APPROVED\nExact schedule reviewed').hexdigest()


@pytest.mark.parametrize('failure,error', [('guard', PermissionError), ('missing', ValueError)])
def test_service_rolls_back_outcome_if_closure_fails(failure, error):
    repo = ReviewStorage(failure)
    with pytest.raises(error):
        HcpService(repo).review(uuid4(), 'APPROVED', 'Exact schedule reviewed')
    assert repo.outcomes == [] and repo.status == 'OPEN'
