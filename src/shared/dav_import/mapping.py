"""Reusable offline ingredient adapters. Exact candidates remain unverified."""
from collections import defaultdict
import importlib.util
import json
from shared.paths import ProjectPath as Path, PROJECT_ROOT
import re
from urllib.parse import urlparse
from .common import digest, dumps, file_hash
from .normalize import key
from .pipeline import connect

ADAPTER_VERSION = 'ingredient-map-v1'


class IngredientIndex:
    """Normalized licensed snapshot contract, not an assumed upstream export schema."""
    namespace = None

    def __init__(self, records, release, *, synthetic=False):
        if not release:
            raise ValueError('Terminology release identifier is required')
        self.release = release
        self.synthetic = synthetic
        self.index = defaultdict(list)
        by_id = {}
        for record in records:
            if record.get('synthetic_fixture', False) is not synthetic:
                raise ValueError('Terminology fixture/source kind mismatch')
            if not record.get('name') or not isinstance(record.get('synonyms', []), list):
                raise ValueError('Mapping records need a name and optional synonym list')
            evidence = record.get('evidence', {})
            if not evidence.get('source_url') or not re.fullmatch(r'[0-9a-f]{64}', evidence.get('artifact_sha256', '')) or not evidence.get('locator'):
                raise ValueError('Terminology records need URL, artifact hash, and row/concept locator')
            if not synthetic:
                host = urlparse(evidence['source_url']).hostname or ''
                allowed = (host == 'nlm.nih.gov' or host.endswith('.nlm.nih.gov')) if self.namespace == 'RxNorm' else host in {'ddinter.scbdd.com', 'ddinter2.scbdd.com'}
                if not allowed:
                    raise ValueError('Real terminology mapping requires official namespace source provenance')
            self.validate(record)
            if record['id'] in by_id and digest(by_id[record['id']]) != digest(record):
                raise ValueError('Conflicting terminology records for one source identifier')
            by_id[record['id']] = record
            for name in [record['name'], *record.get('synonyms', [])]:
                self.index[key(name)].append(record)
        self.fingerprint = digest({'records': list(by_id.values()), 'release': release, 'synthetic': synthetic})

    def validate(self, record):
        raise NotImplementedError

    def resolve(self, name):
        candidates = {r['id']: r for r in self.index.get(key(name), [])}
        eligible = [r for r in candidates.values() if self.eligible(r)]
        result = {'namespace': self.namespace, 'release': self.release, 'adapter_version': ADAPTER_VERSION,
                  'input_name': name, 'status': 'UNRESOLVED', 'target_id': None, 'target_name': None,
                  'concept_type': None, 'evidence': [], 'candidates': sorted(candidates)}
        if len(candidates) > 1:
            result['status'] = 'AMBIGUOUS'
            result['evidence'] = [r['evidence'] for r in candidates.values()]
        elif len(eligible) == 1:
            r = eligible[0]
            result.update(status='CANDIDATE', target_id=r['id'], target_name=r['name'],
                          concept_type=r.get('tty'), evidence=[r['evidence']])
        elif candidates:
            result.update(status='REJECTED', evidence=[r['evidence'] for r in candidates.values()])
        return result

    def eligible(self, record):
        return True

    @classmethod
    def from_snapshot(cls, path, *, allow_synthetic=False):
        snapshot = json.loads(Path(path).read_text(encoding='utf-8'))
        if snapshot.get('schema_version') != 'dav.ingredient_snapshot.v1' or snapshot.get('namespace') != cls.namespace:
            raise ValueError('Wrong terminology snapshot schema/namespace')
        if snapshot.get('synthetic_fixture') and not allow_synthetic:
            raise ValueError('Synthetic terminology snapshot requires explicit allow_synthetic')
        if not snapshot.get('license_or_permission'):
            raise ValueError('Snapshot must record license/permission')
        # Bind supplied record locators to this local snapshot too.
        snapshot_hash = file_hash(path)
        for row in snapshot['records']:
            row['evidence']['snapshot_sha256'] = snapshot_hash
        return cls(snapshot['records'], snapshot['release'], synthetic=bool(snapshot.get('synthetic_fixture')))


class RxNormAdapter(IngredientIndex):
    namespace = 'RxNorm'

    def validate(self, record):
        if not re.fullmatch(r'\d+', record.get('id', '')):
            raise ValueError('RxNorm uses numeric RxCUIs')

    def eligible(self, record):
        return record.get('tty') in {'IN', 'PIN'} and record.get('concept_status') == 'Active'


class DDInterAdapter(IngredientIndex):
    namespace = 'DDInter'

    def validate(self, record):
        if not re.fullmatch(r'DDInter\d+', record.get('id', '')):
            raise ValueError('DDInter uses actual DDInter-prefixed identifiers, never RxCUIs')


class SavedRxNormCacheAdapter:
    """Reuse existing exact-query/properties/history cache reader without new API calls."""
    namespace = 'RxNorm'
    synthetic = False

    def __init__(self, cache_dir, release):
        if not release:
            raise ValueError('Identify saved cache release/date explicitly')
        path = Path(__file__).parent / 'saved_rxnorm.py'
        spec = importlib.util.spec_from_file_location('_dav_existing_rxnorm_cache', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.client = module.SavedRxNorm(Path(cache_dir))
        self.release = release
        self.code_hash = file_hash(path)
        self.fingerprint = digest({'reader_code': self.code_hash, 'release': release,
            'cache_files': {p.name: file_hash(p) for p in sorted(Path(cache_dir).glob('*.json'))}})

    def resolve(self, name):
        result = self.client.resolve(name)
        return {'namespace': self.namespace, 'release': self.release, 'adapter_version': ADAPTER_VERSION,
                'input_name': name, 'status': {'VERIFIED': 'CANDIDATE', 'REVIEW_REQUIRED': 'UNRESOLVED'}.get(result['status'], result['status']),
                'target_id': result.get('rxcui'), 'target_name': result.get('international_name'),
                'concept_type': result.get('tty'),
                'evidence': [*result['evidence'], {'reader_code_sha256': self.code_hash, 'issues': result['issues']}],
                'candidates': result['candidates']}


def map_ingredients(db_path, adapter):
    """One lookup per distinct source ingredient. Persistent results can be resumed/reused."""
    db = connect(db_path)
    count = 0
    try:
        ids = db.execute('SELECT id,source_name FROM ingredients WHERE synthetic=? ORDER BY id', (int(adapter.synthetic),)).fetchall()
        for row in ids:
            mid = digest({'ingredient': row['id'], 'namespace': adapter.namespace, 'release': adapter.release,
                          'adapter_version': ADAPTER_VERSION})
            existing = db.execute('SELECT evidence_json FROM terminology_mappings WHERE id=?', (mid,)).fetchone()
            if existing:
                saved = json.loads(existing['evidence_json'])
                if not saved or saved[-1].get('adapter_input_sha256') != adapter.fingerprint:
                    raise ValueError('Terminology snapshot/cache changed under same release; use a new release identifier')
                continue
            result = adapter.resolve(row['source_name'])
            proof = [*result['evidence'], {'adapter_input_sha256': adapter.fingerprint}]
            with db:
                db.execute('INSERT INTO terminology_mappings VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                           (mid, row['id'], adapter.namespace, adapter.release, ADAPTER_VERSION, row['source_name'],
                            result['status'], result['target_id'], result['target_name'], result['concept_type'],
                            dumps(proof), dumps(result['candidates'])))
            count += 1
        return count
    finally:
        db.close()
