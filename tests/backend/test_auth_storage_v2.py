"""UUID migration and role-history regressions; temporary SQLite or marked PG."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json
import os
from pathlib import Path
from uuid import uuid4, UUID

import pytest
from sqlalchemy import select, text, create_engine
from sqlalchemy.exc import IntegrityError, DBAPIError
from alembic import command
from alembic.config import Config

from shared.auth.db import transaction, reset_connection
from shared.auth.models import User, UserRole, Role, AuditEvent
from shared.auth.sessions import now
from shared.auth.types import identity_uuid
from tests.backend.test_rbac import client, admin, grant

ROOT = Path(__file__).resolve().parents[2]


def test_regrant_has_new_id_and_preserves_revocation(client):
    admin(client)
    assert grant(client).status_code == 200
    assert client.delete('/api/admin/users/u-support/roles/hcp').status_code == 200
    assert grant(client).status_code == 200
    with transaction() as db:
        role = db.scalar(select(Role).where(Role.role_code == 'hcp'))
        rows = db.scalars(select(UserRole).where(UserRole.user_id == 'u-support', UserRole.role_id == role.role_id)
                          .order_by(UserRole.granted_at)).all()
        assert len(rows) == 2 and len({r.grant_id for r in rows}) == 2
        assert rows[0].revoked_at is not None and rows[1].revoked_at is None
        assert rows[0].revoked_at <= rows[1].granted_at


def test_raw_sql_cannot_overlap_or_rewrite_grant_and_audit(client):
    with transaction() as db:
        role = db.scalar(select(Role).where(Role.role_code == 'patient'))
        current = db.scalar(select(UserRole).where(UserRole.user_id == 'u-patient', UserRole.role_id == role.role_id))
        assert UUID(current.user_id)
        assert current.granted_at.tzinfo is not None
        with pytest.raises(IntegrityError):
            with db.begin_nested():
                db.add(UserRole(user_id=current.user_id, role_id=role.role_id, granted_at=now()))
                db.flush()
        with pytest.raises(IntegrityError):
            with db.begin_nested():
                current.granted_at = now() - timedelta(days=1)
                db.flush()
    admin(client)
    with transaction() as db:
        event = db.scalar(select(AuditEvent))
        assert isinstance(event.success, bool) and event.occurred_at.tzinfo is not None
        with pytest.raises(IntegrityError):
            with db.begin_nested():
                event.success = not event.success
                db.flush()


def test_raw_sql_cannot_lock_last_permanent_administrator(client):
    with pytest.raises(IntegrityError):
        with transaction() as db:
            db.get(User, 'u-admin').account_status = 'locked'


def test_legacy_lookup_does_not_guess_a_different_accounts_uuid(client):
    alias='synthetic-legacy-'+uuid4().hex
    actual_id=str(uuid4())
    guessed_id=identity_uuid(alias)
    with transaction() as db:
        for identity,legacy in [(actual_id,alias),(guessed_id,None)]:
            db.add(User(user_id=identity,legacy_user_id=legacy,email=identity+'@example.com',
                        password_hash='not-a-login-hash',full_name='Synthetic legacy lookup',account_status='active'))
    admin(client)
    assert grant(client,user=alias,role='hcp').status_code==200
    with transaction() as db:
        role=db.scalar(select(Role).where(Role.role_code=='hcp'))
        assert len(db.scalars(select(UserRole).where(UserRole.user_id==actual_id,UserRole.role_id==role.role_id)).all())==1
        assert not db.scalars(select(UserRole).where(UserRole.user_id==guessed_id,UserRole.role_id==role.role_id)).all()


@pytest.fixture
def pg_auth_transaction():
    url = os.environ.get('SYSTEM_AUTH_TEST_URL')
    if not url:
        pytest.skip('SYSTEM_AUTH_TEST_URL identifies a dedicated marked Auth test database')
    from sqlalchemy.engine import make_url
    parts = make_url(url)
    assert parts.host in ('127.0.0.1', 'localhost') and parts.database.startswith('msa_auth_test_system')
    engine = create_engine(url)
    with engine.connect() as connection:
        tx = connection.begin()
        try:
            marker = connection.exec_driver_sql("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()").scalar_one()
            assert marker == 'Medication Safety Assistant Auth isolated test'
            assert not connection.exec_driver_sql("SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='users'").first(), 'Upgrade fixture requires a schema-empty dedicated test DB'
            config = Config()
            config.set_main_option('script_location', str(ROOT / 'db/auth/migrations'))
            config.attributes['connection'] = connection
            yield connection, config
        finally:
            tx.rollback()
    with engine.connect() as check:
        assert check.exec_driver_sql("SELECT to_regclass('public.users')").scalar_one() is None
    engine.dispose()


@pytest.mark.parametrize('fresh,explicit_binding', [(True,False),(False,False),(False,True)])
def test_postgres_native_schema_and_legacy_upgrade(pg_auth_transaction, fresh, explicit_binding, monkeypatch):
    c, config = pg_auth_transaction
    old = 'synthetic-legacy-' + uuid4().hex
    target = str(uuid4()) if explicit_binding else identity_uuid(old)
    if explicit_binding:
        monkeypatch.setenv('AUTH_LEGACY_UUID_MAP',json.dumps({old:target}))
    token = 'a' * 64
    if not fresh:
        command.upgrade(config, 'auth_003')
        c.execute(text("INSERT INTO users VALUES(:id,:email,'original-password-hash','Original name','active')"), {'id': old, 'email': old + '@example.invalid'})
        c.exec_driver_sql("INSERT INTO roles VALUES(1,'patient','Patient')")
        c.execute(text("INSERT INTO user_roles VALUES(:id,1,'2020-01-01T07:00:00+07:00',NULL,'2021-01-01T00:00:00+00:00')"), {'id': old})
        c.execute(text("INSERT INTO auth_sessions VALUES(:token,:id,'2030-01-01T00:00:00+00:00',NULL)"), {'token': token, 'id': old})
        c.execute(text("INSERT INTO audit_events VALUES(1,:id,'test','account',:id,1,'2020-01-01T07:00:00+07:00')"), {'id': old})
        c.exec_driver_sql("SELECT setval(pg_get_serial_sequence('audit_events','event_id'),1)")
    command.upgrade(config, 'head')
    from sqlalchemy import inspect
    actual = inspect(c)
    assert str(actual.get_columns('users')[0]['type']) == 'UUID'
    for table, column in [('user_roles', 'granted_at'), ('auth_sessions', 'expires_at'), ('audit_events', 'occurred_at'), ('login_throttles', 'expires_at')]:
        col = next(col for col in actual.get_columns(table) if col['name'] == column)
        assert col['type'].timezone is True
    assert str(next(col for col in actual.get_columns('audit_events') if col['name'] == 'success')['type']) == 'BOOLEAN'
    assert actual.get_pk_constraint('user_roles')['constrained_columns'] == ['grant_id']
    if not fresh:
        row = c.execute(text('SELECT user_id,legacy_user_id,password_hash FROM users')).one()
        assert str(row[0]) == target and row[1] == old and row[2] == 'original-password-hash'
        assert str(c.exec_driver_sql('SELECT user_id FROM auth_sessions').scalar_one()) == row[0].__str__()
        event = c.exec_driver_sql("SELECT actor_user_id,success,occurred_at FROM audit_events WHERE action_code='test'").one()
        assert str(event[0]) == str(row[0]) and event[1] is True and event[2].hour == 0
        assert c.exec_driver_sql('SELECT count(*) FROM user_roles WHERE revoked_at IS NOT NULL').scalar_one() == 1
    command.upgrade(config, 'head')


def test_postgres_legacy_mapping_cannot_merge_accounts(pg_auth_transaction,monkeypatch):
    c,config=pg_auth_transaction
    command.upgrade(config,'auth_003')
    old_ids=['synthetic-'+uuid4().hex,'synthetic-'+uuid4().hex]
    for identity in old_ids:
        c.execute(text("INSERT INTO users VALUES(:id,:email,'keep-hash','Synthetic','active')"),{'id':identity,'email':identity+'@example.com'})
    target=str(uuid4())
    monkeypatch.setenv('AUTH_LEGACY_UUID_MAP',json.dumps({value:target for value in old_ids}))
    with pytest.raises(ValueError,match='merge separate accounts'):
        with c.begin_nested():
            command.upgrade(config,'head')
    assert {r[0] for r in c.exec_driver_sql('SELECT user_id FROM users')}==set(old_ids)
    assert c.exec_driver_sql('SELECT version_num FROM auth_alembic_version').scalar_one()=='auth_003'


@pytest.mark.parametrize('field,value', [('occurred_at', 'not-a-time'), ('success', '7')])
def test_postgres_bad_legacy_values_fail_without_partial_upgrade(pg_auth_transaction, field, value):
    c, config = pg_auth_transaction
    if field=='success':
        # An adopted historic table may predate the original integer CHECK.
        c.exec_driver_sql('''CREATE TABLE audit_events(event_id integer PRIMARY KEY,actor_user_id varchar(80),
            action_code varchar(80) NOT NULL,target_type varchar(80) NOT NULL,target_id varchar(200) NOT NULL,
            success integer NOT NULL,occurred_at varchar(40) NOT NULL)''')
    command.upgrade(config, 'auth_003')
    if field == 'success':
        c.exec_driver_sql("INSERT INTO audit_events VALUES(1,NULL,'test','test','synthetic',7,'2020-01-01T00:00:00Z')")
        expected='Invalid historic audit success'
    else:
        c.execute(text("INSERT INTO audit_events VALUES(1,NULL,'test','test','synthetic',1,:value)"), {'value': value})
        expected='audit_events row 1 occurred_at'
    with pytest.raises(ValueError, match=expected):
        with c.begin_nested():
            command.upgrade(config, 'head')
    assert c.exec_driver_sql('SELECT version_num FROM auth_alembic_version').scalar_one() == 'auth_003'
    if field=='success':
        assert c.exec_driver_sql('SELECT success FROM audit_events').scalar_one()==7
    else:
        assert c.exec_driver_sql('SELECT occurred_at FROM audit_events').scalar_one()==value
    assert c.exec_driver_sql("SELECT data_type FROM information_schema.columns WHERE table_schema='public' AND table_name='users' AND column_name='user_id'").scalar_one() == 'character varying'


def test_core_registry_installer_refuses_auth_database(pg_auth_transaction):
    c,config=pg_auth_transaction
    command.upgrade(config,'head')
    from db.manage import provision_identity_registry
    with pytest.raises(RuntimeError,match='separate Auth database'):
        provision_identity_registry(c.connection.driver_connection)
    assert c.exec_driver_sql("SELECT to_regnamespace('identity')").scalar_one() is None


def test_account_provision_retry_after_core_failure_and_same_uuid(client, monkeypatch):
    from contextlib import contextmanager
    import psycopg
    from shared.auth.core_owner import ensure_account, provision_core_identity
    from shared.auth.passwords import verify_password
    dsn = os.environ.get('SYSTEM_TEST_DSN')
    if not dsn:
        pytest.skip('SYSTEM_TEST_DSN required for real two-store provisioning')
    monkeypatch.setenv('CORE_USER_BINDINGS', '{}')
    identity = str(uuid4())
    fields = {'email': identity + '@example.com', 'password': 'Original-password-2026', 'full_name': 'Synthetic account'}
    class CoreUnavailable:
        @contextmanager
        def transaction(self):
            raise OSError('Synthetic Core unavailable')
            yield
    with pytest.raises(OSError, match='Core unavailable'):
        ensure_account(identity, **fields, core_connection=CoreUnavailable())
    with transaction() as db:
        assert db.get(User, identity).email == fields['email']
        assert len(db.scalars(select(UserRole).where(UserRole.user_id == identity)).all()) == 1
    with psycopg.connect(dsn, autocommit=True) as core:
        assert core.info.dbname.startswith('msa_core_test_v4system')
        assert core.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()").fetchone()[0] == 'Medication Safety Assistant Core V4 isolated test'
        assert not core.execute('SELECT 1 FROM identity.users WHERE id=%s', (UUID(identity),)).fetchone()
        try:
            assert ensure_account(identity, **fields, core_connection=core) == identity
            assert ensure_account(identity, **{**fields, 'password': 'Must-not-reset-password'}, core_connection=core) == identity
            assert core.execute('SELECT count(*) FROM identity.users WHERE id=%s', (UUID(identity),)).fetchone()[0] == 1
            with pytest.raises(PermissionError):
                provision_core_identity(str(uuid4()), core)
            with transaction() as db:
                assert verify_password(fields['password'], db.get(User, identity).password_hash)
                assert len(db.scalars(select(UserRole).where(UserRole.user_id == identity)).all()) == 1
        finally:
            assert core.execute('DELETE FROM identity.users WHERE id=%s', (UUID(identity),)).rowcount == 1
            assert not core.execute('SELECT 1 FROM identity.users WHERE id=%s', (UUID(identity),)).fetchone()
            print('\nCORE PROVISIONING CLEANUP: identity.users=1, remaining=0')
