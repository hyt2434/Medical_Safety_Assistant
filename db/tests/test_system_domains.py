"""SAD constraints on marked PostgreSQL; every fixture rolls back all row writes.

Set SYSTEM_TEST_DSN to the separately marked system-schema checks database.
No reference import, existing-record cleanup or report generation is performed.
"""
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta, date
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb
import pytest

from shared.db import CoreRepository
from shared.db.intake_adapter import medication_fields

ROOT = Path(__file__).resolve().parents[2]


def actor(db, identity, permissions=()):
    db.execute("SELECT set_config('msa.authenticated_owner',%s,true),set_config('msa.authenticated_permissions',%s,true)",
               (str(identity), json.dumps(permissions)))


@pytest.fixture
def domain():
    dsn = os.environ.get('SYSTEM_TEST_DSN')
    if not dsn:
        pytest.skip('SYSTEM_TEST_DSN must identify a marked system test database')
    with psycopg.connect(dsn, autocommit=True) as db:
        assert db.info.host in ('127.0.0.1', 'localhost', '::1')
        assert db.info.dbname.startswith('msa_core_test_v4system') and db.info.dbname.endswith('checks')
        assert db.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()").fetchone()[0] == 'Medication Safety Assistant Core V4 isolated test'
        tables = db.execute("SELECT tablename FROM pg_tables WHERE schemaname='msa'").fetchall()
        counts = {t: db.execute(sql.SQL('SELECT count(*) FROM msa.{}').format(sql.Identifier(t))).fetchone()[0] for (t,) in tables}
        users = db.execute('SELECT count(*) FROM identity.users').fetchone()[0]
        with db.transaction(force_rollback=True):
            # Candidate completion migrations are exercised transactionally until
            # finalized; published baseline migration files remain untouched.
            from db.manage import migrate
            migrate(db)
            owner, other, hcp = uuid4(), uuid4(), uuid4()
            db.execute('INSERT INTO identity.users(id) VALUES (%s),(%s),(%s)', (owner, other, hcp))
            actor(db, owner)
            ctx = Context(db, owner, other, hcp)
            yield ctx
            written = {t: db.execute(sql.SQL('SELECT count(*) FROM msa.{}').format(sql.Identifier(t))).fetchone()[0] - counts.get(t, 0) for (t,) in tables}
            print('\nROLLBACK TABLE WRITES:', {k: v for k, v in written.items() if v}, 'identity.users: 3')
        assert db.execute('SELECT count(*) FROM identity.users').fetchone()[0] == users
        for table, count in counts.items():
            assert db.execute(sql.SQL('SELECT count(*) FROM msa.{}').format(sql.Identifier(table))).fetchone()[0] == count


@contextmanager
def denied(db, match=None):
    with pytest.raises(psycopg.Error, match=match):
        with db.transaction():
            yield


def evidence(tag='consent.v1'):
    return {'schema': tag, 'sources': [{'locator': 'test://explicit-synthetic-consent', 'sha256': '1' * 64}]}


class Context:
    def __init__(self, db, owner, other, hcp):
        self.db, self.owner, self.other, self.hcp = db, owner, other, hcp
        self.repo = CoreRepository(db, authenticated_owner=owner)

    def insert(self, table, **values):
        return self.repo._insert('msa.' + table, **values)

    def entry(self, *, confirmed=True):
        chat = self.insert('conversation_sessions', user_id=self.owner)
        intake = self.insert('intake_sessions', user_id=self.owner, conversation_id=chat['id'], purpose='MEDICATION_COLLECTION')
        fields = medication_fields({'name_raw': 'Explicit synthetic medication', 'dose_raw': 'one tablet',
            'administrations': [{'timing_raw': '08:00', 'dose_raw': 'one tablet'}],
            'evidence_text': 'Explicit synthetic medication, one tablet at 08:00'})
        inp = self.insert('intake_inputs', user_id=self.owner, session_id=intake['id'], modality='TEXT',
            input_digest=hashlib.sha256(fields['evidence_text'].encode()).hexdigest(),
            payload_or_locator={'schema': 'input.v4', 'digest_basis': 'ORIGINAL_BYTES', 'text': fields['evidence_text']})
        extraction = self.insert('intake_extractions', user_id=self.owner, input_id=inp['id'], attempt_no=1,
            extractor_name='TEST', extractor_version='synthetic.v1', status='SUCCEEDED',
            result={'schema': 'extraction.v4', 'medications': [fields], 'warnings': [], 'document_instructions_raw': []})
        item = self.insert('intake_items', user_id=self.owner, extraction_id=extraction['id'], item_ordinal=1,
            origin_evidence={'schema': 'item-origin.v4', 'input_id': str(inp['id']), 'extraction_id': str(extraction['id']),
                             'item_ordinal': 1, 'locator': {}, 'text_raw': fields['evidence_text']})
        entry = self.insert('medication_entry_versions', user_id=self.owner, item_id=item['id'], version_no=1,
                            medication_fields=fields, source_extraction_id=extraction['id'])
        if confirmed:
            self.db.execute("SELECT set_config('msa.displayed_digest',%s,true)", (entry['content_digest'],))
            entry = self.repo._one('UPDATE msa.medication_entry_versions SET confirmed_at=clock_timestamp(),confirmation_key=%s WHERE id=%s RETURNING *', (uuid4(), entry['id']))
        return entry

    def schedule(self, *, verified=False, **overrides):
        entry = self.entry()
        schedule = self.insert('medication_schedules', **{'user_id': self.owner, 'entry_version_id': entry['id'],
            'schedule_details': {'schema': 'schedule.v1', 'times': ['08:00'], 'dose_raw': 'one tablet'},
            'timezone': 'Asia/Ho_Chi_Minh', 'schedule_origin': 'PRESCRIPTION_TRANSCRIPTION', **overrides})
        if verified:
            schedule = self.confirm(schedule, entry)
        return schedule, entry

    def confirm(self, schedule, entry, **overrides):
        value = {'schema': 'schedule-verification.v1', 'entry_digest': entry['content_digest'],
                 'schedule_digest': schedule['content_digest'], 'explicit': True, 'confirmation_key': str(uuid4()), **overrides}
        return self.repo._one("UPDATE msa.medication_schedules SET verification_status='PATIENT_CONFIRMED',verification_evidence=%s,verified_at=clock_timestamp() WHERE id=%s RETURNING *", (Jsonb(value), schedule['id']))

    def case(self):
        schedule, entry = self.schedule()
        case = self.insert('review_cases', user_id=self.owner, case_type='SCHEDULE', schedule_id=schedule['id'])
        return case, schedule

    def permit_case(self, case):
        grant = self.insert('review_case_permissions', user_id=self.owner, case_id=case['id'], hcp_id=self.hcp, consent_evidence=evidence())
        self.db.execute("UPDATE msa.review_cases SET assigned_hcp_id=%s,status='OPEN',updated_at=clock_timestamp() WHERE id=%s", (self.hcp, case['id']))
        return grant

    def summary(self):
        identity = uuid4()
        content = {'schema': 'patient-summary.v4', 'as_of': '2026-11-21', 'patient_context': {},
            'conditions': {'state': 'UNKNOWN', 'items': []}, 'allergies': {'state': 'UNKNOWN', 'items': []},
            'medications': [], 'safety_findings': [], 'limitations': [],
            'sections': [{'key': k, 'title': k, 'text': 'Synthetic ' + k, 'source_keys': ['external']} for k in ('medicines', 'conditions')]}
        manifest = {'schema': 'summary-manifest.v4', 'sources': [{'key': 'external', 'kind': 'EXTERNAL_DOCUMENT',
            'digest': '1' * 64, 'scope': 'synthetic fixture', 'locator': {'uri': 'test://source', 'artifact_sha256': '1' * 64}}]}
        digest = self.repo._one('SELECT msa.summary_digest(%s,%s) AS digest', (Jsonb(content), Jsonb(manifest)))['digest']
        self.db.execute("SELECT set_config('msa.displayed_digest',%s,true)", (digest,))
        return self.insert('patient_health_summaries', id=identity, user_id=self.owner, series_root_id=identity, version_no=1,
            summary_content=content, source_manifest=manifest, confirmation_key=uuid4(),
            generation_context={'schema': 'summary-generation.v4', 'generator_version': 'synthetic.v1', 'template_version': None, 'model_ref': None, 'limitations': []},
            generated_at=datetime.now(timezone.utc), confirmed_at=datetime.now(timezone.utc))


def test_cabinet_separate_boxes_expiry_unknown_and_ownership(domain):
    c = domain
    rows = [c.insert('medication_cabinet_items', user_id=c.owner, medication_name_raw='Unidentified synthetic medicine', expires_on=d)
            for d in [date(2026, 12, 1), date(2027, 1, 1), None]]
    assert len({r['id'] for r in rows}) == 3 and rows[2]['expires_on'] is None
    assert all(r['product_id'] is None for r in rows)
    with denied(c.db, 'owner'):
        c.insert('medication_cabinet_items', user_id=c.other, medication_name_raw='Forbidden')
    with denied(c.db):
        c.insert('medication_cabinet_items', user_id=c.owner, medication_name_raw='Wrong product', product_id=uuid4())


@pytest.mark.parametrize('details', [{}, {'schema': 'schedule.v1', 'times': [], 'dose_raw': 'one'},
    {'schema': 'schedule.v1', 'times': ['25:00'], 'dose_raw': 'one'},
    {'schema': 'schedule.v1', 'times': ['08:00', '08:00'], 'dose_raw': 'one'}])
def test_schedule_json_rejects_invalid_or_duplicate_times(domain, details):
    with denied(domain.db):
        domain.schedule(schedule_details=details)


def test_schedule_needs_confirmed_entry_and_iana_zone(domain):
    c = domain
    entry = c.entry(confirmed=False)
    with denied(c.db):
        c.schedule(entry_version_id=entry['id'])
    with denied(c.db, 'timezone'):
        c.schedule(timezone='invented/zone')


@pytest.mark.parametrize('change', [{'explicit': False}, {'entry_digest': '0' * 64}, {'schedule_digest': '0' * 64}, {'confirmation_key': 'invalid'}])
def test_schedule_exact_confirmation_contract(domain, change):
    schedule, entry = domain.schedule()
    with denied(domain.db, 'confirmation'):
        domain.confirm(schedule, entry, **change)


def test_schedule_revision_invalidates_confirmation_and_preserves_old(domain):
    c = domain
    schedule, entry = c.schedule(verified=True)
    changed = c.insert('medication_schedules', user_id=c.owner, entry_version_id=entry['id'], supersedes_schedule_id=schedule['id'],
        schedule_details={'schema': 'schedule.v1', 'times': ['09:00'], 'dose_raw': 'one tablet'},
        timezone='Asia/Ho_Chi_Minh', schedule_origin='PROPOSED_CHANGE')
    assert changed['verification_status'] == 'UNVERIFIED' and changed['verification_evidence'] is None
    assert changed['content_digest'] != schedule['content_digest']
    with denied(c.db):
        c.confirm(changed, entry)
    assert c.db.execute('SELECT verification_status FROM msa.medication_schedules WHERE id=%s', (schedule['id'],)).fetchone()[0] == 'PATIENT_CONFIRMED'


def test_dose_occurrence_dedup_and_append_correction(domain):
    c = domain
    schedule, _ = c.schedule(verified=True)
    when = datetime(2026, 11, 21, 1, tzinfo=timezone.utc)
    row = c.insert('dose_records', user_id=c.owner, schedule_id=schedule['id'], scheduled_for=when, dose_status='TAKEN')
    with denied(c.db):
        c.insert('dose_records', user_id=c.owner, schedule_id=schedule['id'], scheduled_for=when, dose_status='MISSED')
    corrected = c.insert('dose_records', user_id=c.owner, schedule_id=schedule['id'], scheduled_for=when, dose_status='SKIPPED', supersedes_record_id=row['id'])
    assert corrected['supersedes_record_id'] == row['id']
    with denied(c.db, 'different occurrence'):
        c.insert('dose_records', user_id=c.owner, schedule_id=schedule['id'], scheduled_for=when + timedelta(days=1), dose_status='TAKEN', supersedes_record_id=corrected['id'])


def test_hcp_case_access_requires_consent_assignment_permission_and_exact_case(domain):
    c = domain
    case, _ = c.case()
    second, _ = c.case()
    with denied(c.db, 'consent'):
        c.db.execute("UPDATE msa.review_cases SET assigned_hcp_id=%s,status='OPEN' WHERE id=%s", (c.hcp, case['id']))
    grant = c.permit_case(case)
    actor(c.db, c.hcp, ['clinical.case_review'])
    assert c.db.execute('SELECT msa.can_access_case(%s,%s)', (case['id'], c.owner)).fetchone()[0]
    assert not c.db.execute('SELECT msa.can_access_case(%s,%s)', (second['id'], c.owner)).fetchone()[0]
    msg = c.insert('review_case_messages', user_id=c.owner, case_id=case['id'], sender_user_id=c.hcp, content='Synthetic review')
    assert msg['sender_user_id'] == c.hcp
    actor(c.db, c.owner)
    c.db.execute('UPDATE msa.review_case_permissions SET revoked_at=clock_timestamp() WHERE id=%s', (grant['id'],))
    actor(c.db, c.hcp, ['clinical.case_review'])
    assert not c.db.execute('SELECT msa.can_access_case(%s,%s)', (case['id'], c.owner)).fetchone()[0]
    with denied(c.db, 'access'):
        c.insert('review_case_messages', user_id=c.owner, case_id=case['id'], sender_user_id=c.hcp, content='After revocation')


def test_summary_share_is_separate_scoped_and_revocable(domain):
    c = domain
    summary = c.summary()
    case, _ = c.case()
    c.permit_case(case)
    actor(c.db, c.hcp, ['clinical.case_review'])
    assert not c.db.execute('SELECT msa.can_access_summary(%s,%s)', (summary['id'], c.owner)).fetchone()[0]
    actor(c.db, c.owner)
    share = c.insert('summary_shares', user_id=c.owner, summary_id=summary['id'], hcp_id=c.hcp,
                     scope='SECTIONS', allowed_sections=['medicines'], consent_evidence=evidence())
    actor(c.db, c.hcp, ['clinical.case_review'])
    shared = c.db.execute('SELECT msa.shared_summary(%s)', (share['id'],)).fetchone()[0]
    assert [s['key'] for s in shared['sections']] == ['medicines'] and 'conditions' not in shared
    actor(c.db, c.owner)
    c.db.execute('UPDATE msa.summary_shares SET revoked_at=clock_timestamp() WHERE id=%s', (share['id'],))
    actor(c.db, c.hcp, ['clinical.case_review'])
    with denied(c.db, 'denied'):
        c.db.execute('SELECT msa.shared_summary(%s)', (share['id'],))


def test_health_fact_is_exact_projection_and_medication_use_is_separate(domain):
    c = domain
    content = {'schema': 'health-source.v4', 'facts': [{'field': 'medication_use', 'value': 'Unidentified synthetic medicine', 'text_raw': 'I stopped it', 'uncertainty': None}], 'limitations': []}
    source = c.insert('patient_health_sources', user_id=c.owner, origin='PATIENT_REPORTED', source_content=content,
        source_locator={'schema': 'health-source-locator.v4', 'uri': 'test://source', 'artifact_sha256': '1' * 64})
    with denied(c.db, 'projection'):
        c.insert('patient_health_facts', user_id=c.owner, health_source_id=source['id'], source_fact_index=0,
            fact_type='MEDICATION_USE', field='medication_use', value_json=Jsonb('Invented value'), text_raw='I stopped it')
    fact = c.insert('patient_health_facts', user_id=c.owner, health_source_id=source['id'], source_fact_index=0,
        fact_type='MEDICATION_USE', field='medication_use', value_json=Jsonb('Unidentified synthetic medicine'), text_raw='I stopped it')
    use = c.insert('patient_medication_uses', user_id=c.owner, health_fact_id=fact['id'], medication_name_raw='Unidentified synthetic medicine', use_status='DISCONTINUED', end_date=date(2026, 11, 20))
    assert use['entry_version_id'] is None
    with denied(c.db):
        c.insert('patient_medication_uses', user_id=c.owner, health_fact_id=fact['id'], medication_name_raw='Synthetic', use_status='CURRENT', end_date=date(2026, 11, 20))


def test_support_assignment_reply_and_no_unassigned_access(domain):
    c = domain
    ticket = c.insert('support_tickets', requester_user_id=c.owner, subject='Synthetic technical issue')
    actor(c.db, c.other, ['operations.queue'])
    with denied(c.db, 'denied'):
        c.insert('support_messages', ticket_id=ticket['id'], author_user_id=c.other, content='Unassigned')
    actor(c.db, c.other, ['operations.assign', 'operations.queue'])
    c.db.execute('UPDATE msa.support_tickets SET assigned_support_user_id=%s WHERE id=%s', (c.other, ticket['id']))
    msg = c.insert('support_messages', ticket_id=ticket['id'], author_user_id=c.other, content='Assigned technical reply')
    assert msg['content'] == 'Assigned technical reply'


def test_dataset_review_does_not_modify_published_reference(domain):
    c = domain
    def reference_counts_and_hashes():
        return [c.db.execute(sql.SQL("SELECT count(*),md5(coalesce(string_agg(to_jsonb(t)::text,'' ORDER BY id),'')) FROM msa_ref.{} t").format(sql.Identifier(t))).fetchone()
                for t in ('medications','ingredients','medication_ingredients','ddinter_mappings')]
    before=reference_counts_and_hashes()
    values = dict(review_batch_id='synthetic-review', subject_type='MEDICATION', source_record_id='SYNTHETIC:1',
                  decision='PROPOSE_CORRECTION', evidence=evidence('review-evidence.v1'), reviewer_user_id=c.owner)
    with denied(c.db, 'reviewer'):
        c.insert('dataset_review_decisions', **values)
    actor(c.db, c.owner, ['catalog.review'])
    review = c.insert('dataset_review_decisions', **values)
    assert review['dataset_build'] is None
    assert reference_counts_and_hashes()==before


def test_new_reminder_cannot_enable_unverified_or_unassessed_schedule(domain):
    c = domain
    s, _ = c.schedule()
    values = dict(user_id=c.owner, schedule_id=s['id'], enabled=False,
                  notification_preferences={'schema': 'notification-preferences.v1', 'channel': 'IN_APP'})
    row = c.insert('reminder_settings', **values)
    assert row['eligibility_status'] == 'UNASSESSED'
    with denied(c.db, 'current verified schedule'):
        c.db.execute("UPDATE msa.reminder_settings SET enabled=true,eligibility_status='ELIGIBLE' WHERE id=%s", (row['id'],))


def test_business_audit_actor_and_append_only(domain):
    c = domain
    row = c.insert('audit_events', actor_user_id=c.owner, subject_user_id=c.owner, action='synthetic.action',
        resource_type='TEST', resource_id='synthetic', outcome='SUCCESS', details={'schema': 'business-audit.v1', 'reason': None})
    with denied(c.db, 'Append-only'):
        c.db.execute("UPDATE msa.audit_events SET outcome='FAILED' WHERE id=%s", (row['id'],))
    with denied(c.db, 'cannot be deleted'):
        c.db.execute('DELETE FROM msa.audit_events WHERE id=%s', (row['id'],))


def test_hcp_review_pins_exact_schedule_and_patient_cannot_self_approve(domain):
    c = domain
    schedule, entry = c.schedule(schedule_origin='PROPOSED_CHANGE')
    case = c.insert('review_cases', user_id=c.owner, case_type='SCHEDULE', schedule_id=schedule['id'])
    c.permit_case(case)
    values = dict(user_id=c.owner, case_id=case['id'], reviewer_id=c.owner, review_type='SCHEDULE', decision='APPROVED',
        evidence=evidence('review-evidence.v1'), schedule_id=schedule['id'], reviewed_content_digest=schedule['content_digest'])
    with denied(c.db, 'HCP'):
        c.insert('review_outcomes', **values)
    actor(c.db, c.hcp, ['clinical.case_review'])
    with denied(c.db, 'stale'):
        c.insert('review_outcomes', **{**values, 'reviewer_id': c.hcp, 'reviewed_content_digest': '0' * 64})
    outcome = c.insert('review_outcomes', **{**values, 'reviewer_id': c.hcp})
    actor(c.db, c.owner)
    verification = {'schema': 'schedule-verification.v1', 'schedule_digest': schedule['content_digest'],
        'entry_digest': entry['content_digest'], 'explicit': True, 'confirmation_key': str(uuid4()), 'review_outcome_id': str(outcome['id'])}
    row = c.repo._one("UPDATE msa.medication_schedules SET verification_status='HCP_VERIFIED',verification_evidence=%s,verified_at=clock_timestamp() WHERE id=%s RETURNING *", (Jsonb(verification), schedule['id']))
    assert row['verification_status'] == 'HCP_VERIFIED'


def test_expired_case_permission_does_not_allow_access(domain):
    c = domain
    case, _ = c.case()
    before = datetime.now(timezone.utc)
    c.insert('review_case_permissions', user_id=c.owner, case_id=case['id'], hcp_id=c.hcp, consent_evidence=evidence(),
             granted_at=before-timedelta(days=2), expires_at=before-timedelta(days=1))
    with denied(c.db, 'consent'):
        c.db.execute("UPDATE msa.review_cases SET assigned_hcp_id=%s,status='OPEN' WHERE id=%s", (c.hcp, case['id']))
    actor(c.db, c.hcp, ['clinical.case_review'])
    assert not c.db.execute('SELECT msa.can_access_case(%s,%s)', (case['id'], c.owner)).fetchone()[0]


def test_share_rejects_unknown_sections_and_expired_grants(domain):
    c = domain
    summary = c.summary()
    values = dict(user_id=c.owner, summary_id=summary['id'], hcp_id=c.hcp, scope='SECTIONS',
                  allowed_sections=['unknown'], consent_evidence=evidence())
    with denied(c.db, 'Unknown shared section'):
        c.insert('summary_shares', **values)
    before = datetime.now(timezone.utc)
    share = c.insert('summary_shares', **{**values, 'allowed_sections': ['medicines'],
                       'granted_at': before-timedelta(days=2), 'expires_at': before-timedelta(days=1)})
    actor(c.db, c.hcp, ['clinical.case_review'])
    with denied(c.db, 'denied'):
        c.db.execute('SELECT msa.shared_summary(%s)', (share['id'],))


def test_missing_context_cannot_use_summary_definer_or_stale_permissions(domain):
    c = domain
    summary = c.summary()
    share = c.insert('summary_shares', user_id=c.owner, summary_id=summary['id'], hcp_id=c.hcp,
        scope='FULL', allowed_sections=[], consent_evidence=evidence())
    c.db.execute("SELECT set_config('msa.authenticated_owner','',true),set_config('msa.authenticated_permissions','[\"clinical.case_review\",\"admin.audit\"]',true)")
    assert c.db.execute('SELECT msa.has_server_permission(%s)',('admin.audit',)).fetchone()[0] is False
    assert c.db.execute('SELECT msa.can_access_summary(%s,%s)',(summary['id'],c.owner)).fetchone()[0] is False
    with denied(c.db,'missing authenticated context'):
        c.db.execute('SELECT msa.shared_summary(%s)',(share['id'],))


def test_dose_timestamp_must_be_an_occurrence_in_schedule_timezone(domain):
    c = domain
    schedule, _ = c.schedule(verified=True)
    with denied(c.db, 'outside the exact schedule'):
        c.insert('dose_records', user_id=c.owner, schedule_id=schedule['id'],
                 scheduled_for=datetime(2026, 11, 21, 8, tzinfo=timezone.utc), dose_status='TAKEN')


def test_patient_cannot_confirm_invented_time_as_prescription_transcription(domain):
    c = domain
    schedule, entry = c.schedule(schedule_details={'schema':'schedule.v1','times':['09:00'],'dose_raw':'one tablet'})
    with denied(c.db, 'copied instructions'):
        c.confirm(schedule, entry)


def test_schedule_confirmation_key_cannot_be_reused_for_another_version(domain):
    c=domain
    first,_=c.schedule(verified=True)
    second,entry=c.schedule()
    with denied(c.db,'schedule_confirmation_once'):
        c.confirm(second,entry,confirmation_key=first['verification_evidence']['confirmation_key'])


def test_row_security_filters_other_patient_without_trusting_role_alone(domain):
    c = domain
    c.insert('medication_cabinet_items', user_id=c.owner, medication_name_raw='Owner synthetic box')
    actor(c.db, c.other)
    c.insert('medication_cabinet_items', user_id=c.other, medication_name_raw='Other synthetic box')
    actor(c.db, c.owner, ['clinical.case_review'])
    role = 'sad_read_' + uuid4().hex
    c.db.execute(sql.SQL('CREATE ROLE {} NOLOGIN').format(sql.Identifier(role)))
    c.db.execute(sql.SQL('GRANT USAGE ON SCHEMA msa TO {}').format(sql.Identifier(role)))
    c.db.execute(sql.SQL('GRANT SELECT ON msa.medication_cabinet_items TO {}').format(sql.Identifier(role)))
    c.db.execute(sql.SQL('SET LOCAL ROLE {}').format(sql.Identifier(role)))
    rows = c.db.execute('SELECT medication_name_raw FROM msa.medication_cabinet_items').fetchall()
    assert rows == [('Owner synthetic box',)]
    c.db.execute('RESET ROLE')


def test_domain_changes_append_business_audit_without_patient_payload(domain):
    c = domain
    row = c.insert('medication_cabinet_items', user_id=c.owner, medication_name_raw='Private synthetic box')
    audit = c.db.execute("SELECT actor_user_id,subject_user_id,details FROM msa.audit_events WHERE resource_type='msa.medication_cabinet_items' AND resource_id=%s", (str(row['id']),)).fetchone()
    assert audit[0] == c.owner and audit[1] == c.owner
    assert 'Private synthetic box' not in json.dumps(audit[2]) and audit[2]['current_digest']


def assert_system_contract(db):
    contract = json.loads((ROOT / 'db/schema_contract.json').read_text(encoding='utf-8'))
    assert contract['system']['migrations'] == [p.name for p in sorted((ROOT/'db/migrations').glob('[0-9][0-9][0-9]_*.sql'))]
    names = {r[0] for r in db.execute("SELECT schemaname||'.'||tablename FROM pg_tables WHERE schemaname IN ('msa','msa_ref')")}
    assert names == {t['name'] for t in contract['tables']} and len(names) == 36
    baseline = [t for t in contract['tables'] if t['name'] in contract['baseline']['tables']]
    assert len(baseline) == 20 and sum(len(t['columns']) for t in baseline) == 193
    for table in contract['tables']:
        rows = db.execute("""SELECT a.attname,t.typname,NOT a.attnotnull,a.attgenerated
            FROM pg_attribute a JOIN pg_type t ON t.oid=a.atttypid
            WHERE a.attrelid=%s::regclass AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum""", (table['name'],)).fetchall()
        expected = [(c['name'], {'integer':'int4','bigint':'int8','boolean':'bool'}.get(c['type'],c['type']), c['nullable'], 's' if c['default']=='GENERATED ALWAYS' else '') for c in table['columns']]
        assert rows == expected, table['name']
        keys = db.execute("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid=%s::regclass AND contype='c'", (table['name'],)).fetchall()
        assert {r[0] for r in keys} == {r['definition'] for r in table['checks']}
        pk = db.execute("""SELECT a.attname FROM pg_constraint c CROSS JOIN LATERAL unnest(c.conkey) WITH ORDINALITY k(num,ord)
            JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=k.num WHERE c.conrelid=%s::regclass AND c.contype='p' ORDER BY k.ord""", (table['name'],)).fetchall()
        assert [r[0] for r in pk] == table['primary_key']
        schema, name = table['name'].split('.')
        indexes = db.execute('SELECT indexname,indexdef FROM pg_indexes WHERE schemaname=%s AND tablename=%s', (schema,name)).fetchall()
        assert set(indexes) == {(r['name'],r['definition']) for r in table['indexes']}, table['name']
        triggers = db.execute('SELECT tgname,pg_get_triggerdef(oid) FROM pg_trigger WHERE tgrelid=%s::regclass AND NOT tgisinternal', (table['name'],)).fetchall()
        assert set(triggers) == {(r['name'],r['definition']) for r in table['triggers']}, table['name']
        security = db.execute('SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid=%s::regclass', (table['name'],)).fetchone()
        assert security == (table['row_security'],table['row_security_forced']), table['name']
        policies = db.execute('SELECT policyname,cmd,qual,with_check FROM pg_policies WHERE schemaname=%s AND tablename=%s', (schema,name)).fetchall()
        assert set(policies) == {(r['name'],r['command'],r['using'],r['with_check']) for r in table['policies']}, table['name']
    fk = db.execute("SELECT confupdtype,confdeltype FROM pg_constraint WHERE contype='f' AND connamespace IN ('msa'::regnamespace,'msa_ref'::regnamespace)").fetchall()
    assert len(fk) == 71 and all(r == ('r','r') for r in fk)


def test_full_system_schema_matches_contract_and_preserves_core_v4(domain):
    assert_system_contract(domain.db)


@pytest.mark.parametrize('start_from_v4,fail_once', [(False,False),(True,False),(True,True)])
def test_fresh_and_preserving_upgrade_with_atomic_rollback(start_from_v4,fail_once):
    dsn=os.environ.get('SYSTEM_UPGRADE_TEST_DSN')
    if not dsn:
        pytest.skip('SYSTEM_UPGRADE_TEST_DSN identifies a schema-empty dedicated upgrade test DB')
    from db.manage import migrate,TEST_MARKER,provision_identity_registry
    with psycopg.connect(dsn,autocommit=True) as db:
        assert db.info.host in ('127.0.0.1','localhost','::1') and db.info.dbname.startswith('msa_core_test_v4systemupgrade')
        assert db.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()").fetchone()[0]==TEST_MARKER
        assert db.execute("SELECT to_regnamespace('msa')").fetchone()[0] is None
        with db.transaction(force_rollback=True):
            assert provision_identity_registry(db)['created'] is True
            assert provision_identity_registry(db)['created'] is False
            if start_from_v4:
                paths=sorted((ROOT/'db/migrations').glob('*.sql'))[:2]
                for path in paths:
                    db.execute(path.read_text(encoding='utf-8'))
                hashes={path.name:hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
                ledger={'version':4,'migration_sha256':hashes['001_v4.sql'],'migrations':hashes,'hash_contract':'pg-jsonb-text-v4'}
                db.execute(sql.SQL('COMMENT ON SCHEMA msa IS {}').format(sql.Literal(json.dumps(ledger))))
                owner,other,hcp=uuid4(),uuid4(),uuid4()
                db.execute('INSERT INTO identity.users(id) VALUES(%s),(%s),(%s)',(owner,other,hcp))
                actor(db,owner)
                ctx=Context(db,owner,other,hcp)
                entry=ctx.entry()
                summary=ctx.summary()
                baseline=json.loads((ROOT/'db/schema_contract.json').read_text(encoding='utf-8'))['baseline']['tables']
                def fingerprints():
                    return {table:db.execute(sql.SQL("SELECT count(*),md5(coalesce(string_agg(md5(to_jsonb(t)::text),'' ORDER BY md5(to_jsonb(t)::text)),'')) FROM {} t").format(sql.Identifier(*table.split('.')))).fetchone() for table in baseline}
                before=fingerprints()
                if fail_once:
                    with pytest.raises(RuntimeError,match='Synthetic post-upgrade failure'):
                        with db.transaction():
                            migrate(db)
                            assert_system_contract(db)
                            raise RuntimeError('Synthetic post-upgrade failure')
                    assert db.execute("SELECT to_regclass('msa.medication_schedules')").fetchone()[0] is None
                    assert fingerprints()==before
                    assert json.loads(db.execute("SELECT obj_description('msa'::regnamespace,'pg_namespace')").fetchone()[0])==ledger
                applied=migrate(db)
                assert applied['applied_migrations']==['003_system_domains.sql','004_domain_access_and_audit.sql','005_schedule_runtime_guard.sql']
                assert fingerprints()==before
                assert db.execute('SELECT content_digest,confirmed_at FROM msa.medication_entry_versions WHERE id=%s',(entry['id'],)).fetchone()==(entry['content_digest'],entry['confirmed_at'])
                assert db.execute('SELECT confirmation_digest FROM msa.patient_health_summaries WHERE id=%s',(summary['id'],)).fetchone()[0]==summary['confirmation_digest']
            else:
                assert len(migrate(db)['applied_migrations'])==5
            assert_system_contract(db)
            assert migrate(db)['applied_migrations']==[]
        assert db.execute("SELECT to_regnamespace('msa'),to_regnamespace('identity')").fetchone()==(None,None)
        print('\nSCHEMA TEST CLEANUP: all schema/data changes rolled back; existing DBs untouched')


@pytest.mark.parametrize('id_type',['uuid','text'])
def test_identity_install_preserves_existing_rows_and_refuses_wrong_type(id_type):
    dsn=os.environ.get('SYSTEM_UPGRADE_TEST_DSN')
    if not dsn:
        pytest.skip('SYSTEM_UPGRADE_TEST_DSN required')
    from db.manage import provision_identity_registry,TEST_MARKER
    with psycopg.connect(dsn,autocommit=True) as db:
        assert db.info.dbname.startswith('msa_core_test_v4systemupgrade')
        assert db.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()").fetchone()[0]==TEST_MARKER
        with db.transaction(force_rollback=True):
            db.execute('CREATE SCHEMA identity')
            db.execute(sql.SQL('CREATE TABLE identity.users(id {} PRIMARY KEY)').format(sql.SQL(id_type)))
            value=uuid4() if id_type=='uuid' else 'synthetic-original-id'
            db.execute('INSERT INTO identity.users(id) VALUES(%s)',(value,))
            if id_type=='uuid':
                assert provision_identity_registry(db)['created'] is False
            else:
                with pytest.raises(RuntimeError,match='existing identity.users'):
                    provision_identity_registry(db)
            assert db.execute('SELECT id FROM identity.users').fetchone()[0]==value
        assert db.execute("SELECT to_regnamespace('identity')").fetchone()[0] is None


def test_nonprivileged_hcp_reads_only_case_context_and_can_record_outcome(domain):
    c = domain
    case, schedule = c.case()
    permit = c.permit_case(case)
    summary = c.summary()
    role = 'sad_hcp_' + uuid4().hex
    c.db.execute(sql.SQL('CREATE ROLE {} NOLOGIN').format(sql.Identifier(role)))
    c.db.execute(sql.SQL('GRANT USAGE ON SCHEMA msa,msa_ref,identity TO {}').format(sql.Identifier(role)))
    c.db.execute(sql.SQL('GRANT SELECT,INSERT,UPDATE ON ALL TABLES IN SCHEMA msa TO {}').format(sql.Identifier(role)))
    c.db.execute(sql.SQL('GRANT SELECT ON ALL TABLES IN SCHEMA msa_ref,identity TO {}').format(sql.Identifier(role)))
    actor(c.db, c.hcp, ['clinical.case_review'])
    c.db.execute(sql.SQL('SET LOCAL ROLE {}').format(sql.Identifier(role)))
    assert c.db.execute('SELECT id FROM msa.medication_schedules').fetchall() == [(schedule['id'],)]
    assert c.db.execute('SELECT count(*) FROM msa.medication_entry_versions').fetchone()[0] == 1
    assert c.db.execute('SELECT count(*) FROM msa.patient_health_summaries').fetchone()[0] == 0
    c.insert('review_outcomes',user_id=c.owner,case_id=case['id'],reviewer_id=c.hcp,review_type='SCHEDULE',
        decision='APPROVED',evidence=evidence('review-evidence.v1'),schedule_id=schedule['id'],reviewed_content_digest=schedule['content_digest'])
    assert c.db.execute("SELECT count(*) FROM msa.audit_events WHERE actor_user_id=%s", (c.hcp,)).fetchone()[0] == 1
    c.db.execute('RESET ROLE')
    actor(c.db,c.owner)
    c.db.execute('UPDATE msa.review_case_permissions SET revoked_at=clock_timestamp() WHERE id=%s', (permit['id'],))
    actor(c.db,c.hcp,['clinical.case_review'])
    c.db.execute(sql.SQL('SET LOCAL ROLE {}').format(sql.Identifier(role)))
    assert c.db.execute('SELECT count(*) FROM msa.medication_schedules').fetchone()[0] == 0
    assert c.db.execute('SELECT count(*) FROM msa.medication_entry_versions').fetchone()[0] == 0
    c.db.execute('RESET ROLE')
