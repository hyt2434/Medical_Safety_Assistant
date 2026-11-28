"""Case workflows using the existing audited domain repository."""
from hashlib import sha256
from uuid import UUID


def evidence(schema, case_id, text):
    return {'schema': schema, 'sources': [{
        'locator': f'msa://{schema.split(".")[0]}/{case_id}',
        'sha256': sha256(text.encode()).hexdigest()}]}


class HcpService:
    def __init__(self, repo):
        self.repo = repo

    def providers(self):
        from datetime import datetime, timezone
        from sqlalchemy import select, or_
        from shared.auth.db import transaction
        from shared.auth.models import User, UserRole, Role
        with transaction() as db:
            candidates = db.execute(select(User.user_id, User.full_name).join(
                UserRole, UserRole.user_id == User.user_id).join(Role).where(
                Role.role_code == 'hcp', User.account_status == 'active',
                UserRole.revoked_at.is_(None),
                UserRole.granted_at <= datetime.now(timezone.utc),
                or_(UserRole.expires_at.is_(None), UserRole.expires_at > datetime.now(timezone.utc))
            ).distinct()).all()
        with self.repo.domain_transaction():
            return [{'id': uid, 'full_name': name} for uid, name in candidates
                    if UUID(str(uid)) != self.repo.owner and self.repo._one(
                        'SELECT id FROM identity.users WHERE id=%s', (uid,))]

    def create(self, kind, hcp_id, consent, assessment_id=None, schedule_id=None):
        if consent is not True:
            raise ValueError('Explicit patient consent required')
        if not any(str(p['id']) == str(hcp_id) for p in self.providers()):
            raise ValueError('Choose an active linked healthcare provider')
        r = self.repo
        with r.domain_transaction():
            if kind == 'SAFETY' and assessment_id is None:
                raise ValueError('Safety review requires a completed assessment')
            if assessment_id:
                assessment = r._owned('safety_assessments', assessment_id)
                if kind == 'SAFETY' and assessment['execution_status'] != 'COMPLETED':
                    raise ValueError('Safety review requires a completed assessment')
            if kind == 'SCHEDULE':
                old = r._owned('medication_schedules', schedule_id, lock=True)
                if r._one('SELECT id FROM msa.medication_schedules WHERE supersedes_schedule_id=%s', (schedule_id,)):
                    raise ValueError('Schedule has already been superseded')
                if assessment_id is None:
                    from module5_reminders.service import latest_assessment
                    assessment_id = latest_assessment(r, old['entry_version_id'])
                if not r._one('''SELECT a.id FROM msa.safety_assessments a
                    JOIN msa.snapshot_entries se ON se.snapshot_id=a.snapshot_id AND se.user_id=a.user_id
                    WHERE a.id=%s AND a.user_id=%s AND a.execution_status='COMPLETED' AND se.entry_version_id=%s''',
                    (assessment_id, r.owner, old['entry_version_id'])):
                    raise ValueError('Completed assessment for this exact medication is required')
                revision = r.save_schedule(old['entry_version_id'], old['schedule_details'], old['timezone'],
                                           origin='PROPOSED_CHANGE', supersedes=old['id'])
                schedule_id = revision['id']
            row = r.create_case(kind, assessment=assessment_id, schedule=schedule_id)
            consent_text = f'I consent to share case {row["id"]} with provider {hcp_id} for {kind} review.'
            r.grant_case_access(row['id'], hcp_id, evidence('consent.v1', row['id'], consent_text))
            return r.assign_case(row['id'], hcp_id)

    def cases(self, *, mine=False):
        r = self.repo
        with r.domain_transaction():
            return r._all('''SELECT c.*, (SELECT to_jsonb(o) FROM msa.review_outcomes o
                WHERE o.case_id=c.id ORDER BY reviewed_at DESC,id DESC LIMIT 1) AS latest_outcome
                FROM msa.review_cases c WHERE ''' + ('c.user_id=%s' if mine else 'c.assigned_hcp_id=%s') +
                ' AND msa.can_access_case(c.id,c.user_id) ORDER BY c.created_at DESC,c.id', (r.owner,))

    def detail(self, case_id):
        r = self.repo
        with r.domain_transaction():
            row = r._one('SELECT * FROM msa.review_cases WHERE id=%s AND msa.can_access_case(id,user_id)', (case_id,))
            if row is None:
                raise PermissionError('Case access denied')
            row['schedule'] = r._one('''SELECT s.*, e.medication_fields->>'name_raw' AS name
                FROM msa.medication_schedules s JOIN msa.medication_entry_versions e ON e.id=s.entry_version_id
                WHERE s.id=%s''', (row['schedule_id'],)) if row['schedule_id'] else None
            row['assessment'] = r._one('SELECT * FROM msa.safety_assessments WHERE id=%s', (row['safety_assessment_id'],)) if row['safety_assessment_id'] else None
            row['medications'] = r._all('''SELECT e.id,e.medication_fields FROM msa.medication_entry_versions e
                JOIN msa.snapshot_entries se ON se.entry_version_id=e.id
                JOIN msa.safety_assessments a ON a.snapshot_id=se.snapshot_id WHERE a.id=%s''', (row['safety_assessment_id'],))
            row['findings'] = r._all('SELECT * FROM msa.safety_findings WHERE assessment_id=%s', (row['safety_assessment_id'],))
            row['messages'] = r._all('SELECT * FROM msa.review_case_messages WHERE case_id=%s ORDER BY sent_at,id', (case_id,))
            row['outcomes'] = r._all('SELECT * FROM msa.review_outcomes WHERE case_id=%s ORDER BY reviewed_at,id', (case_id,))
            return row

    def message(self, case_id, text):
        if not text.strip():
            raise ValueError('Message cannot be blank')
        return self.repo.case_message(case_id, text.strip())

    def review(self, case_id, decision, notes):
        """Record the clinician's outcome; patient activation owns case closure."""
        return self.repo.record_review(
            case_id, decision,
            evidence('review-evidence.v1', case_id, f'{decision}\n{notes}'),
            notes=notes,
        )
