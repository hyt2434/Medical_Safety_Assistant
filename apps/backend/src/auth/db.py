"""SQLAlchemy unit of work and migrations. Never changes Core V4."""
import os
import threading
from contextlib import contextmanager
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session
import settings  # Load .env for API and migration entry points.

ROOT = Path(__file__).resolve().parents[4]
ROLE_CODES = ("patient", "hcp", "medical_reviewer", "technical_support", "admin")
_engine = None
_lock = threading.RLock()
_ready = False

def database_path():
    return Path(os.environ.get("AUTH_DB_PATH", ROOT / "artifacts/auth/dev.sqlite"))

def database_url():
    # Explicit legacy/test overrides must never connect tests to the shared DB.
    if "AUTH_DATABASE_URL" in os.environ or "AUTH_DB_PATH" in os.environ:
        return os.environ.get("AUTH_DATABASE_URL") or "sqlite:///" + database_path().as_posix()
    if os.environ.get("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    if os.environ.get("DB_HOST"):
        try:
            port = int(os.environ.get("DB_PORT", "5432"))
            if not 1 <= port <= 65535:
                raise ValueError
        except ValueError:
            raise ValueError("DB_PORT must be an integer between 1 and 65535") from None
        for key in ("DB_NAME", "DB_USER"):
            if not os.environ.get(key):
                raise ValueError(f"{key} is required when DB_HOST is configured")
        return URL.create("postgresql+psycopg", username=os.environ["DB_USER"],
            password=os.environ.get("DB_PASSWORD", ""), host=os.environ["DB_HOST"],
            port=port, database=os.environ["DB_NAME"]).render_as_string(hide_password=False)
    return "sqlite:///" + database_path().as_posix()

def engine():
    global _engine
    with _lock:
        if _engine is None:
            url = database_url()
            if url.startswith("sqlite"):
                database_path().parent.mkdir(parents=True, exist_ok=True)
            _engine = create_engine(url, pool_pre_ping=True,
                connect_args={"check_same_thread": False, "timeout": 30} if url.startswith("sqlite") else {})
            if _engine.dialect.name == "sqlite":
                @event.listens_for(_engine, "connect")
                def foreign_keys(connection, _):
                    connection.execute("PRAGMA foreign_keys=ON")
        return _engine

def migrate():
    from alembic import command
    from alembic.config import Config
    config = Config()
    config.set_main_option("script_location", str(ROOT / "db/auth/migrations"))
    with engine().begin() as connection:
        if connection.dialect.name == "postgresql":
            connection.exec_driver_sql("SELECT pg_advisory_xact_lock(74031821)")
        config.attributes["connection"] = connection
        command.upgrade(config, "head")

def initialize():
    global _ready
    with _lock:
        if _ready:
            return
        settings.validate_security_config()
        migrate()
        from auth.seed import seed_catalog, seed_accounts
        with transaction() as db:
            seed_catalog(db)
            if os.environ.get("AUTH_ENV", "development") == "production":
                from sqlalchemy import select
                from auth.models import User
                from auth.seed_accounts import _ACCOUNTS
                if db.scalar(select(User.user_id).where(User.email.in_([row[1] for row in _ACCOUNTS]))):
                    raise RuntimeError("Remove development accounts before production startup")
            if os.environ.get("AUTH_SEED_DEMO", "0") == "1":
                seed_accounts(db)
        _ready = True

@contextmanager
def transaction():
    with Session(engine(), expire_on_commit=False) as db:
        try:
            if engine().dialect.name == "sqlite":
                db.connection().exec_driver_sql("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise

def reset_connection():
    global _engine, _ready
    with _lock:
        if _engine is not None:
            _engine.dispose()
        _engine, _ready = None, False

