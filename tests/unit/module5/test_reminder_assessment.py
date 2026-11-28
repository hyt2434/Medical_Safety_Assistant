from contextlib import nullcontext
from unittest.mock import Mock

import pytest

from module5_reminders.service import ReminderService


def repository(status='HCP_VERIFIED'):
    repo = Mock(owner='owner')
    repo.domain_transaction = nullcontext
    repo._owned.return_value = {'id': 'schedule', 'entry_version_id': 'entry',
        'verification_status': status, 'content_digest': 'digest',
        'verification_evidence': {'review_outcome_id': 'outcome'}}
    return repo


def test_hcp_reminder_uses_exact_reviewed_assessment_not_latest(monkeypatch):
    latest = Mock(side_effect=AssertionError('Must not use the newer assessment'))
    monkeypatch.setattr('module5_reminders.service.latest_assessment', latest)
    repo = repository()
    repo._one.return_value = {'id': 'reviewed-assessment'}
    ReminderService(repo).reminder('schedule', True)
    query, params = repo._one.call_args.args
    assert params == ('outcome', 'owner', 'schedule', 'digest', 'entry')
    assert "a.execution_status='COMPLETED'" in query
    assert 'se.entry_version_id=%s' in query
    assert repo.set_reminder.call_args.kwargs['assessment'] == 'reviewed-assessment'


def test_missing_or_invalid_reviewed_assessment_rejects_enable():
    repo = repository()
    repo._one.return_value = None
    with pytest.raises(ValueError, match='Reviewed assessment'):
        ReminderService(repo).reminder('schedule', True)
    repo.set_reminder.assert_not_called()


def test_patient_confirmed_reminder_uses_latest_assessment(monkeypatch):
    latest = Mock(return_value='latest')
    monkeypatch.setattr('module5_reminders.service.latest_assessment', latest)
    repo = repository('PATIENT_CONFIRMED')
    ReminderService(repo).reminder('schedule', True)
    latest.assert_called_once_with(repo, 'entry')
    assert repo.set_reminder.call_args.kwargs['assessment'] == 'latest'


def test_disabling_does_not_require_a_reviewed_assessment():
    repo = repository()
    ReminderService(repo).reminder('schedule', False)
    repo._one.assert_not_called()
    assert repo.set_reminder.call_args.kwargs['assessment'] is None


def test_unverified_schedule_cannot_enable():
    repo = repository('UNVERIFIED')
    with pytest.raises(ValueError, match='verified schedule'):
        ReminderService(repo).reminder('schedule', True)
    repo.set_reminder.assert_not_called()
