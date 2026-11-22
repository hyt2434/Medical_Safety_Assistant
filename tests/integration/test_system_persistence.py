"""Actual transactions: confirmed M1-3 -> scoped HCP review -> reminder/doses.

Uses existing approved reference data and exact-owner administrative teardown.
No model inference is needed here; real Qwen/Whisper remain in sources_real_e2e.
"""
from contextlib import ExitStack
from datetime import datetime, timezone, date
from uuid import uuid4
import os
from psycopg import sql
import pytest
import psycopg

from shared.db import CoreRepository, DomainRepository
from shared.db.intake_adapter import persist_module1
from shared.db.identification_adapter import run_identification
from shared.db.safety_adapter import run_safety
from tests.db_cleanup import isolated_core_owner
from tests.integration.test_module1_sources_real_e2e import case, counts, postgres_repo, ddinter


def evidence():
    return {'schema': 'consent.v1', 'sources': [{'locator': 'test://explicit-synthetic-consent', 'sha256': '1'*64}]}


def test_real_persistence_hcp_schedule_reminder_doses_and_prior_setting_preservation(case):
    original_repo, build, products, dataset = case
    with ExitStack() as cleanup:
        hcp_id = cleanup.enter_context(isolated_core_owner(original_repo.db))
        owner = cleanup.enter_context(isolated_core_owner(original_repo.db))
        repo = CoreRepository(original_repo.db, authenticated_owner=owner)
        patient = DomainRepository(repo.db, authenticated_actor=repo.owner)
        chat = repo.create_conversation()
        intake = repo.create_intake(chat['id'])
        entries, matches = [], []
        for product in products.values():
            before = counts(repo)
            raw = product['brand_name'] + ', 1 viên lúc 08:00'
            med = {'name_raw': product['brand_name'], 'dose_raw': '1 viên',
                   'administrations': [{'timing_raw':'08:00','dose_raw':'1 viên'}], 'evidence_text': raw}
            saved = persist_module1(repo, intake['id'], raw.encode(), {'medications':[med]}, modality='TEXT',
                input_payload={'schema':'input.v4','digest_basis':'ORIGINAL_BYTES','text':raw},
                extractor_name='EXPLICIT_SYNTHETIC_FIXTURE', extractor_version='system.v1')
            entry = saved['entries'][0]
            assert counts(repo) == before
            entry = repo.confirm_entry(entry['id'],entry['content_digest'],uuid4(),explicit_confirmation=True)
            match, _ = run_identification(repo,entry['id'],dataset_build=build)
            assert match['match_status']=='SELECTED' and match['product_id']==product['id']
            entries.append(entry)
            matches.append((entry['id'],match['id']))
        snap = repo.create_snapshot(matches,data_context='SYNTHETIC_TEST')
        assessment, result = run_safety(repo,snap['id'],dataset)
        assert assessment['check_results']['ddi']['coverage']=='PARTIAL' and result['safe_to_take'] is None
        details = {'schema':'schedule.v1','times':['08:00'],'dose_raw':'1 viên'}
        schedule = patient.save_schedule(entries[0]['id'],details,'Asia/Ho_Chi_Minh')
        schedule = patient.confirm_schedule(schedule['id'],schedule['content_digest'],uuid4(),explicit_confirmation=True)
        preferences = {'schema':'notification-preferences.v1','channel':'IN_APP'}
        with pytest.raises(psycopg.Error,match='HCP approval'):
            patient.set_reminder(schedule['id'],enabled=True,preferences=preferences,assessment=assessment['id'])
        # A new revision records the requested schedule for a bounded HCP review.
        reviewed = patient.save_schedule(entries[0]['id'],details,'Asia/Ho_Chi_Minh',origin='PROPOSED_CHANGE',supersedes=schedule['id'])
        case_row = patient.create_case('SCHEDULE',schedule=reviewed['id'],assessment=assessment['id'])
        permit = patient.grant_case_access(case_row['id'],hcp_id,evidence())
        patient.assign_case(case_row['id'],hcp_id)
        hcp = DomainRepository(repo.db,authenticated_actor=hcp_id,permissions=['clinical.case_review'])
        hcp.case_message(case_row['id'],'Synthetic review of exact instructions and assessment limitations')
        outcome = hcp.record_review(case_row['id'],'APPROVED',{'schema':'review-evidence.v1','sources':evidence()['sources']})
        reviewed = patient.confirm_schedule(reviewed['id'],reviewed['content_digest'],uuid4(),explicit_confirmation=True,review_outcome=outcome['id'])
        setting = patient.set_reminder(reviewed['id'],enabled=True,preferences=preferences,assessment=assessment['id'])
        assert setting['enabled'] and setting['eligibility_status']=='ELIGIBLE'
        assert repo._owned('safety_assessments',assessment['id'])['check_results']['ddi']['coverage']=='PARTIAL'
        when = datetime(2026,11,21,1,tzinfo=timezone.utc)
        dose = patient.record_dose(reviewed['id'],when,'TAKEN')
        assert patient.record_dose(reviewed['id'],when,'TAKEN')['id']==dose['id']
        corrected = patient.record_dose(reviewed['id'],when,'SKIPPED',supersedes=dose['id'])
        assert corrected['supersedes_record_id']==dose['id']
        proposal = patient.request_schedule_change(reviewed['id'],{**details,'times':['09:00']})
        assert proposal['status']=='PENDING'
        new_schedule = patient.save_schedule(entries[0]['id'],{**details,'times':['09:00']},'Asia/Ho_Chi_Minh',origin='PROPOSED_CHANGE',supersedes=reviewed['id'])
        assert new_schedule['verification_status']=='UNVERIFIED'
        assert patient._one('SELECT enabled FROM msa.reminder_settings WHERE id=%s',(setting['id'],))['enabled'] is True
        with pytest.raises(psycopg.Error):
            patient.set_reminder(new_schedule['id'],enabled=True,preferences=preferences,assessment=assessment['id'])
        patient.revoke_access(permit['id'])
        with pytest.raises(PermissionError):
            hcp.case_message(case_row['id'],'Forbidden after revocation')
        assert patient._one('SELECT enabled FROM msa.reminder_settings WHERE id=%s',(setting['id'],))['enabled'] is True
        boxes = [patient.add_cabinet_item('Synthetic unidentified box',expires_on=d) for d in [date(2026,12,1),date(2027,1,1),None]]
        assert len({b['id'] for b in boxes})==3


def test_real_pool_reuse_does_not_leak_owner_or_permissions(postgres_repo):
    from sqlalchemy.pool import QueuePool
    repo=postgres_repo
    role='sad_app_'+uuid4().hex
    with isolated_core_owner(repo.db) as other:
        with repo.db.transaction():
            repo.db.execute(sql.SQL('CREATE ROLE {} NOLOGIN NOSUPERUSER NOBYPASSRLS').format(sql.Identifier(role)))
            repo.db.execute(sql.SQL('GRANT USAGE ON SCHEMA msa TO {}').format(sql.Identifier(role)))
            repo.db.execute(sql.SQL('GRANT SELECT,INSERT,UPDATE ON msa.medication_cabinet_items,msa.audit_events TO {}').format(sql.Identifier(role)))
        def creator():
            c=psycopg.connect(os.environ['MODULE2_TEST_DSN'],autocommit=True)
            c.execute(sql.SQL('SET ROLE {}').format(sql.Identifier(role)))
            return c
        pool=QueuePool(creator,pool_size=1,max_overflow=0)
        try:
            physical_pid=None
            for owner,label,permissions in [(repo.owner,'First synthetic box',['clinical.case_review']), (other,'Second synthetic box',[])]:
                lease=pool.connect()
                try:
                    c=lease.driver_connection
                    flags=c.execute('SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user').fetchone()
                    assert flags==(False,False)
                    pid=c.execute('SELECT pg_backend_pid()').fetchone()[0]
                    assert physical_pid is None or pid==physical_pid
                    physical_pid=pid
                    # A dirty baseline must also be discarded before an operation.
                    c.execute("SELECT set_config('msa.authenticated_owner',%s,false),set_config('msa.authenticated_permissions','[\"admin.audit\"]',false)",(str(uuid4()),))
                    scoped=DomainRepository(c,authenticated_actor=owner,permissions=permissions)
                    scoped.add_cabinet_item(label)
                    assert [r['medication_name_raw'] for r in scoped._all('SELECT medication_name_raw FROM msa.medication_cabinet_items')]==[label]
                    empty=c.execute("SELECT current_setting('msa.authenticated_owner',true),current_setting('msa.authenticated_permissions',true)").fetchone()
                    assert empty==('','[]')
                    assert c.execute('SELECT count(*) FROM msa.medication_cabinet_items').fetchone()[0]==0
                    with pytest.raises(psycopg.Error):
                        c.execute("INSERT INTO msa.medication_cabinet_items(user_id,medication_name_raw) VALUES(%s,'Forbidden without context')",(owner,))
                finally:
                    lease.close()
        finally:
            pool.dispose()
            with repo.db.transaction():
                repo.db.execute(sql.SQL('REVOKE ALL ON msa.medication_cabinet_items,msa.audit_events FROM {}').format(sql.Identifier(role)))
                repo.db.execute(sql.SQL('REVOKE ALL ON SCHEMA msa FROM {}').format(sql.Identifier(role)))
                repo.db.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(role)))
