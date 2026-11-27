"""Exact-owner teardown for marked Core test DBs with independently committed APIs.

Public Core transactions intentionally cannot be wrapped in an outer rollback.
Its append-only history has no DELETE API. Only this administrative teardown uses
transaction-local replication_role on a verified test DB and UUIDs created here.
No schema changes, global truncation, reference writes or old-owner deletion.
"""
from contextlib import contextmanager
import re
from uuid import UUID, uuid4
from psycopg import sql


@contextmanager
def isolated_core_owner(db, *, identity=None):
    assert db.autocommit and db.info.host in ('127.0.0.1', 'localhost', '::1')
    assert re.fullmatch(r'msa_core_test_v4[a-z0-9]*checks', db.info.dbname)
    assert db.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()").fetchone()[0] == 'Medication Safety Assistant Core V4 isolated test'
    # Verify cleanup capability BEFORE creating any data that needs it.
    with db.transaction():
        db.execute("SET LOCAL session_replication_role='replica'")
    owner = UUID(str(identity)) if identity is not None else uuid4()
    assert db.execute('SELECT 1 FROM identity.users WHERE id=%s', (owner,)).fetchone() is None
    db.execute('INSERT INTO identity.users(id) VALUES (%s)', (owner,))
    try:
        yield owner
    finally:
        columns = db.execute("""SELECT table_name,column_name FROM information_schema.columns
            WHERE table_schema='msa' AND column_name IN ('user_id','requester_user_id','actor_user_id','subject_user_id','reviewer_user_id','author_user_id')""").fetchall()
        by_table = {}
        for table, column in columns:
            by_table.setdefault(table, []).append(column)
        deleted = {}
        with db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            for table, fields in by_table.items():
                where = sql.SQL(' OR ').join(sql.SQL('{}=%s').format(sql.Identifier(f)) for f in fields)
                query = sql.SQL('DELETE FROM msa.{} WHERE ').format(sql.Identifier(table)) + where
                count = db.execute(query, (owner,) * len(fields)).rowcount
                if count:
                    deleted['msa.' + table] = count
            deleted['identity.users'] = db.execute('DELETE FROM identity.users WHERE id=%s', (owner,)).rowcount
        assert db.execute('SHOW session_replication_role').fetchone()[0] == 'origin'
        assert db.execute('SELECT 1 FROM identity.users WHERE id=%s', (owner,)).fetchone() is None
        for table, fields in by_table.items():
            where = sql.SQL(' OR ').join(sql.SQL('{}=%s').format(sql.Identifier(f)) for f in fields)
            assert not db.execute(sql.SQL('SELECT 1 FROM msa.{} WHERE ').format(sql.Identifier(table)) + where,
                                  (owner,) * len(fields)).fetchone()
        print(f'\nCLEANED synthetic owner {owner}: {deleted}; remaining=0; guards=origin')
