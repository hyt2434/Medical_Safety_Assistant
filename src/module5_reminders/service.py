from datetime import datetime, timezone
from uuid import uuid4
from .calculations import occurrences, adherence, verified_schedule_periods, current_schedule_listing


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
        with self.repo.domain_transaction():
            return self.repo._all('''SELECT e.id,e.medication_fields->>'name_raw' AS name,e.medication_fields
                FROM msa.medication_entry_versions e WHERE e.user_id=%s AND e.confirmed_at IS NOT NULL
                AND NOT EXISTS(SELECT FROM msa.medication_entry_versions n WHERE n.item_id=e.item_id AND n.version_no>e.version_no)
                ORDER BY e.created_at DESC,e.id''', (self.repo.owner,))

    def create(self, entry_version_id, times, dose_raw, timezone, confirm):
        if confirm is not True:
            raise ValueError('Explicit confirmation required')
        r = self.repo
        with r.domain_transaction():
            # Serialize creation for this entry, including concurrent requests.
            r._owned('medication_entry_versions', entry_version_id, lock=True)
            if r._one('''SELECT s.id FROM msa.medication_schedules s
                WHERE s.user_id=%s AND s.entry_version_id=%s AND NOT EXISTS(
                    SELECT FROM msa.medication_schedules n WHERE n.supersedes_schedule_id=s.id)''',
                (r.owner, entry_version_id)):
                raise ValueError('An active schedule already exists for this medication; use a revision')
            row = r.save_schedule(entry_version_id, {'schema': 'schedule.v1', 'times': times, 'dose_raw': dose_raw}, timezone)
            return r.confirm_schedule(row['id'], row['content_digest'], uuid4(), explicit_confirmation=True)

    def schedules(self, *, include_history=False):
        r = self.repo
        with r.domain_transaction():
            rows = r._all('''SELECT s.*,e.medication_fields->>'name_raw' AS name,
                coalesce(rs.enabled,false) AS reminder_enabled,
                (SELECT o.decision FROM msa.review_outcomes o WHERE o.schedule_id=s.id ORDER BY o.reviewed_at DESC,o.id DESC LIMIT 1) AS review_decision
                FROM msa.medication_schedules s JOIN msa.medication_entry_versions e ON e.id=s.entry_version_id
                LEFT JOIN msa.reminder_settings rs ON rs.schedule_id=s.id
                WHERE s.user_id=%s ORDER BY s.created_at DESC,s.id''', (r.owner,))
            return rows if include_history else current_schedule_listing(rows)

    def reminder(self, schedule_id, enabled):
        r = self.repo
        with r.domain_transaction():
            s = r._owned('medication_schedules', schedule_id, lock=True)
            assessment = None
            if enabled:
                if s['verification_status'] == 'HCP_VERIFIED':
                    outcome = (s.get('verification_evidence') or {}).get('review_outcome_id')
                    reviewed = r._one('''SELECT a.id FROM msa.review_outcomes o
                        JOIN msa.review_cases c ON c.id=o.case_id AND c.user_id=o.user_id
                        JOIN msa.safety_assessments a ON a.id=c.safety_assessment_id AND a.user_id=c.user_id
                        WHERE o.id=%s AND o.user_id=%s AND o.schedule_id=%s AND o.decision='APPROVED'
                        AND o.reviewed_content_digest=%s AND a.execution_status='COMPLETED'
                        AND EXISTS(SELECT FROM msa.snapshot_entries se WHERE se.snapshot_id=a.snapshot_id
                            AND se.user_id=a.user_id AND se.entry_version_id=%s)''',
                        (outcome, r.owner, s['id'], s['content_digest'], s['entry_version_id']))
                    if reviewed is None:
                        raise ValueError('Reviewed assessment must be completed and cover this medication')
                    assessment = reviewed['id']
                elif s['verification_status'] == 'PATIENT_CONFIRMED':
                    assessment = latest_assessment(r, s['entry_version_id'])
                else:
                    raise ValueError('Reminder requires a verified schedule')
            return r.set_reminder(schedule_id, enabled=enabled, assessment=assessment,
                                  preferences={'schema': 'notification-preferences.v1', 'channel': 'IN_APP'})

    def activate(self, schedule_id):
        r = self.repo
        with r.domain_transaction():
            s = r._owned('medication_schedules', schedule_id, lock=True)
            if s['schedule_origin'] != 'PROPOSED_CHANGE':
                raise ValueError('Activation requires a reviewed schedule revision')
            if r._one('SELECT id FROM msa.medication_schedules WHERE supersedes_schedule_id=%s', (schedule_id,)):
                raise ValueError('Cannot activate a superseded schedule')
            outcome = r._one('''SELECT o.*,c.safety_assessment_id AS assessment_id
                FROM msa.review_outcomes o JOIN msa.review_cases c ON c.id=o.case_id
                JOIN msa.safety_assessments a ON a.id=c.safety_assessment_id AND a.user_id=c.user_id
                WHERE o.schedule_id=%s AND o.user_id=%s
                AND a.execution_status='COMPLETED' AND EXISTS(SELECT FROM msa.snapshot_entries se
                    WHERE se.snapshot_id=a.snapshot_id AND se.user_id=a.user_id AND se.entry_version_id=%s)
                ORDER BY o.reviewed_at DESC,o.id DESC LIMIT 1''',
                (schedule_id, r.owner, s['entry_version_id']))
            if outcome is None or outcome['decision'] != 'APPROVED':
                raise ValueError('Approval with a completed assessment for this medication is required')
            case = r._owned('review_cases', outcome['case_id'], lock=True)
            if case['status'] not in ('OPEN', 'IN_REVIEW', 'CLOSED'):
                raise ValueError('Case is not available for activation')
            if s['verification_status'] == 'UNVERIFIED':
                r.confirm_schedule(s['id'], s['content_digest'], uuid4(), explicit_confirmation=True, review_outcome=outcome['id'])
            setting = r.set_reminder(schedule_id, enabled=True, assessment=outcome['assessment_id'],
                                     preferences={'schema': 'notification-preferences.v1', 'channel': 'IN_APP'})
            if case['status'] != 'CLOSED':
                closed = r._one('''UPDATE msa.review_cases
                    SET status='CLOSED',closed_at=clock_timestamp(),updated_at=clock_timestamp()
                    WHERE id=%s AND user_id=%s AND status IN ('OPEN','IN_REVIEW')
                    RETURNING id''', (case['id'], r.owner))
                if closed is None:
                    raise ValueError('Case could not be closed during activation')
            return setting

    def records(self):
        r = self.repo
        with r.domain_transaction():
            return r._all('SELECT * FROM msa.dose_records WHERE user_id=%s ORDER BY recorded_at,id', (r.owner,))

    def today(self, now=None):
        return occurrences(self._dose_schedules(), self.records(), now or datetime.now(timezone.utc))

    def _dose_schedules(self):
        return verified_schedule_periods(self.schedules(include_history=True))

    def history(self, days=7, now=None):
        return occurrences(self._dose_schedules(), self.records(), now or datetime.now(timezone.utc), days)

    def adherence(self, days=7, now=None):
        return adherence(self._dose_schedules(), self.records(), now or datetime.now(timezone.utc), days)

    def dose(self, schedule_id, scheduled_for, status, supersedes=None):
        if scheduled_for.tzinfo is None or scheduled_for.utcoffset() is None:
            raise ValueError('Dose time must include a timezone')
        if scheduled_for > datetime.now(timezone.utc):
            raise ValueError('Cannot record a future dose')
        r = self.repo
        with r.domain_transaction():
            r._owned('medication_schedules', schedule_id, lock=True)
            schedule = [s for s in self._dose_schedules() if str(s['id']) == str(schedule_id)]
            valid = occurrences(schedule, [], scheduled_for)
            if not any(row['scheduled_for'] == scheduled_for.astimezone(timezone.utc) for row in valid):
                raise ValueError('Dose time is outside the verified schedule effective period')
            return r.record_dose(schedule_id, scheduled_for, status, supersedes=supersedes)
