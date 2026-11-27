"""Add Core to the configured PostgreSQL Auth DB without dropping existing data.

python db/setup_system.py          # read-only preflight
python db/setup_system.py --apply  # backup, migrations, reference import, identity links
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
import psycopg
from psycopg.conninfo import make_conninfo, conninfo_to_dict
from sqlalchemy.engine import make_url
from dotenv import set_key
from shared.auth.db import database_url, migrate as migrate_auth
from shared.auth.settings import BACKEND_ROOT
from shared.db.importer import read_sources, import_datasets
from db.manage import provision_identity_registry, migrate


def system_dsn():
    url = make_url(database_url())
    if url.get_backend_name() != 'postgresql':
        raise ValueError('Unified setup requires PostgreSQL Auth configuration, not SQLite.')
    options = url.translate_connect_args(username='user', database='dbname')
    options.update(dict(url.query))
    options.setdefault('connect_timeout', 5)
    return make_conninfo(**options)


def backup_database(dsn, folder):
    executable = shutil.which('pg_dump')
    if not executable and os.name == 'nt':
        candidates = sorted(Path('C:/Program Files/PostgreSQL').glob('*/bin/pg_dump.exe'),
                            key=lambda p: int(p.parents[1].name), reverse=True)
        executable = str(candidates[0]) if candidates else None
    if not executable:
        raise RuntimeError('Install PostgreSQL client tools (pg_dump); backup is required before --apply.')
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.dump')
    # Connection secrets go through the child environment, never command arguments/logs.
    names = {'host': 'PGHOST', 'port': 'PGPORT', 'dbname': 'PGDATABASE', 'user': 'PGUSER',
             'password': 'PGPASSWORD', 'sslmode': 'PGSSLMODE', 'connect_timeout': 'PGCONNECT_TIMEOUT',
             'sslcert': 'PGSSLCERT', 'sslkey': 'PGSSLKEY', 'sslrootcert': 'PGSSLROOTCERT',
             'options': 'PGOPTIONS', 'service': 'PGSERVICE'}
    options = conninfo_to_dict(dsn)
    if set(options) - names.keys():
        raise ValueError('Unsupported backup connection options: ' + ', '.join(sorted(set(options) - names.keys())))
    env = {**os.environ, **{names[k]: str(v) for k, v in options.items()}}
    subprocess.run([executable, '--format=custom', '--no-password', '--file', str(target)], env=env, check=True)
    restore = str(Path(executable).with_name('pg_restore.exe' if os.name == 'nt' else 'pg_restore'))
    subprocess.run([restore, '--list', str(target)], check=True, stdout=subprocess.DEVNULL)
    return target


def install_core(db, csv_dir):
    """Caller has migrated Auth and deliberately selected a single DB deployment."""
    if db.execute("SELECT to_regclass('public.auth_alembic_version')").fetchone()[0] is None:
        raise RuntimeError('Migrate Auth before installing the unified system.')
    registry = provision_identity_registry(db, unified=True)
    schema = migrate(db)
    reference = import_datasets(db, csv_dir)
    with db.transaction():
        db.execute((ROOT / 'db/unified_identity.sql').read_text(encoding='utf-8'))
        missing = db.execute('SELECT count(*) FROM public.users u LEFT JOIN identity.users i ON i.id=u.user_id WHERE i.id IS NULL').fetchone()[0]
        if missing:
            raise RuntimeError('Auth/Core UUID reconciliation failed')
    return {'registry': registry, 'migrations': schema['applied_migrations'],
            'dataset_build': reference['dataset_build'], 'reused_build': reference['reused_build'],
            'source_records': reference['total_source_records'],
            'linked_accounts': db.execute('SELECT count(*) FROM public.users').fetchone()[0]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--csv-dir', type=Path, default=ROOT / 'data/datasets')
    args = parser.parse_args()
    dsn = system_dsn()
    with psycopg.connect(dsn, autocommit=True) as db:
        # A separate configured Core may contain patient history. Never silently abandon it.
        if os.environ.get('CORE_DB_DSN'):
            with psycopg.connect(os.environ['CORE_DB_DSN'], autocommit=True) as core:
                def target(conn):
                    return conn.execute('SELECT current_database(),inet_server_addr(),inet_server_port()').fetchone()
                if target(core) != target(db):
                    raise RuntimeError('Existing separate Core configured. Migrate its data explicitly before unified setup.')
        plan = {'database': db.info.dbname, 'host': db.info.host, 'port': db.info.port,
                'schemas': ['public (Auth and legacy OCR)', 'identity', 'msa', 'msa_ref']}
        print(json.dumps(plan), flush=True)
        read_sources(args.csv_dir)  # fail before writing if any approved source is missing/malformed
        if not args.apply:
            print('Preflight passed. Use --apply to back up and install the unified system.')
            return
        backup = backup_database(dsn, ROOT / 'artifacts/system-db/backups')
        print('Verified backup: ' + str(backup), flush=True)
        migrate_auth()
        result = install_core(db, args.csv_dir)
    # Persist only after successful reconciliation. Existing DB_* credentials remain unchanged.
    env_path = BACKEND_ROOT / '.env'
    set_key(str(env_path), 'DATABASE_MODE', 'unified')
    set_key(str(env_path), 'CORE_REFERENCE_BUILD', result['dataset_build'])
    result['backup'] = str(backup)
    report = ROOT / 'artifacts/system-db/setup.json'
    report.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))
    print('Restart backend. Auth and Intake now use the same PostgreSQL database.')


if __name__ == '__main__':
    main()
