from contextlib import contextmanager, nullcontext
from unittest.mock import Mock
from uuid import uuid4

from module4_hcp.service import HcpService
from shared.db.errors import DomainConflict
import pytest


def directory(monkeypatch, candidates, linked, owner):
    db = Mock()
    db.execute.return_value.all.return_value = candidates

    @contextmanager
    def auth_transaction():
        yield db

    monkeypatch.setattr('shared.auth.db.transaction', auth_transaction)
    repo = Mock(owner=owner)
    repo.domain_transaction = nullcontext
    repo._all.return_value = [{'id': uid} for uid in linked]
    return HcpService(repo), repo, db


def test_provider_directory_batches_core_identity_validation(monkeypatch):
    owner, linked, missing = uuid4(), uuid4(), uuid4()
    service, repo, db = directory(monkeypatch,
        [(str(owner), 'Self'), (str(linked), 'Linked'), (str(missing), 'Missing')], [linked], owner)
    assert service.providers() == [{'id': str(linked), 'full_name': 'Linked'}]
    repo._all.assert_called_once_with('SELECT id FROM identity.users WHERE id = ANY(%s)', ([linked, missing],))
    repo._one.assert_not_called()
    query = str(db.execute.call_args.args[0])
    assert 'revoked_at IS NULL' in query and 'expires_at' in query and 'account_status' in query


def test_empty_directory_needs_no_core_queries(monkeypatch):
    service, repo, _ = directory(monkeypatch, [], [], uuid4())
    assert service.providers() == []
    repo._all.assert_not_called()


def test_provider_lookup_filters_auth_to_requested_identity(monkeypatch):
    requested = uuid4()
    service, repo, db = directory(monkeypatch, [(str(requested), 'Provider')], [requested], uuid4())
    assert len(service.providers(hcp_id=requested)) == 1
    params = db.execute.call_args.args[0].compile().params
    assert params['user_id_1'] == str(requested)
    repo._all.assert_called_once_with('SELECT id FROM identity.users WHERE id = ANY(%s)', ([requested],))


def test_case_creation_checks_only_requested_provider():
    repo = Mock()
    repo.domain_transaction = nullcontext
    repo._owned.return_value = {'execution_status': 'COMPLETED'}
    repo.create_case.return_value = {'id': 'case'}
    service = HcpService(repo)
    service.providers = Mock(return_value=[{'id': 'requested'}])
    service.create('SAFETY', 'requested', True, assessment_id='assessment')
    service.providers.assert_called_once_with(hcp_id='requested')


def test_unlinked_or_inactive_requested_provider_is_a_conflict():
    service = HcpService(Mock())
    service.providers = Mock(return_value=[])
    with pytest.raises(DomainConflict):
        service.create('SAFETY', 'requested', True, assessment_id='assessment')
    service.repo.create_case.assert_not_called()
