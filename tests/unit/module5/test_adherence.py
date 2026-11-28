from datetime import datetime, timezone
import pytest
from module5_reminders.calculations import occurrences, adherence


def instant(value):
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def schedule(**changes):
    return {'id': 's1', 'name': 'Medication', 'timezone': 'Asia/Ho_Chi_Minh',
            'verification_status': 'PATIENT_CONFIRMED', 'schedule_details': {'times': ['08:00', '20:00']}, **changes}


def test_local_day_and_future_doses_not_in_denominator():
    now = instant('2026-11-27T09:00:00+07:00')
    rows = occurrences([schedule()], [], now)
    assert [r['scheduled_for'].hour for r in rows] == [1, 13]
    assert [r['due'] for r in rows] == [True, False]
    assert adherence([schedule()], [], now, 1) == {'days': 1, 'taken': 0, 'total_due': 1, 'rate': 0}


def test_corrections_replace_original_and_skipped_remains_in_denominator():
    now = instant('2026-11-27T23:00:00+07:00')
    records = [{'id': 'r1', 'schedule_id': 's1', 'scheduled_for': instant('2026-11-27T08:00:00+07:00'), 'dose_status': 'TAKEN'},
               {'id': 'r2', 'schedule_id': 's1', 'scheduled_for': instant('2026-11-27T01:00:00+00:00'), 'dose_status': 'SKIPPED', 'supersedes_record_id': 'r1'}]
    assert occurrences([schedule()], records, now)[0]['record_id'] == 'r2'
    assert adherence([schedule()], records, now, 1)['rate'] == 0


def test_seven_calendar_days_and_no_doses_before_creation_instant():
    now = instant('2026-11-27T09:00:00+07:00')
    assert adherence([schedule()], [], now)['total_due'] == 13
    assert adherence([schedule(created_at=instant('2026-11-26T10:00:00+07:00'))], [], now)['total_due'] == 2


def test_superseded_schedule_keeps_historical_doses_only():
    now = instant('2026-11-27T23:00:00+07:00')
    old = schedule(effective_until=instant('2026-11-27T12:00:00+07:00'))
    records = [{'id': 'taken', 'schedule_id': 's1', 'scheduled_for': instant('2026-11-27T08:00:00+07:00'), 'dose_status': 'TAKEN'}]
    result = adherence([old], records, now, 1)
    assert result['total_due'] == 1 and result['rate'] == 1


def test_empty_and_unverified_are_not_zero_percent():
    now = instant('2026-11-27T09:00:00+07:00')
    assert adherence([], [], now)['rate'] is None
    assert occurrences([schedule(verification_status='UNVERIFIED')], [], now) == []


def test_day_is_schedule_local_not_utc():
    rows = occurrences([schedule()], [], instant('2026-11-26T23:00:00Z'))
    assert rows[0]['scheduled_for'] == instant('2026-11-27T01:00:00Z')
    assert not rows[0]['due']


def test_dst_gap_is_skipped_and_fold_is_one_occurrence():
    s = schedule(timezone='America/New_York', schedule_details={'times': ['01:30', '02:30']})
    gap = occurrences([s], [], instant('2026-03-08T20:00:00Z'))
    assert len(gap) == 1
    fold = occurrences([s], [], instant('2026-11-01T20:00:00Z'))
    assert len(fold) == 2
    assert fold[0]['scheduled_for'] == instant('2026-11-01T05:30:00Z')


@pytest.mark.parametrize('days', [0, -1, 367])
def test_invalid_window(days):
    with pytest.raises(ValueError):
        adherence([], [], datetime.now(timezone.utc), days)


@pytest.mark.parametrize('minutes,expected', [(0, 0), (59, 0), (60, 1), (61, 1)])
def test_adherence_has_a_full_hour_grace_period(minutes, expected):
    from datetime import timedelta
    due = instant('2026-11-27T08:00:00+07:00')
    row = schedule(schedule_details={'times': ['08:00']})
    for status in ['TAKEN', 'MISSED', 'SKIPPED']:
        records = [{'id': 'record', 'schedule_id': 's1', 'scheduled_for': due, 'dose_status': status}]
        result = adherence([row], records, due + timedelta(minutes=minutes), 1)
        assert result['total_due'] == expected
        assert result['taken'] == (expected if status == 'TAKEN' else 0)
        if not expected:
            assert result['rate'] is None
