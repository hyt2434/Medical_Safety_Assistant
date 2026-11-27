"""Opt-in browser + actual local models on marked PostgreSQL TEST stores only.

No dev database teardown, reference import, schema migration or generated report.
The CLI branch is a read-only oracle used by the browser test, never an API.
"""
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile
from uuid import UUID, uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict
import pytest

from tests.integration.test_module1_sources_real_e2e import case, postgres_repo, ddinter
from tests.db_cleanup import isolated_core_owner

ROOT = Path(__file__).resolve().parents[2]


def oracle(request):
    dsn = os.environ['E2E_CORE_DSN']
    options = conninfo_to_dict(dsn)
    assert options.get('host') in ('127.0.0.1', 'localhost')
    assert options['dbname'].startswith('msa_core_test_v4') and options['dbname'].endswith('checks')
    owner = UUID(os.environ['UI_ACCOUNT_ID'])
    with psycopg.connect(dsn, autocommit=True) as db:
        assert db.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()").fetchone()[0] == 'Medication Safety Assistant Core V4 isolated test'
        db.execute('SET default_transaction_read_only=on')
        counts = {t: db.execute(sql.SQL('SELECT count(*) FROM msa.{} WHERE user_id=%s').format(sql.Identifier(t)), (owner,)).fetchone()[0]
                  for t in ('entry_matches', 'medication_list_snapshots', 'safety_assessments')}
        output = {'counts': counts}
        workflow_id = request.get('workflow_id')
        if workflow_id:
            wf = db.execute('SELECT context,intake_session_id FROM msa.workflow_instances WHERE id=%s AND user_id=%s', (UUID(workflow_id),owner)).fetchone()
            assert wf
            entries = []
            for entry_id in wf[0].get('entry_version_ids', []):
                row = db.execute('SELECT medication_fields,confirmed_at FROM msa.medication_entry_versions WHERE id=%s AND user_id=%s',(UUID(entry_id),owner)).fetchone()
                entries.append({'id':entry_id,'medication':row[0],'confirmed':row[1] is not None})
            output['entries'] = entries
            output['inputs'] = [{'modality':modality,'digest':digest,'payload':payload} for modality,digest,payload in db.execute(
                'SELECT modality,input_digest,payload_or_locator FROM msa.intake_inputs WHERE session_id=%s AND user_id=%s ORDER BY created_at,id',(wf[1],owner))]
            output['matches'] = [{'entry_id':str(e),'status':status,'product_id':str(p) if p else None,'source_id':source,
                                  'name':name,'ingredients':ingredients} for e,status,p,source,name,ingredients in db.execute('''
                SELECT em.entry_version_id,em.match_status,em.product_id,m.source_medication_id,m.brand_name,
                 (SELECT coalesce(jsonb_agg(jsonb_build_object('name',c.ingredient_name_raw,'raw',c.ingredient_text_raw) ORDER BY c.ordinal),'[]'::jsonb)
                  FROM msa_ref.medication_ingredients c WHERE c.medication_id=m.id AND c.dataset_build=m.dataset_build)
                FROM msa.entry_matches em LEFT JOIN msa_ref.medications m ON m.id=em.product_id AND m.dataset_build=em.reference_build
                WHERE em.user_id=%s AND em.entry_version_id=ANY(%s) ORDER BY em.created_at''',(owner,[UUID(e['id']) for e in entries]))]
        if request.get('assessment_id'):
            assessment = db.execute('SELECT execution_status,check_results FROM msa.safety_assessments WHERE id=%s AND user_id=%s', (UUID(request['assessment_id']),owner)).fetchone()
            assert assessment
            findings = db.execute('SELECT severity,source_severity,evidence FROM msa.safety_findings WHERE assessment_id=%s AND user_id=%s',(UUID(request['assessment_id']),owner)).fetchall()
            from module3_interactions.official_ddinter.dataset import OfficialDataset
            source = OfficialDataset().lookup('DDInter14','DDInter1174')
            assert source['status'] == 'INTERACTION_DETECTED' and source['original_level'] == 'Moderate'
            control = source['source_records'][0]
            assert hashlib.sha256((ROOT/'data/DDInter'/control['evidence']['filename']).read_bytes()).hexdigest() == control['evidence']['csv_sha256']
            assert any(level == 'Moderate' and any(record.get('record') == control for record in evidence.get('sources',[]))
                       for _,level,evidence in findings), 'Module 3 must retain the exact source control record'
            output['assessment'] = {'execution':assessment[0],'checks':assessment[1],
                'source_levels':[level for _,level,_ in findings],'control_pair':['DDInter14','DDInter1174'],
                'control_level':source['original_level'],'control_source_hash':control['evidence']['csv_sha256']}
        return output


@pytest.mark.skipif(os.environ.get('INTAKE_RUN_REAL_BROWSER')!='1', reason='Opt-in real browser/Qwen/Whisper/Tesseract')
def test_four_browser_sources_with_real_models_and_test_database(case, monkeypatch):
    repo,build,_,_=case
    from sqlalchemy import text
    from sqlalchemy.engine import make_url
    from shared.auth.db import engine,reset_connection,initialize
    from shared.auth.core_owner import ensure_account
    url=os.environ['RBAC_POSTGRES_TEST_URL']; parsed=make_url(url)
    assert parsed.host in ('127.0.0.1','localhost') and parsed.database.startswith('msa_auth_test_')
    monkeypatch.setenv('AUTH_DATABASE_URL',url);monkeypatch.setenv('AUTH_SEED_DEMO','0');monkeypatch.setenv('AUTH_ENV','test')
    reset_connection()
    with engine().connect() as auth:
        assert auth.execute(text("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")).scalar_one()=='Medication Safety Assistant Auth isolated test'
        assert auth.execute(text('SELECT version_num FROM auth_alembic_version')).scalar_one()=='auth_005'
    initialize()
    tables=('users','user_roles','auth_sessions','audit_events','login_throttles','roles','permissions','role_permissions')
    with engine().connect() as auth:
        before={t:auth.execute(text('SELECT count(*) FROM '+t)).scalar_one() for t in tables}
        original_audit=auth.execute(text('SELECT to_jsonb(t) FROM audit_events t ORDER BY event_id')).scalars().all()
        peer_key=hashlib.sha256(b'peer:127.0.0.1').hexdigest()
        peer_before=auth.execute(text('SELECT key_hash,expires_at,attempts FROM login_throttles WHERE key_hash=:key'),{'key':peer_key}).mappings().first()
    password=secrets.token_urlsafe(24)
    with isolated_core_owner(repo.db) as other:
        ids=[str(repo.owner),str(other),str(uuid4())]
        emails=['browser-'+identity+'@example.test' for identity in ids]
        try:
            for identity,email in zip(ids,emails):
                ensure_account(identity,email=email,password=password,full_name='Synthetic browser acceptance')
            with tempfile.TemporaryDirectory(prefix='.ui-real-',dir=ROOT/'apps/frontend') as temporary:
                assert Path(temporary).resolve().is_relative_to((ROOT/'apps/frontend').resolve())
                env=os.environ.copy();env.update(INTAKE_REAL_E2E='1',E2E_PYTHON=sys.executable,E2E_CORE_DSN=os.environ['MODULE2_TEST_DSN'],
                    E2E_AUTH_URL=url,E2E_REFERENCE_BUILD=build,E2E_OUTPUT_DIR=str(Path(temporary)/'results'),
                    UI_ACCOUNT_ID=ids[0],UI_EMAIL=emails[0],UI_OTHER_ID=ids[1],UI_OTHER_EMAIL=emails[1],UI_UNLINKED_EMAIL=emails[2],UI_PASSWORD=password,
                    HF_HOME=str(ROOT/'artifacts/voice_manual_input/huggingface'),HF_HUB_OFFLINE='1',WHISPER_MODEL_SIZE='small',
                    UI_OCR_IMAGE=str(ROOT/'data/local/module1/runs/ee43ee07-717a-4e9f-81f9-dce85389b23d/original.png'),
                    MSA_DDINTER_INDEX=str(ROOT/'data/DDInter/official.sqlite'))
                result=subprocess.run([shutil.which('node'),'node_modules/@playwright/test/cli.js','test','tests/intake-real.spec.ts'],cwd=ROOT/'apps/frontend',env=env)
                assert result.returncode==0,'See browser assertions above; no inference retry is performed'
        finally:
            # Only our three generated identities and this run's anonymous provisioning events.
            with engine().begin() as auth:
                auth.execute(text("SET LOCAL session_replication_role='replica'"))
                params={'ids':ids}
                deleted={'audit_events':auth.execute(text('DELETE FROM audit_events WHERE actor_user_id=ANY(CAST(:ids AS uuid[])) OR (actor_user_id IS NULL AND action_code=\'account.created\' AND target_id=ANY(CAST(:ids AS text[])))'),params).rowcount}
                for table in ('auth_sessions','user_roles','users'):
                    deleted[table]=auth.execute(text('DELETE FROM '+table+' WHERE user_id=ANY(CAST(:ids AS uuid[]))'),params).rowcount
                keys=[hashlib.sha256(value.encode()).hexdigest() for value in ['account:'+e for e in emails]+['peer:127.0.0.1']]
                deleted['login_throttles']=auth.execute(text('DELETE FROM login_throttles WHERE key_hash=ANY(:keys)'),{'keys':keys}).rowcount
                if peer_before:
                    auth.execute(text('INSERT INTO login_throttles (key_hash,expires_at,attempts) VALUES (:key_hash,:expires_at,:attempts)'),dict(peer_before))
            with engine().connect() as auth:
                assert {t:auth.execute(text('SELECT count(*) FROM '+t)).scalar_one() for t in tables}==before
                assert auth.execute(text('SELECT to_jsonb(t) FROM audit_events t ORDER BY event_id')).scalars().all()==original_audit
                assert auth.exec_driver_sql('SHOW session_replication_role').scalar_one()=='origin'
            print('\nBROWSER AUTH CLEANUP:',deleted,'remaining=0; existing audit unchanged; guards=origin')
            reset_connection()


if __name__=='__main__':
    print(json.dumps(oracle(json.loads(sys.stdin.read())),ensure_ascii=False,default=str))
