from auth.db import database_url
from sqlalchemy.engine import make_url
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
