"""Review HTTP contract with real Auth; clinician writes outcomes only."""
from hashlib import sha256
from contextlib import nullcontext
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


def review_repo():
    repo = Mock(spec=['record_review', 'domain_transaction', '_one'])
    repo.domain_transaction = nullcontext
    repo._one.side_effect = [{'id': 'case'}, None]
    return repo


def test_service_records_evidence_without_updating_patient_case():
    repo = review_repo()
    case_id = uuid4()
    repo.record_review.return_value = {'id': uuid4(), 'decision': 'APPROVED'}
    result = HcpService(repo).review(case_id, 'APPROVED', 'Exact schedule reviewed')
    assert result == repo.record_review.return_value
    args, kwargs = repo.record_review.call_args
    assert args[:2] == (case_id, 'APPROVED')
    assert kwargs == {'notes': 'Exact schedule reviewed'}
    assert args[2]['schema'] == 'review-evidence.v1'
    assert args[2]['sources'][0]['sha256'] == sha256(
        b'APPROVED\nExact schedule reviewed').hexdigest()
    assert 'FOR UPDATE' in repo._one.call_args_list[0].args[0]
    assert all('UPDATE msa.' not in call.args[0] for call in repo._one.call_args_list)


@pytest.mark.parametrize('error', [PermissionError, ValueError])
def test_service_propagates_review_denial_without_other_writes(error):
    repo = review_repo()
    repo.record_review.side_effect = error('Review denied')
    with pytest.raises(error):
        HcpService(repo).review(uuid4(), 'APPROVED', 'Exact schedule reviewed')
    repo.record_review.assert_called_once()


@pytest.mark.parametrize('decision', ['APPROVED', 'REJECTED', 'CHANGES_REQUESTED'])
def test_review_rejects_second_outcome_for_open_case(decision):
    repo = review_repo()
    repo._one.side_effect = [{'id': 'case', 'status': 'OPEN'}, {'id': 'outcome', 'decision': decision}]
    with pytest.raises(ValueError, match='already has a review outcome'):
        HcpService(repo).review(uuid4(), 'APPROVED', 'Second review')
    repo.record_review.assert_not_called()


def test_review_checks_case_access_before_outcome():
    repo = review_repo()
    repo._one.side_effect = [None]
    with pytest.raises(PermissionError, match='Case access denied'):
        HcpService(repo).review(uuid4(), 'APPROVED', 'Denied')
    repo.record_review.assert_not_called()
    repo._one.assert_called_once()
