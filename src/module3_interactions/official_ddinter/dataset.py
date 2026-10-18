"""SQLite adapter for the existing Module 3 API, retaining every source row."""
from collections import defaultdict
from contextlib import closing
from copy import deepcopy
import csv
import json
from shared.paths import ProjectPath as Path, PROJECT_ROOT
import sqlite3
from urllib.parse import urlparse
from shared.dav_import.common import dumps, file_hash
from ..engine import HEADERS, valid_id, text_key, pair_key

SCHEMA = '''
CREATE TABLE metadata(key TEXT PRIMARY KEY,value_json TEXT NOT NULL);
CREATE TABLE artifacts(filename TEXT PRIMARY KEY,url TEXT NOT NULL,sha256 TEXT NOT NULL,metadata_json TEXT NOT NULL);
CREATE TABLE source_rows(filename TEXT NOT NULL REFERENCES artifacts(filename),row_number INTEGER NOT NULL,
 id_a TEXT NOT NULL,name_a TEXT NOT NULL,id_b TEXT NOT NULL,name_b TEXT NOT NULL,level TEXT NOT NULL,
 low_id TEXT NOT NULL,high_id TEXT NOT NULL,PRIMARY KEY(filename,row_number));
CREATE TABLE identities(identifier TEXT PRIMARY KEY,identity_json TEXT NOT NULL);
CREATE INDEX source_pair ON source_rows(low_id,high_id);
CREATE INDEX source_id_a ON source_rows(id_a);
CREATE INDEX source_id_b ON source_rows(id_b);
'''


def build_index(collection, output, *, public_record=None):
    collection, output = Path(collection).resolve(), Path(output).resolve()
    manifest_path = collection / 'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest.get('schema_version') != 'ddinter.official_collection.v1' or not manifest.get('artifacts'):
        raise ValueError('Expected a completed official collection manifest')
    if output.exists() or output.with_suffix('.manifest.json').exists():
        raise ValueError('Choose a new index path; prior evidence is immutable')
    files = manifest['artifacts']
    synthetic = manifest.get('synthetic_fixture', False)
    if not isinstance(synthetic, bool):
        raise ValueError('Synthetic fixture flag must be a boolean')
    if len({a['filename'] for a in files}) != len(files):
        raise ValueError('Repeated artifact filenames in collection')
    for artifact in files:
        filename = artifact['filename']
        if Path(filename).name != filename or file_hash(collection / filename) != artifact['sha256']:
            raise ValueError('Artifact path/hash mismatch: ' + filename)
        source = urlparse(artifact['source_url'])
        if not synthetic and (source.scheme != 'https' or source.hostname != 'ddinter2.scbdd.com'):
            raise ValueError('Real collection requires official HTTPS artifact URLs')
        if synthetic and source.scheme != 'synthetic':
            raise ValueError('Synthetic index tests require synthetic:// source provenance')
    output.parent.mkdir(parents=True, exist_ok=True)
    names = defaultdict(lambda: defaultdict(list))
    levels, file_reports = defaultdict(int), []
    with closing(sqlite3.connect(output)) as db:
        db.execute('PRAGMA foreign_keys=ON')
        db.executescript(SCHEMA)
        with db:
            for artifact in files:
                filename = artifact['filename']
                db.execute('INSERT INTO artifacts VALUES(?,?,?,?)',
                           (filename, artifact['source_url'], artifact['sha256'], dumps(artifact)))
                row_count, batch = 0, []
                with (collection / filename).open(encoding='utf-8-sig', newline='') as stream:
                    reader = csv.DictReader(stream)
                    if reader.fieldnames != HEADERS:
                        raise ValueError('Unexpected exact CSV schema: ' + filename)
                    for index, row in enumerate(reader, 1):
                        if set(row) != set(HEADERS) or any(not isinstance(v, str) for v in row.values()):
                            raise ValueError(f'Malformed CSV width/type at {filename}:{index}')
                        for side in ('A', 'B'):
                            identifier, name = row['DDInterID_' + side], row['Drug_' + side]
                            if not valid_id(identifier) or not name.strip():
                                raise ValueError(f'Invalid drug endpoint at {filename}:{index}')
                            variants = names[identifier][text_key(name)]
                            # Preserve first occurrence of every raw spelling plus all original rows in SQL.
                            if not any(v['name'] == name for v in variants):
                                variants.append({'name': name, 'filename': filename, 'row_number': index, 'endpoint': side})
                        if not row['Level'].strip():
                            raise ValueError(f'Empty severity at {filename}:{index}')
                        a, b = row['DDInterID_A'], row['DDInterID_B']
                        low, high = pair_key(a, b)
                        batch.append((filename, index, a, row['Drug_A'], b, row['Drug_B'], row['Level'], low, high))
                        row_count += 1
                        levels[row['Level']] += 1
                        if len(batch) == 2000:
                            db.executemany('INSERT INTO source_rows VALUES(?,?,?,?,?,?,?,?,?)', batch)
                            batch.clear()
                    if batch:
                        db.executemany('INSERT INTO source_rows VALUES(?,?,?,?,?,?,?,?,?)', batch)
                if not row_count:
                    raise ValueError('Empty offered CSV: ' + filename)
                file_reports.append({'filename': filename, 'source_rows': row_count, 'sha256': artifact['sha256']})
            artifacts = {a['filename']: a for a in files}
            conflicts = []
            identities = {}
            for identifier, semantic_names in sorted(names.items()):
                variants = [v for group in semantic_names.values() for v in group]
                first = variants[0]
                artifact = artifacts[first['filename']]
                identity = {'name': first['name'], 'synonyms': [],
                    'identity_status': 'VERIFIED' if len(semantic_names) == 1 else 'REVIEW_REQUIRED',
                    'name_candidates': [v['name'] for v in variants],
                    'evidence': {'kind': 'synthetic_endpoint' if synthetic else 'official_csv_endpoint', 'source_url': artifact['source_url'],
                        'csv_sha256': artifact['sha256'], 'filename': first['filename'],
                        'csv_record_1_based': first['row_number'], 'id_column': 'DDInterID_' + first['endpoint'],
                        'name_column': 'Drug_' + first['endpoint'], 'review_scope': 'drug_entity_only',
                        'source_name_variants': variants}}
                if len(semantic_names) > 1:
                    conflicts.append({'ddinter_id': identifier, 'names': identity['name_candidates']})
                identities[identifier] = identity
            synonym_evidence = None
            if public_record:
                public_record = Path(public_record)
                public = json.loads(public_record.read_text(encoding='utf-8'))
                for artifact in public.get('source_artifacts', []):
                    if file_hash(artifact['path']) != artifact['sha256']:
                        raise ValueError('Official synonym source artifact hash mismatch')
                synonym_evidence = {'path': str(public_record.resolve()), 'sha256': file_hash(public_record)}
                for entry in public['records']:
                    identifier = entry['ddinter_id']
                    known = identities.get(identifier)
                    if not known or known['identity_status'] != 'VERIFIED' or text_key(known['name']) != text_key(entry['name']):
                        continue
                    for synonym in entry.get('synonyms', []):
                        if (synonym.get('verification') == 'explicit_official_record_synonym'
                                and synonym.get('source_url') == f'https://ddinter2.scbdd.com/server/drug-detail/{identifier}/'):
                            known['synonyms'].append(synonym['name'])
                            known['evidence'].setdefault('synonym_evidence', []).append(
                                {**deepcopy(synonym), 'snapshot_sha256': synonym_evidence['sha256']})
            for identifier, identity in identities.items():
                db.execute('INSERT INTO identities VALUES(?,?)', (identifier, dumps(identity)))
            source_rows = db.execute('SELECT count(*) FROM source_rows').fetchone()[0]
            pairs = db.execute('SELECT count(*) FROM (SELECT low_id,high_id FROM source_rows GROUP BY low_id,high_id)').fetchone()[0]
            pair_levels = db.execute('SELECT count(*) FROM (SELECT low_id,high_id,level FROM source_rows GROUP BY low_id,high_id,level)').fetchone()[0]
            duplicates = db.execute('SELECT count(*) FROM (SELECT low_id,high_id FROM source_rows GROUP BY low_id,high_id HAVING count(*)>1)').fetchone()[0]
            contradictory = db.execute('SELECT count(*) FROM (SELECT low_id,high_id FROM source_rows GROUP BY low_id,high_id HAVING count(DISTINCT level)>1)').fetchone()[0]
            contradiction_examples = [dict(zip(('drug_id_a', 'drug_id_b', 'source_rows', 'original_levels'), r))
                for r in db.execute('SELECT low_id,high_id,count(*),group_concat(DISTINCT level) FROM source_rows '
                                    'GROUP BY low_id,high_id HAVING count(DISTINCT level)>1 LIMIT 30')]
            name_ids = defaultdict(set)
            for identifier, values in names.items():
                for name in values:
                    name_ids[name].add(identifier)
            published = manifest['published_statistics']
            coverage = {'scope': 'all explicitly offered official DDInter 2.0 CSV categories; partial published release',
                'dataset_verdict': 'PARTIAL', 'offered_csv_collection_complete': manifest['all_explicit_csv_hyperlinks_acquired'],
                'complete_database_loaded': False, 'interaction_coverage_complete': False,
                'file_release_version_independently_verified': False, 'synthetic_fixture': synthetic,
                'loaded_rows': source_rows, 'unique_interaction_pairs': pairs, 'distinct_pair_severity_records': pair_levels,
                'unique_pair_endpoint_ids': len(identities), 'identity_evidence_entries': len(identities),
                'duplicate_pair_groups': duplicates, 'duplicate_pair_occurrences': source_rows - pairs,
                'duplicate_pair_severity_occurrences': source_rows - pair_levels,
                'contradictory_severity_pairs': contradictory, 'conflicting_identifier_names': len(conflicts),
                'same_name_multiple_identifiers': sum(len(ids) > 1 for ids in name_ids.values()),
                'self_pair_source_rows': db.execute('SELECT count(*) FROM source_rows WHERE id_a=id_b').fetchone()[0],
                'original_severity_counts': dict(levels), 'files': file_reports,
                'published_statistics': published,
                'ddi_pair_count_difference_from_published_records': published['ddi_records'] - pairs,
                'drug_id_count_difference_from_published_entries': published['drug_entries'] - len(identities),
                'comparison_limitation': 'Published records/entries and CSV unordered pairs/endpoints may have different definitions and release dates.',
                'clinical_mechanisms_available': False, 'management_available': False, 'clinical_references_available': False,
                'license': manifest['license'], 'source_url': 'synthetic://official-index-tests' if synthetic else 'https://ddinter2.scbdd.com/download/',
                'missing_explicit_category_downloads': sorted(set('ABCDGHJLMNPRSVU') - {a['filename'].split('_')[-1][0] for a in files}),
                'missing_release_evidence': 'No full dictionary, full-release DDI export or mechanisms/management/reference fields offered on inspected page.'}
            db.execute('INSERT INTO metadata VALUES(?,?)', ('coverage', dumps(coverage)))
            db.execute('INSERT INTO metadata VALUES(?,?)', ('version', dumps('ddinter-official-index-v1')))
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('SQLite index integrity failure')
    report = {'schema_version': 'ddinter.official_index.v1', 'index_sha256': file_hash(output),
        'collection_manifest_sha256': file_hash(manifest_path), 'collection': str(collection),
        'coverage': coverage, 'identifier_conflicts': conflicts, 'severity_conflict_examples': contradiction_examples,
        'synonym_snapshot': synonym_evidence}
    output.with_suffix('.manifest.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return report


class OfficialDataset:
    """Same identities/coverage/lookup contract consumed by engine.assess()."""
    def __init__(self, path):
        self.path = Path(path).resolve()
        seal = json.loads(self.path.with_suffix('.manifest.json').read_text(encoding='utf-8'))
        if seal.get('schema_version') != 'ddinter.official_index.v1' or file_hash(self.path) != seal['index_sha256']:
            raise ValueError('Unified index schema/hash mismatch')
        collection = Path(seal['collection'])
        if file_hash(collection / 'manifest.json') != seal['collection_manifest_sha256']:
            raise ValueError('Collection manifest hash mismatch')
        manifest = json.loads((collection / 'manifest.json').read_text(encoding='utf-8'))
        for artifact in manifest['artifacts']:
            if Path(artifact['filename']).name != artifact['filename'] or file_hash(collection / artifact['filename']) != artifact['sha256']:
                raise ValueError('Original CSV hash mismatch: ' + artifact['filename'])
        for name, page in manifest.get('official_pages', {}).items():
            if Path(page['filename']).name != page['filename'] or file_hash(collection / page['filename']) != page['sha256']:
                raise ValueError('Official page snapshot hash mismatch: ' + name)
        snapshot = seal.get('synonym_snapshot')
        if snapshot and file_hash(snapshot['path']) != snapshot['sha256']:
            raise ValueError('Official synonym snapshot hash mismatch')
        if snapshot:
            public = json.loads(Path(snapshot['path']).read_text(encoding='utf-8'))
            for artifact in public.get('source_artifacts', []):
                if file_hash(artifact['path']) != artifact['sha256']:
                    raise ValueError('Official synonym source artifact hash mismatch')
        with closing(self._connect()) as db:
            self.coverage = json.loads(db.execute("SELECT value_json FROM metadata WHERE key='coverage'").fetchone()[0])
            self.identities = {identifier: json.loads(value) for identifier, value in db.execute('SELECT identifier,identity_json FROM identities')}

    def _connect(self):
        return sqlite3.connect(self.path.as_uri() + '?mode=ro', uri=True)

    def lookup(self, a, b):
        if not valid_id(a) or not valid_id(b):
            raise ValueError('Pair lookup requires actual DDInter identifiers')
        low, high = pair_key(a, b)
        with closing(self._connect()) as db:
            rows = db.execute('SELECT s.filename,s.row_number,s.id_a,s.name_a,s.id_b,s.name_b,s.level,a.url,a.sha256 '
                'FROM source_rows s JOIN artifacts a ON a.filename=s.filename WHERE s.low_id=? AND s.high_id=? '
                'ORDER BY s.filename,s.row_number', (low, high)).fetchall()
        records = []
        for filename, number, id_a, name_a, id_b, name_b, level, url, sha in rows:
            records.append({'drug_id_pair': [low, high], 'original_level': level,
                'raw_source_row': dict(zip(HEADERS, (id_a, name_a, id_b, name_b, level))),
                'evidence': {'filename': filename, 'source_url': url, 'csv_sha256': sha,
                    'csv_record_1_based': number, 'level_column': 'Level',
                    'source_kind': 'synthetic_fixture' if self.coverage.get('synthetic_fixture') else 'official_public_csv'},
                'mechanism': None, 'management': None, 'clinical_references': None})
        if not records:
            return {'status': 'NO_RECORD_IN_LOADED_SUBSET', 'source_records': [],
                    'coverage_conclusion': 'INSUFFICIENT_COVERAGE', 'original_level': None, 'safe': None}
        levels = list(dict.fromkeys(r['original_level'] for r in records))
        conflict = len(levels) > 1 or low == high
        return {'status': 'CONFLICTING_SOURCE_RECORDS' if conflict else 'INTERACTION_DETECTED',
            'original_level': levels[0] if not conflict else None, 'original_levels': levels,
            'source_records': records, 'coverage_conclusion': 'POSITIVE_RECORD_ONLY_NOT_EXHAUSTIVE', 'safe': None}
