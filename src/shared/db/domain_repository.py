"""SAD domain persistence over Core's real transactions and server identity.

These operations store data and enforce consent/version contracts. They do not
schedule notifications, perform clinical review or implement future module APIs.
"""
from contextlib import contextmanager
import json
from psycopg.types.json import Jsonb
from shared.db.repository import CoreRepository, now


class DomainRepository(CoreRepository):
    def __init__(self, connection, *, authenticated_actor, permissions=()):
        super().__init__(connection, authenticated_owner=authenticated_actor)
        self.permissions = tuple(permissions)
        self._domain_transaction_depth = 0

    @contextmanager
    def transaction(self):
        # Inherited Core operations must retain the strict outer-transaction guard.
        with super().transaction():
            self.db.execute("SELECT set_config('msa.authenticated_permissions',%s,true)",
                            (json.dumps(self.permissions),))
            yield

    @contextmanager
    def domain_transaction(self):
        """Compose only domain operations; Core operations still use transaction."""
        if self._domain_transaction_depth:
            with self.db.transaction():
                yield
            return
        with self.transaction():
            self._domain_transaction_depth += 1
            try:
                yield
            finally:
                self._domain_transaction_depth -= 1

    def add_cabinet_item(self, name_raw, *, product_id=None, reference_build=None, expires_on=None):
        with self.domain_transaction():
            return self._insert('msa.medication_cabinet_items', user_id=self.owner, medication_name_raw=name_raw,
                                product_id=product_id, reference_build=reference_build, expires_on=expires_on)

    def save_schedule(self, entry_version, details, timezone, *, origin='PRESCRIPTION_TRANSCRIPTION', supersedes=None):
        with self.domain_transaction():
            self._owned('medication_entry_versions', entry_version, lock=True)
            return self._insert('msa.medication_schedules', user_id=self.owner, entry_version_id=entry_version,
                schedule_details=details, timezone=timezone, schedule_origin=origin, supersedes_schedule_id=supersedes)

    def confirm_schedule(self, schedule, displayed_digest, request_key, *, explicit_confirmation, review_outcome=None):
        if explicit_confirmation is not True:
            raise ValueError('Explicit confirmation required')
        with self.domain_transaction():
            row = self._owned('medication_schedules', schedule, lock=True)
            if row['content_digest'] != displayed_digest:
                raise ValueError('Schedule differs from displayed content')
            if row['verification_status'] != 'UNVERIFIED':
                if (row['verification_evidence']['confirmation_key'] == str(request_key) and
                    row['verification_evidence'].get('review_outcome_id') == (str(review_outcome) if review_outcome is not None else None)):
                    return row
                raise ValueError('Schedule already confirmed by another action')
            entry = self._owned('medication_entry_versions', row['entry_version_id'])
            evidence = {'schema': 'schedule-verification.v1', 'explicit': True,
                        'schedule_digest': displayed_digest, 'entry_digest': entry['content_digest'],
                        'confirmation_key': str(request_key)}
            if review_outcome is not None:
                evidence['review_outcome_id'] = str(review_outcome)
            return self._one('''UPDATE msa.medication_schedules SET verification_status=%s,
                verification_evidence=%s,verified_at=clock_timestamp() WHERE id=%s RETURNING *''',
                ('HCP_VERIFIED' if review_outcome else 'PATIENT_CONFIRMED', Jsonb(evidence), schedule))

    def record_dose(self, schedule, scheduled_for, status, *, supersedes=None):
        with self.domain_transaction():
            self._owned('medication_schedules', schedule, lock=True)
            if supersedes is None:
                prior = self._one('''SELECT * FROM msa.dose_records r WHERE schedule_id=%s AND scheduled_for=%s
                    AND user_id=%s AND NOT EXISTS(SELECT FROM msa.dose_records n WHERE n.supersedes_record_id=r.id)''',
                    (schedule, scheduled_for, self.owner))
                if prior:
                    if prior['dose_status'] == status:
                        return prior
                    raise ValueError('Correct the displayed dose record explicitly')
            return self._insert('msa.dose_records', user_id=self.owner, schedule_id=schedule,
                scheduled_for=scheduled_for, dose_status=status, supersedes_record_id=supersedes)

    def create_case(self, kind, *, assessment=None, schedule=None, change_request=None):
        with self.domain_transaction():
            return self._insert('msa.review_cases', user_id=self.owner, case_type=kind,
                safety_assessment_id=assessment, schedule_id=schedule, schedule_change_request_id=change_request)

    def grant_case_access(self, case, hcp, consent, *, expires_at=None):
        with self.domain_transaction():
            self._owned('review_cases', case, lock=True)
            return self._insert('msa.review_case_permissions', user_id=self.owner, case_id=case, hcp_id=hcp,
                                consent_evidence=consent, expires_at=expires_at)

    def assign_case(self, case, hcp):
        with self.domain_transaction():
            self._owned('review_cases', case, lock=True)
            return self._one("UPDATE msa.review_cases SET assigned_hcp_id=%s,status='OPEN',updated_at=clock_timestamp() WHERE id=%s RETURNING *", (hcp, case))

    def share_summary(self, summary, hcp, consent, *, sections=None, expires_at=None):
        with self.domain_transaction():
            self._owned('patient_health_summaries', summary)
            return self._insert('msa.summary_shares', user_id=self.owner, summary_id=summary, hcp_id=hcp,
                scope='FULL' if sections is None else 'SECTIONS', allowed_sections=sections or [],
                consent_evidence=consent, expires_at=expires_at)

    def revoke_access(self, grant, *, summary=False):
        table = 'summary_shares' if summary else 'review_case_permissions'
        with self.domain_transaction():
            row = self._owned(table, grant, lock=True)
            if row['revoked_at'] is not None:
                return row
            return self._one(f'UPDATE msa.{table} SET revoked_at=clock_timestamp() WHERE id=%s RETURNING *', (grant,))

    def shared_summary(self, share):
        with self.domain_transaction():
            return self._one('SELECT msa.shared_summary(%s) AS content', (share,))['content']

    def case_message(self, case, text):
        with self.domain_transaction():
            row = self._one('SELECT * FROM msa.review_cases WHERE id=%s AND msa.can_access_case(id,user_id)', (case,))
            if row is None:
                raise PermissionError('Case access denied')
            return self._insert('msa.review_case_messages', user_id=row['user_id'], case_id=case,
                                sender_user_id=self.owner, content=text)

    def record_review(self, case, decision, evidence, *, notes=None):
        with self.domain_transaction():
            row = self._one('SELECT * FROM msa.review_cases WHERE id=%s AND msa.can_access_case(id,user_id) FOR UPDATE', (case,))
            if row is None:
                raise PermissionError('Case access denied')
            schedule = self._one('SELECT content_digest FROM msa.medication_schedules WHERE id=%s', (row['schedule_id'],)) if row['schedule_id'] else None
            return self._insert('msa.review_outcomes', user_id=row['user_id'], case_id=case, reviewer_id=self.owner,
                review_type=row['case_type'], decision=decision, evidence=evidence, notes=notes,
                schedule_id=row['schedule_id'], reviewed_content_digest=schedule['content_digest'] if schedule else None)

    def request_schedule_change(self, schedule, details):
        with self.domain_transaction():
            self._owned('medication_schedules', schedule)
            return self._insert('msa.schedule_change_requests', user_id=self.owner, schedule_id=schedule, proposed_timing=details)

    def set_reminder(self, schedule, *, enabled, preferences, assessment=None, eligibility=None):
        if type(enabled) is not bool:
            raise ValueError('Explicit enabled/disabled action required')
        with self.domain_transaction():
            self._owned('medication_schedules', schedule, lock=True)
            previous = self._one('SELECT * FROM msa.reminder_settings WHERE schedule_id=%s AND user_id=%s FOR UPDATE', (schedule, self.owner))
            assessment = assessment or (previous['last_assessment_id'] if previous else None)
            status = eligibility or ('ELIGIBLE' if enabled else previous['eligibility_status'] if previous else 'UNASSESSED')
            evaluated = now() if assessment else None
            if previous:
                return self._one('''UPDATE msa.reminder_settings SET enabled=%s,notification_preferences=%s,
                    last_assessment_id=%s,eligibility_status=%s,evaluated_at=%s WHERE id=%s RETURNING *''',
                    (enabled, Jsonb(preferences), assessment, status, evaluated, previous['id']))
            return self._insert('msa.reminder_settings', user_id=self.owner, schedule_id=schedule, enabled=enabled,
                notification_preferences=preferences, last_assessment_id=assessment, eligibility_status=status, evaluated_at=evaluated)

    def project_health_fact(self, source_id, index, fact_type):
        with self.domain_transaction():
            source = self._owned('patient_health_sources', source_id)
            fact = source['source_content']['facts'][index]
            return self._insert('msa.patient_health_facts', user_id=self.owner, health_source_id=source_id,
                source_fact_index=index, fact_type=fact_type, field=fact['field'], value_json=Jsonb(fact['value']),
                text_raw=fact['text_raw'], uncertainty_raw=fact['uncertainty'])
