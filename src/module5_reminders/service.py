from datetime import datetime, timezone
from uuid import uuid4
from .calculations import occurrences, adherence


def latest_assessment(repo, entry):
    row = repo._one('''SELECT a.id FROM msa.safety_assessments a
        JOIN msa.snapshot_entries se ON se.snapshot_id=a.snapshot_id AND se.user_id=a.user_id
        WHERE a.user_id=%s AND se.entry_version_id=%s AND a.execution_status='COMPLETED'
        ORDER BY a.finished_at DESC,a.id DESC LIMIT 1''', (repo.owner, entry))
    if row is None:
        raise ValueError('Complete a safety assessment for this medication first')
    return row['id']


class ReminderService:
    def __init__(self, repo):
        self.repo = repo

    def entries(self):
        with self.repo.transaction():
            return self.repo._all('''SELECT e.id,e.medication_fields->>'name_raw' AS name,e.medication_fields
                FROM msa.medication_entry_versions e WHERE e.user_id=%s AND e.confirmed_at IS NOT NULL
                AND NOT EXISTS(SELECT FROM msa.medication_entry_versions n WHERE n.item_id=e.item_id AND n.version_no>e.version_no)
                ORDER BY e.created_at DESC,e.id''', (self.repo.owner,))

    def create(self, entry_version_id, times, dose_raw, timezone, confirm):
        if confirm is not True:
            raise ValueError('Explicit confirmation required')
        r = self.repo
        with r.transaction():
            row = r.save_schedule(entry_version_id, {'schema': 'schedule.v1', 'times': times, 'dose_raw': dose_raw}, timezone)
            return r.confirm_schedule(row['id'], row['content_digest'], uuid4(), explicit_confirmation=True)

    def schedules(self, *, include_history=False):
        r = self.repo
        with r.transaction():
            return r._all('''SELECT s.*,e.medication_fields->>'name_raw' AS name,
                coalesce(rs.enabled,false) AS reminder_enabled,
                (SELECT n.created_at FROM msa.medication_schedules n WHERE n.supersedes_schedule_id=s.id) AS effective_until,
                (SELECT o.decision FROM msa.review_outcomes o WHERE o.schedule_id=s.id ORDER BY o.reviewed_at DESC,o.id DESC LIMIT 1) AS review_decision
                FROM msa.medication_schedules s JOIN msa.medication_entry_versions e ON e.id=s.entry_version_id
                LEFT JOIN msa.reminder_settings rs ON rs.schedule_id=s.id
                WHERE s.user_id=%s AND (%s OR NOT EXISTS(SELECT FROM msa.medication_schedules n WHERE n.supersedes_schedule_id=s.id))
                ORDER BY s.created_at DESC,s.id''', (r.owner, include_history))

    def reminder(self, schedule_id, enabled):
        r = self.repo
        with r.transaction():
            s = r._owned('medication_schedules', schedule_id, lock=True)
            assessment = latest_assessment(r, s['entry_version_id']) if enabled else None
            return r.set_reminder(schedule_id, enabled=enabled, assessment=assessment,
                                  preferences={'schema': 'notification-preferences.v1', 'channel': 'IN_APP'})

    def activate(self, schedule_id):
        r = self.repo
        with r.transaction():
            s = r._owned('medication_schedules', schedule_id, lock=True)
            if s['schedule_origin'] != 'PROPOSED_CHANGE':
                raise ValueError('Activation requires a reviewed schedule revision')
            outcome = r._one('''SELECT o.* FROM msa.review_outcomes o JOIN msa.review_cases c ON c.id=o.case_id
                WHERE o.schedule_id=%s AND o.user_id=%s AND o.decision='APPROVED'
                AND c.safety_assessment_id=%s ORDER BY o.reviewed_at DESC,o.id DESC LIMIT 1''',
                (schedule_id, r.owner, latest_assessment(r, s['entry_version_id'])))
            if outcome is None:
                raise ValueError('Approval for the current assessment is required')
            if s['verification_status'] == 'UNVERIFIED':
                r.confirm_schedule(s['id'], s['content_digest'], uuid4(), explicit_confirmation=True, review_outcome=outcome['id'])
            return self.reminder(schedule_id, True)

    def records(self):
        r = self.repo
        with r.transaction():
            return r._all('SELECT * FROM msa.dose_records WHERE user_id=%s ORDER BY recorded_at,id', (r.owner,))

    def today(self, now=None):
        return occurrences(self.schedules(), self.records(), now or datetime.now(timezone.utc))

    def history(self, days=7, now=None):
        return occurrences(self.schedules(include_history=True), self.records(), now or datetime.now(timezone.utc), days)

    def adherence(self, days=7, now=None):
        return adherence(self.schedules(include_history=True), self.records(), now or datetime.now(timezone.utc), days)

    def dose(self, schedule_id, scheduled_for, status, supersedes=None):
        if scheduled_for > datetime.now(timezone.utc):
            raise ValueError('Cannot record a future dose')
        return self.repo.record_dose(schedule_id, scheduled_for, status, supersedes=supersedes)
