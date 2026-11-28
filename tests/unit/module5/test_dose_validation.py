from contextlib import nullcontext
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from module5_reminders.calculations import occurrences, verified_schedule_periods
from module5_reminders.service import ReminderService
from tests.unit.module5.test_service import schedules, at


@pytest.mark.parametrize('timestamp,verified,until', [
    (at(8), at(9), None),  # Before verification, although on the schedule clock.
    (at(19), at(1), None),
    (at(20).replace(second=1), at(1), None),
    (at(20), at(1), at(12)),  # Superseded before the requested occurrence.
])
def test_dose_rejects_non_occurrences_without_writing(timestamp, verified, until):
    repo = Mock()
    repo.domain_transaction = nullcontext
    service = ReminderService(repo)
    row = {**schedules()[0], 'verified_at': verified, 'effective_until': until}
    service._dose_schedules = Mock(return_value=[row])
    with pytest.raises(ValueError, match='effective period'):
        service.dose('old', timestamp, 'TAKEN')
    repo.record_dose.assert_not_called()


def test_unverified_schedule_cannot_record_doses():
    repo = Mock()
    repo.domain_transaction = nullcontext
    service = ReminderService(repo)
    service._dose_schedules = Mock(return_value=verified_schedule_periods(schedules()))
    with pytest.raises(ValueError):
        service.dose('new', at(8), 'TAKEN')
    repo.record_dose.assert_not_called()


def test_valid_historical_correction_keeps_original_schedule_id():
    repo = Mock()
    repo.domain_transaction = nullcontext
    service = ReminderService(repo)
    row = {**schedules()[0], 'effective_until': at(12)}
    service._dose_schedules = Mock(return_value=[row])
    service.dose('old', at(8), 'SKIPPED', supersedes='prior')
    repo.record_dose.assert_called_once_with('old', at(8), 'SKIPPED', supersedes='prior')


def test_dst_repeated_time_accepts_only_the_generated_occurrence():
    repo = Mock()
    repo.domain_transaction = nullcontext
    service = ReminderService(repo)
    row = {**schedules()[0], 'timezone': 'America/New_York', 'schedule_details': {'times': ['01:30']},
           'created_at': datetime(2020, 10, 31, tzinfo=timezone.utc),
           'verified_at': datetime(2020, 10, 31, tzinfo=timezone.utc)}
    service._dose_schedules = Mock(return_value=[row])
    first = datetime(2020, 11, 1, 5, 30, tzinfo=timezone.utc)
    service.dose('old', first, 'TAKEN')
    with pytest.raises(ValueError):
        service.dose('old', first.replace(hour=6), 'TAKEN')
    assert repo.record_dose.call_count == 1


@pytest.mark.parametrize('verified', [None, at(9)])
def test_occurrences_start_at_verification_or_creation_instant(verified):
    row = {**schedules()[0], 'created_at': at(9), 'verified_at': verified}
    assert [r['time'] for r in occurrences([row], [], at(21))] == ['20:00']


def test_duplicate_schedule_creation_locks_entry_and_rejects_without_writes():
    repo = Mock(owner='owner')
    repo.domain_transaction = nullcontext
    repo._owned.return_value = {'id': 'entry', 'item_id': 'item', 'version_no': 2, 'confirmed_at': at(1)}
    repo._one.side_effect = [None, {'id': 'active-on-first-version'}]
    with pytest.raises(ValueError, match='active schedule already exists'):
        ReminderService(repo).create('entry', ['08:00'], 'one', 'UTC', True)
    assert repo._owned.call_args_list[1].args == ('intake_items', 'item')
    assert repo._owned.call_args_list[1].kwargs == {'lock': True}
    assert repo._one.call_args.args[1] == ('owner', 'item')
    assert 'e.item_id=%s' in repo._one.call_args.args[0]
    assert repo.mock_calls[0][0] == '_owned'
    repo.save_schedule.assert_not_called()


@pytest.mark.parametrize('confirmed,newer,message', [(False, False, 'must be confirmed'), (True, True, 'newest')])
def test_schedule_creation_rejects_unconfirmed_and_stale_entries(confirmed, newer, message):
    repo = Mock(owner='owner')
    repo.domain_transaction = nullcontext
    repo._owned.return_value = {'id': 'entry', 'item_id': 'item', 'version_no': 1,
                               'confirmed_at': at(1) if confirmed else None}
    repo._one.return_value = {'id': 'newer'} if newer else None
    with pytest.raises(ValueError, match=message):
        ReminderService(repo).create('entry', ['08:00'], 'one', 'UTC', True)
    repo.save_schedule.assert_not_called()


def test_schedule_creation_accepts_confirmed_latest_entry_without_existing_schedule():
    repo = Mock(owner='owner')
    repo.domain_transaction = nullcontext
    repo._owned.return_value = {'id': 'entry', 'item_id': 'item', 'version_no': 2, 'confirmed_at': at(1)}
    repo._one.return_value = None
    repo.save_schedule.return_value = {'id': 'schedule', 'content_digest': 'digest'}
    ReminderService(repo).create('entry', ['08:00'], 'one', 'UTC', True)
    repo.save_schedule.assert_called_once()
    repo.confirm_schedule.assert_called_once()
