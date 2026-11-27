"""Load backend-local configuration without replacing process/test overrides."""
from pathlib import Path
import os
from urllib.parse import urlsplit
from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parents[3] / 'apps/backend'
load_dotenv(BACKEND_ROOT / ".env", override=False)


def core_database_dsn():
    """Use the Auth connection in unified mode; explicit test/Core overrides win."""
    if 'CORE_DB_DSN' in os.environ:
        return os.environ['CORE_DB_DSN']
    if os.environ.get('DATABASE_MODE', 'separate') != 'unified':
        return ''
    from sqlalchemy.engine import make_url
    from psycopg.conninfo import make_conninfo
    from shared.auth.db import database_url
    url = make_url(database_url())
    # SQLite test/preview overrides must never fall through to the real database.
    if url.get_backend_name() != 'postgresql':
        return ''
    options = url.translate_connect_args(username='user', database='dbname')
    options.update(dict(url.query))
    options.setdefault('connect_timeout', 5)
    return make_conninfo(**options)

def allowed_origins():
    return [value.strip() for value in os.environ.get("AUTH_ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173").split(",") if value.strip()]

def validate_security_config():
    if os.environ.get("AUTH_ENV", "development") != "production":
        return
    if os.environ.get("AUTH_SEED_DEMO", "0") != "0" or os.environ.get("AUTH_COOKIE_SECURE", "0") != "1":
        raise RuntimeError("Production requires AUTH_SEED_DEMO=0 and AUTH_COOKIE_SECURE=1")
    origins = allowed_origins()
    if not origins or any(urlsplit(o).scheme != "https" or not urlsplit(o).hostname
                          or urlsplit(o).hostname in {"localhost", "127.0.0.1", "::1"}
                          or urlsplit(o).path or urlsplit(o).query or urlsplit(o).fragment for o in origins):
        raise RuntimeError("Production requires explicit HTTPS origins without paths")
