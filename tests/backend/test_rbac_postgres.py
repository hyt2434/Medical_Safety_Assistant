"""Real PostgreSQL API/grant concurrency; clean exactly this run's UUIDs/keys."""
import hashlib
import os
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text, event
from sqlalchemy.orm import Session
from sqlalchemy.exc import DBAPIError
from sqlalchemy.engine import make_url
from shared.auth.db import reset_connection, initialize, transaction, engine
from shared.auth.models import User, Role, UserRole, AuditEvent
from shared.auth.passwords import hash_password
from shared.auth.sessions import timestamp, now, audit
from apps.backend.api.app import app


@pytest.mark.skipif(not os.environ.get('RBAC_POSTGRES_TEST_URL'), reason='Set dedicated RBAC_POSTGRES_TEST_URL')
def test_postgres_migration_sessions_and_concurrent_grants(monkeypatch):
    url = os.environ['RBAC_POSTGRES_TEST_URL']
    parsed = make_url(url)
    assert parsed.host in ('127.0.0.1', 'localhost') and parsed.database.startswith('msa_auth_test_')
    monkeypatch.setenv('AUTH_DATABASE_URL', url)
    monkeypatch.setenv('AUTH_SEED_DEMO', '0')
    reset_connection()
    with engine().begin() as db:
        assert db.execute(text("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")).scalar_one() == 'Medication Safety Assistant Auth isolated test'
        db.execute(text("SET LOCAL session_replication_role='replica'"))
    initialize()
    from tests.backend.test_database_config import assert_migrated_auth_matches_models
    assert_migrated_auth_matches_models(engine())
    tables = ('users', 'roles', 'permissions', 'role_permissions', 'user_roles', 'auth_sessions', 'audit_events', 'login_throttles')
    with engine().connect() as db:
        assert db.execute(text("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")).scalar_one() == 'Medication Safety Assistant Auth isolated test'
        before = {t: db.execute(text(f'SELECT count(*) FROM {t}')).scalar_one() for t in tables}
        before_audit = db.execute(text('SELECT to_jsonb(t) FROM audit_events t ORDER BY event_id')).scalars().all()
    identities = [str(uuid4()), str(uuid4()), str(uuid4())]
    admin_id, identity, other_patient = identities
    emails = [value + '@example.com' for value in identities]
    unknown_email = uuid4().hex + '@example.com'
    orphan = str(uuid4())
    peer = 'synthetic-' + uuid4().hex
    throttle_keys = [hashlib.sha256(value.encode()).hexdigest() for value in
                     ['account:' + email for email in emails + [unknown_email]] + ['peer:' + peer]]
    params = {'admin': admin_id, 'patient': identity, 'other': other_patient}
    audit_ids = set()
    def capture_audit(session, context):
        # Includes our NULL/orphan actors; never delete another run's anonymous events.
        audit_ids.update(row.event_id for row in session.new if isinstance(row, AuditEvent) and row.event_id is not None)
    event.listen(Session, 'after_flush', capture_audit)
    try:
        with transaction() as db:
            roles = {role.role_code: role.role_id for role in db.scalars(select(Role))}
            for uid, email, role in zip(identities, emails, ('admin', 'patient', 'patient')):
                db.add(User(user_id=uid, email=email, password_hash=hash_password('Pg-test-2026'), full_name='' if uid == other_patient else 'Synthetic PostgreSQL test', account_status='active'))
                db.flush()
                db.add(UserRole(user_id=uid, role_id=roles[role], granted_at=timestamp()))
            audit(db, orphan, 'synthetic.missing_actor', target=identity)
            audit(db, orphan, 'account.created', target=identity)
            audit(db, other_patient, 'synthetic.empty_name', target=identity)
            audit(db, None, 'synthetic.unknown', target=identity)
        with TestClient(app, headers={'origin': 'http://127.0.0.1:5173'}, client=(peer, 50000)) as client:
            assert client.get('/api/admin/audit').status_code == 401
            assert client.post('/api/auth/login', json={'email': unknown_email, 'password': 'invalid-audit-login'}).status_code == 401
            assert client.post('/api/auth/login', json={'email': emails[0], 'password': 'Pg-test-2026'}).status_code == 200
            with engine().connect() as db:
                stored = db.execute(text('SELECT event_id,to_jsonb(t) FROM audit_events t ORDER BY event_id')).all()
            events = client.get('/api/admin/audit')
            assert events.status_code == 200
            events = events.json()['events']
            failed = next(e for e in events if e['id'] in audit_ids and e['actionCode'] == 'auth.login_failed')
            assert failed['actorUserId'] is None and failed['actorName'] == 'Chưa xác định' and failed['success'] is False
            system = next(e for e in events if e['actionCode'] == 'permission.introduced' and e['actorUserId'] is None)
            assert system['actorName'] == 'Hệ thống'
            user_event = next(e for e in events if e['actorUserId'] == admin_id and e['actionCode'] == 'auth.login')
            assert user_event['actorName'] == 'Synthetic PostgreSQL test'
            assert all(e['actorName'] == f'Tài khoản {orphan}' for e in events if e['actorUserId'] == orphan)
            empty_name = next(e for e in events if e['actionCode'] == 'synthetic.empty_name' and e['actorUserId'] == other_patient)
            assert empty_name['actorName'] == f'Tài khoản {other_patient}'
            unknown = next(e for e in events if e['actionCode'] == 'synthetic.unknown' and e['id'] in audit_ids)
            assert unknown['actorName'] == 'Chưa xác định'
            with engine().connect() as db:
                assert db.execute(text('SELECT event_id,to_jsonb(t) FROM audit_events t ORDER BY event_id')).all() == stored
            token = client.cookies.get('msa_session')
            def grant():
                with TestClient(app, headers={'origin': 'http://127.0.0.1:5173'}, client=(peer, 50000)) as parallel:
                    parallel.cookies.set('msa_session', token)
                    return parallel.post('/api/admin/role-grants', json={'userId': identity, 'roleCode': 'hcp', 'granted': True}).status_code
            with ThreadPoolExecutor(max_workers=3) as workers:
                assert list(workers.map(lambda _: grant(), range(3))) == [200, 200, 200]
            rows = client.get('/api/admin/accounts').json()['accounts']
            assert next(r for r in rows if r['id'] == identity)['roles'].count('hcp') == 1
            assert client.delete(f'/api/admin/users/{identity}/roles/hcp').status_code == 200
            assert client.post('/api/admin/role-grants', json={'userId': identity, 'roleCode': 'hcp', 'granted': True}).status_code == 200
            with transaction() as db:
                history = db.scalars(select(UserRole).where(UserRole.user_id == identity, UserRole.role_id == roles['hcp']).order_by(UserRole.granted_at)).all()
                assert len(history) == 2 and history[0].revoked_at is not None and history[1].revoked_at is None
                assert history[0].grant_id != history[1].grant_id
            assert client.delete(f'/api/admin/users/{identity}/roles/hcp').status_code == 200
            # Also exercise the SQL backstop, independently of API idempotency.
            future = now() + timedelta(minutes=1)
            def raw_grant(_):
                try:
                    with engine().begin() as db:
                        db.execute(text('INSERT INTO user_roles(grant_id,user_id,role_id,granted_at) VALUES(:id,:user,:role,:moment)'),
                            {'id':str(uuid4()),'user':identity,'role':roles['hcp'],'moment':future})
                    return 'created'
                except DBAPIError as error:
                    assert getattr(error.orig,'sqlstate',None) in ('23P01','P0001')
                    assert 'overlap' in str(error).lower()
                    return 'overlap-rejected'
            with ThreadPoolExecutor(max_workers=2) as workers:
                assert sorted(workers.map(raw_grant,range(2)))==['created','overlap-rejected']
            assert client.delete(f'/api/admin/users/{admin_id}/roles/admin').status_code == 409
            reset_connection()
            assert client.get('/api/admin/accounts').status_code == 200
            result = client.post('/api/auth/login', json={'email': emails[1], 'password': 'Pg-test-2026'})
            assert result.json()['roles'] == ['patient'] and result.json()['account']['id'] == identity
            assert client.get('/api/admin/accounts').status_code == 403
            assert client.get('/api/admin/audit').status_code == 403
            if os.environ.get('SYSTEM_TEST_DSN'):
                import psycopg
                from tests.db_cleanup import isolated_core_owner
                from shared.auth.core_owner import provision_core_identity
                monkeypatch.setenv('CORE_DB_DSN',os.environ['SYSTEM_TEST_DSN'])
                monkeypatch.setenv('CORE_REFERENCE_BUILD','463cd6c56dc5476fcabf5ad13405a909f3d0254a0043c3d5509140fb92ba1ab9')
                monkeypatch.setenv('CORE_USER_BINDINGS','{}')
                assert client.get('/api/v1/intake/capabilities').json()['persistent_intake'] is False
                for number, body in enumerate(({}, {'actor':admin_id, 'owner':other_patient,
                    'password':'private-denial-password','token':'private-denial-token',
                    'medication':'private-denial-medication'}), start=1):
                    assert client.post('/api/v1/intake/workflows',json=body).status_code==403
                    # A fresh connection sees durable denial events after HTTP 403.
                    with engine().connect() as db:
                        denied = db.execute(text("SELECT actor_user_id,target_type,target_id,success FROM audit_events WHERE event_id=ANY(:ids) AND action_code='intake.denied.core_link_missing'"), {'ids':list(audit_ids)}).all()
                    assert len(denied) == number
                    assert all(str(actor)==target==identity and kind=='account' and success is False
                               for actor,kind,target,success in denied)
                    print(f'\nCORE LINK DENIAL: request={number}; HTTP=403; committed_auth_events={len(denied)}; actor=target={identity}; reason=core_link_missing; success=false')
                with psycopg.connect(os.environ['SYSTEM_TEST_DSN'],autocommit=True) as core:
                    for table in ('conversation_sessions','conversation_messages','workflow_instances','intake_sessions',
                                  'intake_inputs','intake_extractions','intake_items','medication_entry_versions',
                                  'entry_matches','medication_list_snapshots','safety_assessments'):
                        assert core.execute(f'SELECT count(*) FROM msa.{table} WHERE user_id=%s',(identity,)).fetchone()[0]==0
                    assert core.execute('SELECT count(*) FROM msa.audit_events WHERE actor_user_id=%s OR subject_user_id=%s',(identity,identity)).fetchone()[0]==0
                    assert core.execute('SELECT 1 FROM identity.users WHERE id=%s',(identity,)).fetchone() is None
                    with isolated_core_owner(core,identity=identity):
                        assert str(provision_core_identity(identity,core))==identity
                        assert client.get('/api/v1/intake/capabilities').json()['persistent_intake'] is True
                        started=client.post('/api/v1/intake/workflows',json={})
                        assert started.status_code==200,started.text
                        workflow=started.json()['workflow_id']
                        assert str(core.execute('SELECT user_id FROM msa.workflow_instances WHERE id=%s',(workflow,)).fetchone()[0])==identity
                        assert client.post('/api/v1/intake/workflows',json={'owner':other_patient}).status_code==422
                        with engine().connect() as db:
                            assert db.execute(text("SELECT count(*) FROM audit_events WHERE actor_user_id=:id AND action_code='intake.denied.core_link_missing'"),{'id':identity}).scalar_one()==2
                            private_rows = db.execute(text('SELECT to_jsonb(t)::text FROM audit_events t WHERE event_id=ANY(:ids)'),{'ids':list(audit_ids)}).scalars().all()
                        assert all('private-denial-' not in row for row in private_rows)
                        for table in ('entry_matches','medication_list_snapshots','safety_assessments'):
                            assert core.execute(f'SELECT count(*) FROM msa.{table} WHERE user_id=%s',(identity,)).fetchone()[0]==0
                        with isolated_core_owner(core,identity=other_patient):
                            with TestClient(app,headers={'origin':'http://127.0.0.1:5173'},client=(peer,50000)) as other_client:
                                assert other_client.post('/api/auth/login',json={'email':emails[2],'password':'Pg-test-2026'}).status_code==200
                                assert other_client.get(f'/api/v1/intake/workflows/{workflow}').status_code==404
                                other_client.post('/api/auth/logout')
            client.post('/api/auth/logout')
            assert client.get('/api/auth/me').status_code == 401
    finally:
        event.remove(Session, 'after_flush', capture_audit)
        # API calls commit on multiple connections. Only administrative test
        # teardown suppresses history triggers LOCALLY for our generated IDs.
        deleted = {}
        with engine().begin() as db:
            db.execute(text("SET LOCAL session_replication_role='replica'"))
            deleted['captured_audit_events'] = db.execute(text('DELETE FROM audit_events WHERE event_id=ANY(:ids)'), {'ids':list(audit_ids)}).rowcount
            for table, field in [('auth_sessions', 'user_id'), ('audit_events', 'actor_user_id'), ('user_roles', 'user_id'), ('users', 'user_id')]:
                deleted[table] = db.execute(text(f'DELETE FROM {table} WHERE {field} IN (:admin,:patient,:other)'), params).rowcount
            for key in throttle_keys:
                deleted['login_throttles'] = deleted.get('login_throttles', 0) + db.execute(text('DELETE FROM login_throttles WHERE key_hash=:key'), {'key': key}).rowcount
        with engine().connect() as db:
            assert db.exec_driver_sql('SHOW session_replication_role').scalar_one() == 'origin'
            after = {t: db.execute(text(f'SELECT count(*) FROM {t}')).scalar_one() for t in tables}
            assert after == before, (before, after)
            assert db.execute(text('SELECT to_jsonb(t) FROM audit_events t ORDER BY event_id')).scalars().all() == before_audit
        print('\nAUTH TEST CLEANUP:', deleted, 'remaining=0; guards=origin')
        reset_connection()
