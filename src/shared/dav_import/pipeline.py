import json
from shared.paths import ProjectPath as Path, PROJECT_ROOT
import shutil
import sqlite3
from . import VERSION
from .authorization import authorize
from .common import digest, dumps, file_hash, now
from .normalize import ALIASES, key, normalize
from .readers import records
from .readers import MAX_ROW_BYTES

HERE = Path(__file__).resolve().parent
SCHEMA = HERE.parent / 'schema.sql'


def connect(path):
    db = sqlite3.connect(path, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('PRAGMA synchronous=FULL')
    db.execute('PRAGMA cache_size=-16384')
    exists = db.execute("SELECT 1 FROM sqlite_master WHERE name='schema_version'").fetchone()
    if exists and [r[0] for r in db.execute('SELECT version FROM schema_version')] != [VERSION]:
        db.close()
        raise ValueError('Database schema version mismatch; use a new database or explicit migration')
    db.executescript(SCHEMA.read_text(encoding='utf-8'))
    return db


def configuration(column_map, sheet, delimiter):
    if not isinstance(column_map, dict) or any(k not in ALIASES or not isinstance(v, str) or not v for k, v in column_map.items()):
        raise ValueError('Column map must map known canonical fields to exact header strings')
    if len(delimiter) != 1:
        raise ValueError('CSV delimiter must be one character')
    return {'version': VERSION, 'column_map': column_map, 'sheet': sheet, 'delimiter': delimiter,
            'code_sha256': {p.name: file_hash(p) for p in sorted(HERE.glob('*.py'))},
            'schema_sha256': file_hash(SCHEMA)}


def archive(input_path, folder, sha):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / (sha + input_path.suffix.lower())
    if dest.exists():
        if file_hash(dest) != sha:
            raise ValueError('Archived artifact integrity failure')
        return dest
    temp = folder / (sha + '.partial')
    # One writer per archive/DB; a leftover partial is safely replaced on restart.
    with input_path.open('rb') as src, temp.open('wb') as out:
        shutil.copyfileobj(src, out, 1024 * 1024)
    if file_hash(temp) != sha:
        raise ValueError('Input changed during archival')
    temp.replace(dest)
    return dest


def add_issue(db, oid, code, severity, detail):
    db.execute('INSERT OR IGNORE INTO issues VALUES(?,?,?,?)', (oid, code, severity, detail))


def ingest_row(db, sid, row_number, raw, locator, config, synthetic):
    if len(dumps(raw).encode('utf-8')) > MAX_ROW_BYTES:
        raise ValueError('Record exceeds 2 MiB')
    flag = raw.get('synthetic_fixture')
    if synthetic and flag not in (True, 'true'):
        raise ValueError('Every synthetic row must declare synthetic_fixture=true')
    if not synthetic and flag not in (None, False, 'false', ''):
        raise ValueError('Synthetic row forbidden in real import')
    if any(header not in raw for header in config['column_map'].values()):
        raise ValueError('Configured export header missing')
    raw_hash = digest(raw)
    transform = digest(config)
    oid = digest({'raw': raw_hash, 'transform': transform, 'synthetic': synthetic})
    existing = db.execute('SELECT id FROM observations WHERE id=?', (oid,)).fetchone()
    if not existing:
        n, validation, problems, signature = normalize(raw, config['column_map'], synthetic)
        mid = rid = None
        if validation != 'QUARANTINED':
            mid = 'med-' + signature
            db.execute('INSERT OR IGNORE INTO medications VALUES(?,?,?,?,?,?,?,?,?)',
                       (mid, signature, n['brand_name'], n['manufacturer'], n['dosage_form'],
                        n['dosage_form_normalized'], n['route'] or None, synthetic, 'REVIEW_REQUIRED'))
            # Preserve observed component order in each normalized observation; candidate's order is first seen.
            for index, c in enumerate(n['components'], 1):
                iid = 'ing-' + digest({'name': key(c['name_raw']), 'synthetic': synthetic})
                db.execute('INSERT OR IGNORE INTO ingredients VALUES(?,?,?,?)', (iid, key(c['name_raw']), c['name_raw'], synthetic))
                db.execute('INSERT OR IGNORE INTO components VALUES(?,?,?,?,?,?,?,?)',
                           (mid, index, iid, c['name_raw'], c['strength_raw'], dumps(c['strength']), c['basis_raw'], 'REVIEW_REQUIRED'))
            rid = 'reg-' + digest({'number': n['registration_key'], 'synthetic': synthetic})
            db.execute('INSERT OR IGNORE INTO registrations VALUES(?,?,?,?)',
                       (rid, n['registration_number'], n['registration_key'], synthetic))
        db.execute('INSERT INTO observations VALUES(?,?,?,?,?,?,?,?,?)',
                   (oid, raw_hash, dumps(raw), dumps(n), transform, mid, rid, synthetic, validation))
        for code, severity, detail in problems:
            add_issue(db, oid, code, severity, detail)
        if mid:
            db.execute('INSERT INTO registration_events VALUES(?,?,?,?,?,?,?,?,?,?)',
                       ('evt-' + oid, rid, mid, oid, n['event_type_normalized'], n['decision_number'] or None,
                        n['effective_date_normalized'], n['valid_until_normalized'], n['claimed_status'] or None, 'UNKNOWN'))
            if n['previous_registration_number']:
                db.execute('INSERT INTO registration_links(observation_id,registration_id,previous_identifier_raw) VALUES(?,?,?)',
                           (oid, rid, n['previous_registration_number']))
            alternatives = db.execute('SELECT DISTINCT medication_id FROM registration_events WHERE registration_id=?', (rid,)).fetchall()
            if len(alternatives) > 1:
                db.execute("UPDATE medications SET verification_status='AMBIGUOUS' WHERE id IN (SELECT medication_id FROM registration_events WHERE registration_id=?)", (rid,))
                db.execute("UPDATE observations SET validation_status='REVIEW_REQUIRED' WHERE registration_id=? AND validation_status!='QUARANTINED'", (rid,))
                db.execute("INSERT OR IGNORE INTO issues SELECT id,'REGISTRATION_FORMULATION_CONFLICT','WARNING','Multiple candidate formulations; preserve versions and reconcile history' FROM observations WHERE registration_id=?", (rid,))
    db.execute('INSERT INTO raw_records VALUES(?,?,?,?,?,?)',
               (sid, row_number, dumps(locator), dumps(raw), raw_hash, oid))


def import_export(input_path, manifest_path, db_path, *, archive_dir=None, column_map=None,
                  sheet=None, delimiter=',', chunk_size=1000, stop_after=None, as_of='2026-10-12',
                  fail_at_row=None):
    """Commit checkpoint + rows together. fail_at_row is an injected rollback test hook."""
    if chunk_size <= 0 or (stop_after is not None and stop_after <= 0):
        raise ValueError('Chunk and stop limits must be positive')
    input_path, db_path = Path(input_path), Path(db_path)
    m = authorize(manifest_path, input_path, as_of)
    config = configuration(column_map or {}, sheet, delimiter)
    sid = 'src-' + digest({'manifest': m, 'artifact': m['artifact_sha256']})
    db_path.parent.mkdir(parents=True, exist_ok=True)
    archived = archive(input_path, archive_dir or db_path.parent / 'artifacts', m['artifact_sha256'])
    db = connect(db_path)
    try:
        previous = db.execute('SELECT config_json,artifact_path FROM sources WHERE id=?', (sid,)).fetchone()
        if previous and previous['config_json'] != dumps(config):
            raise ValueError('Import configuration/code changed; resume refused. Use a new DB for reprocessing')
        with db:
            db.execute('INSERT OR IGNORE INTO sources VALUES(?,?,?,?,?,?,?,?,?,?)',
                       (sid, m['source_kind'], m['source_url'], m['snapshot_at'], m['artifact_sha256'],
                        str(archived.resolve()), dumps(m), digest(m), dumps(config), now()))
            db.execute("INSERT OR IGNORE INTO batches VALUES(?,0,'RUNNING',NULL,?)", (sid, now()))
        batch = db.execute('SELECT * FROM batches WHERE id=?', (sid,)).fetchone()
        if batch['state'] == 'COMPLETE':
            return sid
        checkpoint = batch['last_row']
        with db:
            db.execute("UPDATE batches SET state='RUNNING',error=NULL,updated_at=? WHERE id=?", (now(), sid))
        count = checkpoint
        pending = 0
        processed = 0
        try:
            for number, (row, locator) in enumerate(records(archived, sheet, delimiter), 1):
                if number <= checkpoint:
                    continue
                if pending == 0:
                    db.execute('BEGIN IMMEDIATE')
                if number == fail_at_row:
                    raise RuntimeError('Injected crash before checkpoint')
                ingest_row(db, sid, number, row, locator, config, int(m['source_kind'] == 'synthetic'))
                count = number
                pending += 1
                processed += 1
                pause = stop_after is not None and processed >= stop_after
                if pending >= chunk_size or pause:
                    db.execute('UPDATE batches SET last_row=?,state=?,updated_at=? WHERE id=?',
                               (count, 'PAUSED' if pause else 'RUNNING', now(), sid))
                    db.commit()
                    pending = 0
                if pause:
                    return sid
            expected = m.get('expected_records')
            if expected is not None and (not isinstance(expected, int) or isinstance(expected, bool) or count != expected):
                raise ValueError('Committed/read row count differs from authorized expected_records')
            db.execute("UPDATE batches SET last_row=?,state='COMPLETE',error=NULL,updated_at=? WHERE id=?", (count, now(), sid))
            db.commit()
        except BaseException as e:
            db.rollback()
            with db:
                db.execute("UPDATE batches SET state='FAILED',error=?,updated_at=? WHERE id=?", (str(e), now(), sid))
            raise
        return sid
    finally:
        db.close()


def review(db_path, entity_type, entity_id, scope, status, reviewer, evidence, note, as_of_date=None):
    """Append human decisions separately; no import or mapping automatically verifies a product."""
    tables = {'medication': 'medications', 'registration': 'registrations', 'mapping': 'terminology_mappings'}
    if entity_type not in tables or not reviewer.strip() or not scope.strip() or not note.strip():
        raise ValueError('Entity type, reviewer, scope, and rationale are required')
    import re
    from datetime import date
    if as_of_date is not None:
        date.fromisoformat(as_of_date)
    if not evidence or not isinstance(evidence, list) or any(not isinstance(e, dict) or not e.get('locator') or not re.fullmatch(r'[0-9a-f]{64}', e.get('sha256', '')) for e in evidence):
        raise ValueError('Review evidence needs locators and artifact hashes')
    db = connect(db_path)
    try:
        if not db.execute('SELECT 1 FROM ' + tables[entity_type] + ' WHERE id=?', (entity_id,)).fetchone():
            raise ValueError('Review entity does not exist')
        if entity_type == 'mapping' and status == 'VERIFIED':
            mapping = db.execute('SELECT status,target_id FROM terminology_mappings WHERE id=?', (entity_id,)).fetchone()
            if mapping['status'] != 'CANDIDATE' or not mapping['target_id']:
                raise ValueError('Only an explicit candidate identifier can receive a verified mapping review')
        with db:
            db.execute('INSERT INTO reviews(entity_type,entity_id,scope,status,reviewer,reviewed_at,as_of_date,evidence_json,note) VALUES(?,?,?,?,?,?,?,?,?)',
                       (entity_type, entity_id, scope, status, reviewer, now(), as_of_date, dumps(evidence), note))
    finally:
        db.close()
