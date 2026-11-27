from shared.auth.db import database_url
from sqlalchemy.engine import make_url
from sqlalchemy import inspect, CheckConstraint, text
import pytest


def test_split_postgres_settings_preserve_password(monkeypatch):
    for key in ("AUTH_DATABASE_URL", "AUTH_DB_PATH", "DATABASE_URL"):
        monkeypatch.delenv(key, raising=False)
    for key, value in {"DB_HOST": "127.0.0.1", "DB_PORT": "5432",
                       "DB_NAME": "application", "DB_USER": "example",
                       "DB_PASSWORD": "p@ss:/?#%word"}.items():
        monkeypatch.setenv(key, value)
    url = make_url(database_url())
    assert url.password == "p@ss:/?#%word"
    assert url.database == "application" and url.port == 5432
    monkeypatch.setenv("DB_PORT", "invalid")
    with pytest.raises(ValueError, match="DB_PORT"):
        database_url()


def test_shared_database_url(monkeypatch):
    monkeypatch.delenv("AUTH_DATABASE_URL", raising=False)
    monkeypatch.delenv("AUTH_DB_PATH", raising=False)
    url = "postgresql+psycopg://example:unused@127.0.0.1/application"
    monkeypatch.setenv("DATABASE_URL", url)
    assert database_url() == url


def test_isolated_database_overrides_shared_connection(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://unused/shared")
    monkeypatch.delenv("AUTH_DATABASE_URL", raising=False)
    path = tmp_path / "isolated.sqlite"
    monkeypatch.setenv("AUTH_DB_PATH", str(path))
    assert database_url() == "sqlite:///" + path.as_posix()
    monkeypatch.setenv("AUTH_DATABASE_URL", "postgresql+psycopg://unused/test")
    assert database_url() == "postgresql+psycopg://unused/test"


def assert_migrated_auth_matches_models(db_engine):
    """Check live DDL semantics, rather than comparing two lists of table names."""
    from shared.auth.models import Base
    inspector = inspect(db_engine)
    for table in Base.metadata.sorted_tables:
        actual = {c['name']: c for c in inspector.get_columns(table.name)}
        assert set(actual) == set(table.columns.keys()), table.name
        for column in table.columns:
            assert actual[column.name]['nullable'] == column.nullable, (table.name, column.name)
            assert str(actual[column.name]['type'].compile(dialect=db_engine.dialect)).upper() == str(column.type.compile(dialect=db_engine.dialect)).upper(), (table.name, column.name)
        assert set(inspector.get_pk_constraint(table.name)['constrained_columns']) == {c.name for c in table.primary_key}
        expected_fk = {(tuple(c.parent.name for c in f.elements), f.referred_table.name,
            tuple(c.column.name for c in f.elements), f.ondelete) for f in table.foreign_key_constraints}
        actual_fk = {(tuple(f['constrained_columns']), f['referred_table'], tuple(f['referred_columns']),
            f['options'].get('ondelete')) for f in inspector.get_foreign_keys(table.name)}
        assert actual_fk == expected_fk, table.name
        expected_unique = {tuple(c.name for c in constraint.columns) for constraint in table.constraints
                           if constraint.__class__.__name__ == 'UniqueConstraint'}
        assert {tuple(c['column_names']) for c in inspector.get_unique_constraints(table.name)} == expected_unique
        checks = [c['sqltext'].replace(' ', '').replace('::text', '').replace('(', '').replace(')', '')
                  for c in inspector.get_check_constraints(table.name)]
        for constraint in table.constraints:
            if isinstance(constraint, CheckConstraint):
                if table.name == 'users':
                    assert any("'active'" in check and "'locked'" in check for check in checks)
                elif table.name == 'audit_events':
                    if db_engine.dialect.name == 'sqlite':
                        assert any('success' in check and '0' in check and '1' in check for check in checks)
                else:
                    expected = str(constraint.sqltext).replace(' ', '').replace('(', '').replace(')', '').lower()
                    assert expected in [check.lower() for check in checks], (table.name, expected, checks)
        if table.name in {'auth_sessions', 'audit_events', 'login_throttles', 'user_roles'}:
            expected_indexes = {tuple(c.name for c in index.columns) for index in table.indexes}
            assert expected_indexes <= {tuple(i['column_names']) for i in inspector.get_indexes(table.name)}
    query = ("SELECT name FROM sqlite_master WHERE type='index'" if db_engine.dialect.name == 'sqlite'
             else "SELECT indexname FROM pg_indexes WHERE schemaname='public'")
    with db_engine.connect() as connection:
        indexes = {row[0] for row in connection.execute(text(query))}
    assert 'uq_users_email_normalized' in indexes
    if db_engine.dialect.name == 'postgresql':
        import json
        from pathlib import Path
        contract = json.loads((Path(__file__).resolve().parents[2]/'db/schema_contract.json').read_text(encoding='utf-8'))
        with db_engine.connect() as connection:
            for table in contract['auth']['tables']:
                params = {'table':'public.'+table['name'], 'name':table['name']}
                constraints = connection.execute(text('SELECT conname,contype,pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid=CAST(:table AS regclass)'),params).all()
                assert set(constraints) == {(r['name'],r['kind'],r['definition']) for r in table['constraints']}, table['name']
                actual_indexes = connection.execute(text("SELECT indexname,indexdef FROM pg_indexes WHERE schemaname='public' AND tablename=:name"),params).all()
                assert set(actual_indexes) == {(r['name'],r['definition']) for r in table['indexes']}, table['name']
                triggers = connection.execute(text('SELECT tgname,pg_get_triggerdef(oid) FROM pg_trigger WHERE tgrelid=CAST(:table AS regclass) AND NOT tgisinternal'),params).all()
                assert set(triggers) == {(r['name'],r['definition']) for r in table['triggers']}, table['name']


def test_auth_migration_model_columns_keys_nullability_and_constraints(tmp_path, monkeypatch):
    from shared.auth.db import reset_connection, initialize, engine
    monkeypatch.setenv('AUTH_DATABASE_URL', '')
    monkeypatch.setenv('AUTH_DB_PATH', str(tmp_path / 'contract.sqlite'))
    monkeypatch.setenv('AUTH_SEED_DEMO', '0')
    reset_connection()
    try:
        initialize()
        assert_migrated_auth_matches_models(engine())
    finally:
        reset_connection()
