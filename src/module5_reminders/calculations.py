"""Pure local-calendar occurrence expansion and adherence calculations."""
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


def verified_schedule_periods(schedules):
    """Keep a verified ancestor effective until a descendant is verified.

    Pending revisions do not interrupt dose recording. Verification time, rather
    than proposal creation time, is the boundary between old and new doses.
    Traverse pending intermediates too, so revision chains retain their history.
    """
    by_id = {str(s['id']): s for s in schedules}
    verified = {key: {**s, 'effective_until': None} for key, s in by_id.items()
                if s['verification_status'] != 'UNVERIFIED'}
    for key, s in verified.items():
        parent = s.get('supersedes_schedule_id')
        if not parent:
            continue
        start = s.get('verified_at') or s.get('created_at')
        s['effective_from'] = start
        visited = {key}
        while parent and str(parent) in by_id and str(parent) not in visited:
            ancestor = str(parent)
            visited.add(ancestor)
            if ancestor in verified:
                previous = verified[ancestor]['effective_until']
                if start is not None and (previous is None or start < previous):
                    verified[ancestor]['effective_until'] = start
                break
            parent = by_id[ancestor].get('supersedes_schedule_id')
    return list(verified.values())


def current_schedule_listing(schedules):
    """Group a pending leaf and its decision with its last verified ancestor."""
    by_id = {str(s['id']): s for s in schedules}
    parents = {str(s['supersedes_schedule_id']) for s in schedules if s.get('supersedes_schedule_id')}
    active = {str(s['id']): s for s in verified_schedule_periods(schedules)
              if s['effective_until'] is None}
    for key, row in by_id.items():
        if key in parents or row['verification_status'] != 'UNVERIFIED':
            continue
        parent, visited = row.get('supersedes_schedule_id'), {key}
        while parent and str(parent) in by_id and str(parent) not in visited:
            parent = str(parent)
            visited.add(parent)
            if parent in active:
                active[parent]['pending_proposal'] = dict(row)
                break
            parent = by_id[parent].get('supersedes_schedule_id')
        else:
            active[key] = dict(row)
    return list(active.values())


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
                verified = s.get('verified_at') or s.get('created_at')
                if verified and instant < verified:
                    continue
                start = s.get('effective_from', s.get('created_at'))
                if s.get('supersedes_schedule_id') and start and instant < start:
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


