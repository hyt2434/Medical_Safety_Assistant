from psycopg.conninfo import conninfo_to_dict
from shared.auth.settings import core_database_dsn


def test_unified_connection_preserves_credentials(monkeypatch):
    monkeypatch.setenv('DATABASE_MODE', 'unified')
    monkeypatch.delenv('CORE_DB_DSN', raising=False)
    monkeypatch.delenv('AUTH_DB_PATH', raising=False)
    monkeypatch.setenv('AUTH_DATABASE_URL', 'postgresql+psycopg://user:p%40ss%3A%2F%23@localhost:5432/system?sslmode=require')
    options = conninfo_to_dict(core_database_dsn())
    assert options['dbname'] == 'system'
    assert options['password'] == 'p@ss:/#'
    assert options['sslmode'] == 'require'


def test_sqlite_override_never_reaches_shared_core(monkeypatch):
    monkeypatch.setenv('DATABASE_MODE', 'unified')
    monkeypatch.delenv('CORE_DB_DSN', raising=False)
    monkeypatch.setenv('AUTH_DATABASE_URL', '')
    monkeypatch.setenv('AUTH_DB_PATH', 'artifacts/auth/isolated.sqlite')
    assert core_database_dsn() == ''


def test_explicit_core_override_including_disabled_wins(monkeypatch):
    monkeypatch.setenv('DATABASE_MODE', 'unified')
    for dsn in ('', 'host=localhost dbname=isolated'):
        monkeypatch.setenv('CORE_DB_DSN', dsn)
        assert core_database_dsn() == dsn


def test_separate_mode_does_not_infer_core(monkeypatch):
    monkeypatch.setenv('DATABASE_MODE', 'separate')
    monkeypatch.delenv('CORE_DB_DSN', raising=False)
    assert core_database_dsn() == ''
