from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from module5_reminders.calculations import occurrences, verified_schedule_periods
from module5_reminders.service import ReminderService


def at(hour):
    return datetime(2020, 11, 28, hour, tzinfo=timezone.utc)


def schedules():
    original = dict(id='old', entry_version_id='entry', name='Medicine',
                    timezone='UTC', schedule_details={'times': ['08:00', '20:00']},
                    verification_status='PATIENT_CONFIRMED', created_at=at(0),
                    verified_at=at(1), supersedes_schedule_id=None, reminder_enabled=True)
    proposal = {**original, 'id': 'new', 'supersedes_schedule_id': 'old',
                'verification_status': 'UNVERIFIED', 'schedule_origin': 'PROPOSED_CHANGE',
                'created_at': at(7), 'verified_at': None}
    return [original, proposal]


def test_pending_revision_preserves_today_history_adherence_and_recordable_id():
    repo = Mock()
    service = ReminderService(repo)
    source = schedules()
    service.schedules = Mock(return_value=source)
    service.records = Mock(return_value=[])
    today = service.today(at(21))
    assert [d['schedule_id'] for d in today] == ['old', 'old']
    assert service.history(1, at(21)) == today
    assert service.adherence(1, at(21))['total_due'] == 2
    assert all(call.kwargs == {'include_history': True} for call in service.schedules.call_args_list)
    service.dose(today[0]['schedule_id'], today[0]['scheduled_for'], 'TAKEN')
    repo.record_dose.assert_called_once_with('old', at(8), 'TAKEN', supersedes=None)
    service.records.return_value = [dict(id='dose', schedule_id='old', scheduled_for=at(8), dose_status='TAKEN')]
    assert service.today(at(21))[0]['status'] == 'TAKEN'
    assert service.adherence(1, at(21))['rate'] == 0.5
    assert source == schedules()  # Pure selection must not mutate repository rows.


def test_revision_takes_over_at_verification_not_proposal_time():
    source = schedules()
    source[1].update(verification_status='HCP_VERIFIED', verified_at=at(12))
    rows = occurrences(verified_schedule_periods(source), [], at(21))
    assert [(r['schedule_id'], r['time']) for r in rows] == [('old', '08:00'), ('new', '20:00')]


def test_pending_chain_keeps_nearest_verified_ancestor_and_older_history():
    source = schedules()
    source.append({**source[1], 'id': 'last', 'supersedes_schedule_id': 'new'})
    assert [s['id'] for s in verified_schedule_periods(source)] == ['old']
    source[2].update(verification_status='HCP_VERIFIED', verified_at=at(12))
    rows = occurrences(verified_schedule_periods(source), [], at(21))
    assert [(r['schedule_id'], r['time']) for r in rows] == [('old', '08:00'), ('last', '20:00')]
    source.append({**source[1], 'id': 'pending', 'supersedes_schedule_id': 'last'})
    assert occurrences(verified_schedule_periods(source), [], at(21)) == rows


class ActivationRepo:
    def __init__(self, failure=None, decision='APPROVED', status='OPEN'):
        self.owner = 'patient'
        self.schedule = dict(id='new', entry_version_id='entry', schedule_origin='PROPOSED_CHANGE',
                             verification_status='UNVERIFIED', content_digest='digest')
        self.case = dict(id='case', user_id=self.owner, status=status)
        self.outcome = dict(id='outcome', case_id='case', decision=decision, assessment_id='reviewed-assessment')
        self.enabled = False
        self.failure = failure
        self.events = []

    @contextmanager
    def transaction(self):
        snapshot = deepcopy((self.schedule, self.case, self.enabled))
        try:
            yield
        except Exception:
            self.schedule, self.case, self.enabled = snapshot
            raise

    def _owned(self, table, identity, *, lock=False):
        assert lock
        row = self.schedule if table == 'medication_schedules' else self.case
        assert row['id'] == identity
        return row.copy()

    def _one(self, query, params):
        if 'FROM msa.medication_schedules WHERE supersedes_schedule_id' in query:
            return {'id': 'child'} if self.failure == 'superseded' else None
        if 'FROM msa.safety_assessments' in query:
            return {'id': 'assessment'}
        if 'FROM msa.review_outcomes' in query:
            assert params == ('new', self.owner, 'entry')
            assert "a.execution_status='COMPLETED'" in query and 'se.entry_version_id=%s' in query
            return self.outcome.copy()
        assert 'UPDATE msa.review_cases' in query
        assert params == ('case', 'patient') and 'user_id=%s' in query
        assert "status='CLOSED'" in query and 'closed_at=clock_timestamp()' in query
        self.events.append('close')
        if self.failure == 'close':
            return None
        self.case['status'] = 'CLOSED'
        return {'id': 'case'}

    def confirm_schedule(self, identity, digest, key, *, explicit_confirmation, review_outcome):
        assert (identity, digest, explicit_confirmation, review_outcome) == ('new', 'digest', True, 'outcome')
        self.events.append('confirm')
        self.schedule['verification_status'] = 'HCP_VERIFIED'

    def set_reminder(self, identity, *, enabled, assessment, preferences):
        assert identity == 'new' and enabled and assessment == 'reviewed-assessment'
        self.events.append('enable')
        if self.failure == 'enable':
            raise ValueError('Eligibility changed')
        self.enabled = True
        return {'enabled': True}


def test_patient_activation_confirms_enables_and_closes_atomically_and_retries():
    repo = ActivationRepo()
    service = ReminderService(repo)
    assert service.activate('new') == {'enabled': True}
    assert repo.events == ['confirm', 'enable', 'close']
    assert repo.case['status'] == 'CLOSED' and repo.enabled
    repo.events.clear()
    service.activate('new')
    assert repo.events == ['enable']  # Do not update an immutable closed case.


@pytest.mark.parametrize('failure', ['enable', 'close'])
def test_failed_activation_rolls_back_verification_reminder_and_closure(failure):
    repo = ActivationRepo(failure=failure)
    with pytest.raises(ValueError):
        ReminderService(repo).activate('new')
    assert repo.schedule['verification_status'] == 'UNVERIFIED'
    assert not repo.enabled and repo.case['status'] == 'OPEN'


@pytest.mark.parametrize('decision,status', [('REJECTED', 'OPEN'), ('APPROVED', 'CANCELLED')])
def test_unapproved_or_cancelled_case_cannot_activate(decision, status):
    repo = ActivationRepo(decision=decision, status=status)
    with pytest.raises(ValueError):
        ReminderService(repo).activate('new')
    assert repo.events == []


def test_activation_rejects_a_superseded_schedule_even_when_already_verified():
    repo = ActivationRepo(failure='superseded')
    repo.schedule['verification_status'] = 'HCP_VERIFIED'
    with pytest.raises(ValueError, match='superseded'):
        ReminderService(repo).activate('new')
    assert repo.events == []


def test_activation_uses_reviewed_assessment_not_latest(monkeypatch):
    import module5_reminders.service as module
    monkeypatch.setattr(module, 'latest_assessment', Mock(side_effect=AssertionError('Must use case assessment')))
    repo = ActivationRepo()
    assert ReminderService(repo).activate('new') == {'enabled': True}


@pytest.mark.parametrize('decision', ['REJECTED', 'CHANGES_REQUESTED', 'APPROVED', None])
def test_listing_keeps_verified_ancestor_and_pending_decision(decision):
    from module5_reminders.calculations import current_schedule_listing
    source = schedules()
    source[1]['review_decision'] = decision
    source.append({**source[1], 'id': 'leaf', 'supersedes_schedule_id': 'new'})
    before = deepcopy(source)
    repo = Mock()
    repo.transaction = __import__('contextlib').nullcontext
    repo._all.return_value = source
    listing = ReminderService(repo).schedules()
    assert len(listing) == 1 and listing[0]['id'] == 'old'
    assert listing[0]['pending_proposal']['id'] == 'leaf'
    assert listing[0]['pending_proposal']['review_decision'] == decision
    assert source == before
    assert ReminderService(repo).schedules(include_history=True) == source
    source[2].update(verification_status='HCP_VERIFIED', verified_at=at(12))
    assert [r['id'] for r in current_schedule_listing(source)] == ['leaf']
