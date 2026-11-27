"""An indexed projection over the existing immutable DAV ingestion tables."""
from copy import deepcopy
from contextlib import closing
from datetime import datetime, timezone
import difflib
import json
import re
from shared.paths import ProjectPath as Path, PROJECT_ROOT
import sqlite3
from shared.dav_import.common import digest, dumps
from shared.dav_import.pipeline import import_export, connect
from shared.dav_import.normalize import canonicalize
from .text import key, brand_key, registration, form_key, strength_key
from .ingredients import parse_ingredients

SCHEMA = '''
CREATE TABLE IF NOT EXISTS m2_version(version TEXT PRIMARY KEY);
INSERT OR IGNORE INTO m2_version VALUES ('direct-reference-v1');
CREATE TABLE IF NOT EXISTS m2_candidates (
 observation_id TEXT PRIMARY KEY REFERENCES observations(id), candidate_key TEXT NOT NULL,
 brand_key TEXT NOT NULL, registration_key TEXT, ingredient_raw TEXT NOT NULL,
 strength_key TEXT NOT NULL, dosage_form_key TEXT NOT NULL, manufacturer_key TEXT NOT NULL,
 synthetic INTEGER NOT NULL, projection_json TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS m2_brand ON m2_candidates(brand_key,synthetic);
CREATE INDEX IF NOT EXISTS m2_registration ON m2_candidates(registration_key,synthetic);
CREATE INDEX IF NOT EXISTS m2_candidate ON m2_candidates(candidate_key);
CREATE TABLE IF NOT EXISTS m2_reviews (
 id INTEGER PRIMARY KEY, candidate_key TEXT NOT NULL, status TEXT NOT NULL,
 reviewer TEXT NOT NULL, reviewed_at TEXT NOT NULL, evidence_json TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS m2_review_candidate ON m2_reviews(candidate_key,id);
CREATE TABLE IF NOT EXISTS m2_aliases (
 alias_key TEXT NOT NULL, candidate_key TEXT NOT NULL, evidence_json TEXT NOT NULL,
 PRIMARY KEY(alias_key,candidate_key));
'''


def projection(raw):
    return {field: deepcopy(raw.get(field)) for field in (
        'brand_name', 'registration_number', 'ingredients', 'strength', 'dosage_form',
        'manufacturer', 'packaging', 'route', 'valid_until', 'effective_date', 'decision_number',
        'event_type', 'verification_status', '_source', '_dav_capture')}


def candidate_key(raw):
    return digest({field: raw.get(field) for field in (
        'brand_name', 'registration_number', 'ingredients', 'strength', 'dosage_form',
        'manufacturer', 'packaging', 'route')})


def build_reference(input_path, manifest_path, db_path, *, as_of, **import_options):
    """The existing importer checks written permissions before storing any DAV rows."""
    # Avoid opening or altering an incompatible database before the existing importer checks it.
    source_id = import_export(input_path, manifest_path, db_path, as_of=as_of, **import_options)
    db = connect(db_path)
    try:
        db.executescript(SCHEMA)
        with db:
            for observation in db.execute('SELECT o.id,o.raw_json,o.synthetic FROM observations o '
                    'LEFT JOIN m2_candidates c ON c.observation_id=o.id WHERE c.observation_id IS NULL'):
                raw = json.loads(observation['raw_json'])
                canonical, _ = canonicalize(raw, import_options.get('column_map') or {})
                canonical.update({k: raw.get(k) for k in ('verification_status', '_source', '_dav_capture')})
                db.execute('INSERT INTO m2_candidates VALUES(?,?,?,?,?,?,?,?,?,?)', (
                    observation['id'], candidate_key(canonical), brand_key(canonical.get('brand_name')),
                    registration(canonical.get('registration_number')), dumps(canonical.get('ingredients')),
                    dumps(strength_key(canonical.get('strength'))), form_key(canonical.get('dosage_form')),
                    key(canonical.get('manufacturer')), observation['synthetic'], dumps(projection(canonical))))
        return {'source_id': source_id, 'observations': db.execute('SELECT count(*) FROM m2_candidates').fetchone()[0],
                'database': str(Path(db_path).resolve()), 'current_authorization': 'UNKNOWN'}
    finally:
        db.close()


class MedicationReference:
    def __init__(self, path, *, allow_synthetic=False):
        self.path = Path(path)
        self.db = sqlite3.connect(self.path.resolve().as_uri() + '?mode=ro', uri=True)
        self.db.row_factory = sqlite3.Row
        self.allow_synthetic = allow_synthetic
        try:
            version = self.db.execute('SELECT version FROM m2_version').fetchall()
            if [r[0] for r in version] != ['direct-reference-v1']:
                raise ValueError('Unsupported Module 2 reference version')
        except Exception:
            self.db.close()
            raise

    def close(self):
        self.db.close()

    def evidence(self, candidate):
        return [dict(row) for row in self.db.execute(
            'SELECT rr.source_id,rr.row_number,rr.raw_sha256,rr.locator_json,s.source_url,'
            's.snapshot_at,s.artifact_sha256,s.manifest_sha256 FROM raw_records rr '
            'JOIN sources s ON s.id=rr.source_id JOIN m2_candidates c ON c.observation_id=rr.observation_id '
            'WHERE c.candidate_key=? ORDER BY rr.source_id,rr.row_number', (candidate,))]

    def lookup(self, medication):
        if not isinstance(medication, dict):
            raise ValueError('Medication input must be an object')
        brand = medication.get('brand_name') or medication.get('name_raw')
        reg_raw = medication.get('registration_number')
        reg = registration(reg_raw) if reg_raw else None
        result = {'identification_status': 'UNRESOLVED', 'lookup_method': None,
                  'candidates': [], 'suggestions': [], 'issues': [], 'current_authorization': 'UNKNOWN'}
        if reg_raw and reg is None:
            result['issues'].append('REGISTRATION_UNREADABLE')
            return result
        if not brand and not reg:
            result['issues'].append('BRAND_OR_REGISTRATION_REQUIRED')
            return result
        synthetic = int(medication.get('synthetic_fixture') is True)
        if synthetic and not self.allow_synthetic:
            result['issues'].append('SYNTHETIC_REFERENCE_DISABLED')
            return result
        # Real inputs cannot see synthetic rows even in fixture-enabled sessions.
        if reg:
            rows = self.db.execute('SELECT c.*,o.validation_status AS ingestion_status FROM m2_candidates c '
                                   'JOIN observations o ON o.id=c.observation_id WHERE c.registration_key=? AND c.synthetic=?',
                                   (reg, synthetic)).fetchall()
            result['lookup_method'] = 'REGISTRATION'
        else:
            rows = self.db.execute('SELECT c.*,o.validation_status AS ingestion_status FROM m2_candidates c '
                                   'JOIN observations o ON o.id=c.observation_id WHERE c.brand_key=? AND c.synthetic=?',
                                   (brand_key(brand), synthetic)).fetchall()
            result['lookup_method'] = 'EXACT_OR_CONSERVATIVE_BRAND'
            if not rows:
                rows = self.db.execute('SELECT c.*,o.validation_status AS ingestion_status FROM m2_aliases a JOIN m2_candidates c '
                    'ON c.candidate_key=a.candidate_key JOIN observations o ON o.id=c.observation_id WHERE a.alias_key=? AND c.synthetic=?',
                    (brand_key(brand), synthetic)).fetchall()
                if rows:
                    result['lookup_method'] = 'VERIFIED_ALIAS'
        groups = {}
        for row in rows:
            raw = json.loads(row['projection_json'])
            # Every supplied identity qualifier is a constraint, never a tie-breaking guess.
            if brand and brand_key(brand) != row['brand_key'] and result['lookup_method'] != 'VERIFIED_ALIAS':
                continue
            filters = [('strength', 'strength_raw', strength_key),
                       ('dosage_form', 'dosage_form_raw', form_key), ('manufacturer', 'manufacturer_raw', key)]
            qualifiers = deepcopy(raw)
            if not qualifiers.get('strength'):
                components = parse_ingredients(raw.get('ingredients'), raw.get('strength'))
                if components['status'] == 'PARSED' and len(components['ingredients']) == 1:
                    qualifiers['strength'] = components['ingredients'][0]['strength_raw']
            if any((value := medication.get(field) or medication.get(alternate)) and
                   normalize(value) != normalize(qualifiers.get(field)) for field, alternate, normalize in filters):
                continue
            cid = row['candidate_key']
            if cid not in groups:
                review = self.db.execute('SELECT status,reviewer,reviewed_at,evidence_json FROM m2_reviews '
                                         'WHERE candidate_key=? ORDER BY id DESC LIMIT 1', (cid,)).fetchone()
                conflict = bool(row['registration_key']) and self.db.execute(
                    'SELECT count(DISTINCT candidate_key)>1 FROM m2_candidates WHERE registration_key=? AND synthetic=?',
                    (row['registration_key'], synthetic)).fetchone()[0]
                groups[cid] = {'candidate_key': cid, 'product': raw, 'registration_number': row['registration_key'],
                    'source_evidence': self.evidence(cid), 'synthetic_fixture': bool(row['synthetic']),
                    'independent_review': dict(review) if review else None,
                    'ingestion_statuses': [],
                    'registration_description_conflict': bool(conflict), 'current_authorization': 'UNKNOWN'}
            if row['ingestion_status'] not in groups[cid]['ingestion_statuses']:
                groups[cid]['ingestion_statuses'].append(row['ingestion_status'])
        result['candidates'] = list(groups.values())
        if len(groups) > 1:
            result.update(identification_status='REVIEW_REQUIRED', issues=['MULTIPLE_PRODUCT_CANDIDATES'])
        elif groups:
            candidate = next(iter(groups.values()))
            if result['lookup_method'] == 'VERIFIED_ALIAS':
                candidate['alias_evidence'] = [json.loads(r[0]) for r in self.db.execute(
                    'SELECT evidence_json FROM m2_aliases WHERE alias_key=? AND candidate_key=?',
                    (brand_key(brand), candidate['candidate_key']))]
            review = candidate['independent_review']
            result['identification_status'] = 'REVIEW_REQUIRED'
            if 'QUARANTINED' in candidate['ingestion_statuses']:
                result['issues'].append('SOURCE_OBSERVATION_QUARANTINED')
            elif candidate['registration_description_conflict']:
                result['issues'].append('CONFLICTING_REGISTRATION_OBSERVATIONS')
            elif review and review['status'] == 'VERIFIED':
                result['identification_status'] = 'VERIFIED'
            else:
                result['issues'].append('INDEPENDENT_PRODUCT_IDENTITY_REVIEW_PENDING')
        else:
            result['issues'].append('NO_CANDIDATE_SATISFIES_SUPPLIED_IDENTITY')
            if brand:
                known = [r[0] for r in self.db.execute('SELECT DISTINCT brand_key FROM m2_candidates WHERE synthetic=?', (synthetic,))]
                result['suggestions'] = [{'brand_key': x, 'status': 'REVIEW_REQUIRED', 'establishes_identity': False}
                    for x in difflib.get_close_matches(brand_key(brand), known, n=5, cutoff=.8)]
        return result


def review_product(path, candidate, *, status, reviewer, evidence):
    """Append explicit historical-identity adjudication; raw status is never rewritten."""
    if status not in {'VERIFIED', 'REVIEW_REQUIRED', 'UNRESOLVED', 'REJECTED'} or not reviewer or not _review_evidence(evidence):
        raise ValueError('Review requires status, reviewer and source evidence')
    with closing(sqlite3.connect(path)) as db, db:
        if not db.execute('SELECT 1 FROM m2_candidates WHERE candidate_key=?', (candidate,)).fetchone():
            raise ValueError('Unknown product candidate')
        db.execute('INSERT INTO m2_reviews(candidate_key,status,reviewer,reviewed_at,evidence_json) VALUES(?,?,?,?,?)',
            (candidate, status, reviewer, datetime.now(timezone.utc).isoformat(), dumps(evidence)))


def add_alias(path, alias, candidate, *, reviewer, evidence):
    if not alias or not reviewer or not _review_evidence(evidence):
        raise ValueError('Alias requires explicit reviewed identity evidence')
    with closing(sqlite3.connect(path)) as db, db:
        if not db.execute('SELECT 1 FROM m2_candidates WHERE candidate_key=?', (candidate,)).fetchone():
            raise ValueError('Unknown alias target')
        db.execute('INSERT INTO m2_aliases VALUES(?,?,?)',
            (brand_key(alias), candidate, dumps({'reviewer': reviewer, 'evidence': evidence})))


def _review_evidence(evidence):
    return isinstance(evidence, list) and bool(evidence) and all(isinstance(e, dict) and e.get('locator')
        and re.fullmatch(r'[0-9a-f]{64}', e.get('sha256', '')) for e in evidence)
