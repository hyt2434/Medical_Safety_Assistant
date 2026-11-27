"""Pure local-calendar occurrence expansion and adherence calculations."""
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


def occurrences(schedules, records, now, days=1):
    """Expand local calendar days; use elapsed UTC instants for due comparisons.

    Nonexistent DST times are omitted; an ambiguous wall time occurs once (fold 0).
    Future doses today stay PENDING. Corrections replace, never double-count, doses.
    """
    if now.tzinfo is None or not 1 <= days <= 366:
        raise ValueError('Aware time and 1..366 days required')
    superseded = {str(r['supersedes_record_id']) for r in records if r.get('supersedes_record_id')}
    latest = {(str(r['schedule_id']), r['scheduled_for'].astimezone(timezone.utc)): r
              for r in records if str(r['id']) not in superseded}
    result = []
    for s in schedules:
        if s['verification_status'] == 'UNVERIFIED':
            continue
        zone = ZoneInfo(s['timezone'])
        today = now.astimezone(zone).date()
        for offset in range(days - 1, -1, -1):
            day = today - timedelta(days=offset)
            for clock in sorted(set(s['schedule_details']['times'])):
                local = datetime.combine(day, time.fromisoformat(clock), zone)
                instant = local.astimezone(timezone.utc)
                if instant.astimezone(zone).replace(tzinfo=None) != local.replace(tzinfo=None):
                    continue
                if s.get('created_at') and day < s['created_at'].astimezone(zone).date():
                    continue
                if s.get('supersedes_schedule_id') and s.get('created_at') and instant < s['created_at']:
                    continue
                if s.get('effective_until') and instant >= s['effective_until']:
                    continue
                record = latest.get((str(s['id']), instant))
                result.append({'schedule_id': s['id'], 'name': s.get('name', ''), 'time': clock,
                    'scheduled_for': instant, 'status': record['dose_status'] if record else 'PENDING',
                    'record_id': record['id'] if record else None, 'due': instant <= now,
                    'reminder_enabled': bool(s.get('reminder_enabled'))})
    return sorted(result, key=lambda row: (row['scheduled_for'], str(row['schedule_id'])))


def adherence(schedules, records, now, days=7):
    due = [r for r in occurrences(schedules, records, now, days) if r['due']]
    taken = sum(r['status'] == 'TAKEN' for r in due)
    return {'days': days, 'taken': taken, 'total_due': len(due),
            'rate': taken / len(due) if due else None}


