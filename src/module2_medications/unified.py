"""Processed, opt-in research reference using the existing Module 2 contracts.

Only previously reviewed research shards are persisted. DAV observations are audited
separately; this module neither calls nor changes the bulk registry importer.
"""
from collections import Counter, defaultdict
from contextlib import closing
from copy import deepcopy
from datetime import datetime, timezone, timedelta
import json
from shared.paths import ProjectPath as Path, PROJECT_ROOT
import re
import sqlite3
from shared.dav_import.common import digest, dumps, file_hash
from shared.dav_import.normalize import parse_strength
from .curated import CuratedFactReference
from .ingredients import parse_ingredients, _split
from .research import ResearchSupplementReference
from .terminology import DirectDDInter, load_ddinter
from .text import clean, key, brand_key, registration, form_key
from .audit import audit_dataset

VERSION = 'module2.unified_research.v1'
CONFIG_VERSION = 'module2.unified_config.v1'
FORMS = {
    'tablet, film coated': 'film_coated_tablet', 'tablet, coated': 'coated_tablet',
    'tablet, extended release': 'extended_release_tablet',
    'tablet, delayed release': 'delayed_release_tablet',
    'capsule, delayed release': 'delayed_release_capsule',
    'capsule, extended release': 'extended_release_capsule',
    'injection, solution': 'injection_solution', 'solution for injection': 'injection_solution',
    'injection, suspension': 'injection_suspension', 'solution for injection in pre-filled pen': 'injection_solution_in_pre_filled_pen',
}
SCHEMA = '''
CREATE TABLE IF NOT EXISTS u_metadata(key TEXT PRIMARY KEY, value_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS u_observations(id TEXT PRIMARY KEY, path TEXT NOT NULL,
 sha256 TEXT NOT NULL, original_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS u_records(id TEXT PRIMARY KEY, observation_id TEXT NOT NULL REFERENCES u_observations(id),
 source_code TEXT NOT NULL, product_key TEXT NOT NULL, presentation_key TEXT NOT NULL,
 brand_key TEXT NOT NULL, registration_key TEXT, normalized_json TEXT NOT NULL,
 parsed_json TEXT NOT NULL, mappings_json TEXT NOT NULL, quality_json TEXT NOT NULL,
 identity_conflict INTEGER NOT NULL, fingerprint TEXT NOT NULL, active INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS u_brand ON u_records(brand_key,active);
CREATE INDEX IF NOT EXISTS u_code ON u_records(source_code,active);
CREATE INDEX IF NOT EXISTS u_reg ON u_records(registration_key,active);
CREATE INDEX IF NOT EXISTS u_presentation ON u_records(presentation_key,active);
CREATE TABLE IF NOT EXISTS u_memberships(record_id TEXT NOT NULL REFERENCES u_records(id),
 batch INTEGER NOT NULL, manifest_path TEXT NOT NULL, shard_path TEXT NOT NULL,
 active INTEGER NOT NULL, PRIMARY KEY(record_id,batch,manifest_path));
CREATE TABLE IF NOT EXISTS u_names(record_id TEXT NOT NULL REFERENCES u_records(id),
 kind TEXT NOT NULL, name_key TEXT NOT NULL, PRIMARY KEY(record_id,kind,name_key));
CREATE INDEX IF NOT EXISTS u_name_lookup ON u_names(kind,name_key);
CREATE TABLE IF NOT EXISTS u_builds(fingerprint TEXT PRIMARY KEY, created_at TEXT NOT NULL, summary_json TEXT NOT NULL);
'''

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

def default_config(project):
    return Path(project)/'data/processed/medication_reference/unified.runtime.config.json'

def discover_sources(project):
    """Use the retained manifests themselves, not historical/unfinished folders."""
    folder = Path(project)/'data/reference/research_supplements'
    batch3 = [p for p in folder.glob('*/supplement.json') if read(p).get('batch') == 3]
    if len(batch3) != 1: raise ValueError('Select the final Batch 3 manifest explicitly; expected one')
    selected = {3: batch3[0]}
    for shard in read(batch3[0])['shards']:
        path = (batch3[0].parent/shard['path']).resolve()
        parent_manifest = path.parent.parent/'supplement.json'
        if parent_manifest.is_file():
            artifact = read(parent_manifest); batch = artifact.get('batch')
            if batch in (1,2):
                if batch in selected and selected[batch] != parent_manifest:
                    raise ValueError('Ambiguous final prior supplement')
                selected[batch] = parent_manifest
    if set(selected) != {1,2,3}: raise ValueError('Final Batch 1 and Batch 2 paths not resolved from Batch 3')
    return [selected[b].resolve() for b in (1,2,3)]

def normalized_form(value):
    value = key(value)
    return FORMS.get(value, form_key(value))

def strength_signature(value):
    """Only explicit dose separators and the existing unit grammar are normalized."""
    value = clean(value)
    if not value: return ('raw', '')
    try: parts = _split(value)
    except ValueError: return ('raw', key(value))
    strengths = [parse_strength(p) for p in parts]
    if any(p['status'] != 'PARSED' for p in strengths): return ('raw', key(value))
    return tuple(tuple(p[f] for f in ('amount','unit','denominator_amount','denominator_unit')) for p in strengths)

def normalized_strength(value):
    signature = strength_signature(value)
    if signature[0] == 'raw': return clean(value)
    pieces = []
    for amount, unit, denominator, denominator_unit in signature:
        text = amount+' '+unit
        if denominator_unit: text += '/'+denominator+' '+denominator_unit
        pieces.append(text)
    return '; '.join(pieces)

def normalize_product(product, record_id=None):
    """Keys never remove salts, devices, release labels, jurisdiction or route."""
    parsed = parse_ingredients(product.get('ingredients'), product.get('strength'))
    components = []
    original = product.get('ingredients')
    for index, item in enumerate(parsed['ingredients']):
        source = original[index] if isinstance(original,list) else {}
        components.append({'name_key': key(item['normalized_ingredient']),
                           'source_form_key': key(item['source_form_declaration']),
                           'strength_key': strength_signature(item['strength_raw']),
                           'quantity_basis': source.get('quantity_basis_class'),
                           'basis': source.get('basis')})
    jurisdiction = (product.get('regulatory_identifiers') or {}).get('jurisdiction')
    reg = registration(product.get('registration_number'))
    family = {'brand': brand_key(product.get('brand_name')), 'registration': reg,
              'jurisdiction': jurisdiction or 'UNSPECIFIED',
              'manufacturer': key(product.get('manufacturer')), 'labeler': key(product.get('source_labeler')),
              'route': key(product.get('route')), 'ingredient_names': [
                  {k:c[k] for k in ('name_key','source_form_key','quantity_basis','basis')} for c in components]}
    # A family key is an inventory grouping, never a claim of interchangeability.
    family_key = digest(family)
    presentation = {**family, 'form': normalized_form(product.get('dosage_form')), 'components': components,
                    'overall_strength': strength_signature(product.get('strength')),
                    'device': key(product.get('source_presentation')),
                    'insulin_form': key(product.get('insulin_form')), 'premix_ratio': product.get('premix_ratio')}
    incomplete = parsed['status'] != 'PARSED' or not components or any(c['strength_key'][0] == 'raw' for c in components)
    possible_formulation_key = digest(presentation)
    # Distinct source presentations are retained even when incomplete device facts look equal.
    presentation.update(source_product_code=product.get('source_product_code'))
    if incomplete: presentation['unresolved_record'] = record_id or digest(product)
    normalized = {'cleaned_fields': {f:clean(product.get(f)) for f in ('brand_name','strength','dosage_form','route')},
                  'brand_key': family['brand'], 'registration_key':reg, 'dosage_form_key':presentation['form'],
                  'strength_key':presentation['overall_strength'], 'components':components,
                  'product_key':family_key, 'presentation_key':digest(presentation),
                  'possible_formulation_key':possible_formulation_key,
                  'rules':'Formatting/unit normalization only; ingredient salts, source codes and formulations retained'}
    return normalized, parsed

def validate_product(product, parsed):
    issues = []; missing = []
    for field in ('brand_name','ingredients','dosage_form'):
        value = product.get(field)
        if not value: missing.append(field); issues.append('MISSING_'+field.upper())
        elif field != 'ingredients' and not isinstance(value,str): issues.append('INVALID_TYPE_'+field.upper())
    if not product.get('source_product_code'): issues.append('MISSING_SOURCE_PRODUCT_CODE')
    for field in ('manufacturer','registration_number','source_labeler','route','strength'):
        if not product.get(field): missing.append(field)
        elif not isinstance(product[field],str): issues.append('INVALID_TYPE_'+field.upper())
    structured = isinstance(product.get('ingredients'),list)
    preserved = not structured or len(product['ingredients']) == len(parsed['ingredients'])
    if not preserved: issues.append('INGREDIENT_COMPONENT_COUNT_MISMATCH')
    if parsed['status'] != 'PARSED': issues.append('INGREDIENT_PARSING_'+parsed['status'])
    if any(i['strength']['status'] != 'PARSED' for i in parsed['ingredients']): issues.append('COMPONENT_STRENGTH_REVIEW')
    issues.extend(parsed['issues'])
    fatal = any(i.startswith(('MISSING_BRAND','MISSING_INGREDIENTS','MISSING_DOSAGE_FORM','INVALID_TYPE','INGREDIENT_COMPONENT_COUNT')) for i in issues)
    return {'status':'REVIEW_REQUIRED' if issues else 'VALID', 'issues':sorted(set(issues)),
            'missing_fields':missing, 'component_count_preserved':preserved,
            'block_product_identity':fatal,
            'strength_note':'Missing component quantities do not justify dose totals; supported ingredient identity can still be assessed'}

def load_sources(manifests, dataset):
    """Reuse recorded fact reviews and source hashes; never create a new equivalence."""
    records = {}; memberships = []; equivalences = {}; proof_hashes = {}; source_info = []
    for path in manifests:
        path = Path(path).resolve(); artifact = read(path)
        reference = ResearchSupplementReference(path)
        try:
            mapper = reference.terminology(dataset)
            entries = read(path.parent/'reviewed_equivalences.json')
            for e in entries:
                token = (key(e['source_name']),e['ddinter_id'])
                for known in equivalences:
                    if known[0] == token[0] and known[1] != token[1]: raise ValueError('Conflicting reviewed terminology links: '+e['source_name'])
                equivalences.setdefault(token,deepcopy(e))
            for shard, entry in zip(artifact['shards'], reference.products):
                shard_path = (path.parent/shard['path']).resolve(); code = entry['product']['source_product_code']
                record_id = digest({'path':str(shard_path),'source_code':code})
                records.setdefault(record_id, {'id':record_id,'path':str(shard_path),'sha256':file_hash(shard_path),
                                               'entry':deepcopy(entry), 'use_assessment':read(shard_path)['use_assessment']})
                memberships.append({'record_id':record_id,'batch':artifact['batch'], 'manifest_path':str(path), 'shard_path':str(shard_path)})
            source_info.append({'path':str(path),'sha256':file_hash(path),'batch':artifact['batch'],'presentations':len(reference.products)})
            for e in entries:
                for p in e['evidence']: proof_hashes[p['path']] = p['sha256']
        finally: reference.close()
    for record in records.values():
        for proof in record['entry']['source_evidence']+record['use_assessment']['source_basis']:
            if not proof.get('path') or not proof.get('sha256') or file_hash(proof['path']) != proof['sha256']:
                raise ValueError('Missing or mismatched retained source/use evidence')
            proof_hashes[proof['path']] = proof['sha256']
    mapper = DirectDDInter(dataset,equivalences.values())
    return list(records.values()), memberships, list(equivalences.values()), source_info, proof_hashes, mapper

def preprocess(project, *, manifests=None, database=None, config=None, dataset=None, progress=print, audit_dav=True):
    project = Path(project).resolve(); config = Path(config or default_config(project)).resolve()
    database = Path(database or config.parent/'unified.sqlite').resolve()
    progress('UNIFIED MEDICATION PREPROCESSING')
    progress('[1/6] Loading datasets...')
    manifests = manifests or discover_sources(project)
    dataset = dataset or load_ddinter(project,'official-all')
    records, memberships, entries, sources, proofs, mapper = load_sources(manifests,dataset)
    progress('[2/6] Validating source records...')
    dav = None
    if audit_dav:
        raw_path = project/'data/raw/dav/records.jsonl'
        dav = audit_dataset(raw_path,mapper,as_of=datetime.now(timezone(timedelta(hours=7))).date().isoformat())
        raw_families = set(); raw_presentations = set()
        for line in raw_path.open(encoding='utf-8-sig'):
            try: raw = json.loads(line)
            except json.JSONDecodeError: continue
            if not isinstance(raw,dict): continue
            n,_ = normalize_product(raw,digest(raw))
            raw_families.add(n['product_key']); raw_presentations.add(n['presentation_key'])
        dav['unique_observed_product_keys'] = len(raw_families)
        dav['unique_observed_presentation_keys'] = len(raw_presentations)
        if file_hash(raw_path) != dav['source']['sha256']: raise ValueError('DAV audit input changed')
        progress(f'DAV quality: {dav["counts"].get("valid_source_observations",0)} valid observations; '
                 f'{dav["counts"].get("exact_duplicate_observations",0)} exact duplicates; '
                 f'{dav["counts"].get("invalid_source_metadata",0)} incomplete provenance records (audit only).')
    missing = Counter(); warnings = Counter(); formats = Counter()
    for record in records:
        p = record['entry']['product']; normalized, parsed = normalize_product(p,record['id'])
        quality = validate_product(p,parsed)
        record.update(normalized=normalized,parser=parsed,quality=quality)
        missing.update(quality['missing_fields']); warnings.update(quality['issues']); formats[type(p.get('ingredients')).__name__] += 1
    progress(f'Quality before processing: {len(records)} supported presentations; missing brand={missing["brand_name"]}, form={missing["dosage_form"]}; component quantity review={warnings["COMPONENT_STRENGTH_REVIEW"]}.')
    progress('[3/6] Cleaning and normalizing...')
    progress('[4/6] Checking duplicates...')
    codes = defaultdict(list); registrations = defaultdict(list); possible = defaultdict(list)
    for r in records:
        p = r['entry']['product']; codes[p['source_product_code']].append(r)
        if r['normalized']['registration_key']:
            registrations[(r['normalized']['registration_key'],(p.get('regulatory_identifiers') or {}).get('jurisdiction','UNSPECIFIED'))].append(r)
        possible[r['normalized']['possible_formulation_key']].append(r)
    conflicts = set()
    for group in list(codes.values())+list(registrations.values()):
        if len({r['normalized']['possible_formulation_key'] for r in group}) > 1:
            conflicts.update(r['id'] for r in group)
    progress('[5/6] Parsing and mapping ingredients...')
    unresolved = Counter(); ingredient_names = set(); ddinter_ids = set()
    for r in records:
        mappings = []
        for item in r['parser']['ingredients']:
            m = mapper.match(item['normalized_ingredient'])
            if item['extraction_status'] != 'PARSED':
                m.update(mapping_status='REVIEW_REQUIRED',ddinter_id=None,unresolved_reason='INGREDIENT_EXTRACTION_REVIEW_REQUIRED')
            mappings.append(m); ingredient_names.add(key(item['normalized_ingredient']))
            if m['mapping_status'] != 'VERIFIED': unresolved[key(item['normalized_ingredient'])] += 1
            else: ddinter_ids.add(m['ddinter_id'])
        r['mappings'] = mappings; r['conflict'] = r['id'] in conflicts
        r['complete_mapping'] = bool(mappings) and r['parser']['status'] == 'PARSED' and all(m['mapping_status']=='VERIFIED' for m in mappings)
        r['ready'] = r['complete_mapping'] and not r['conflict'] and not r['quality']['block_product_identity']
    # Exact source facts are distinguished from potential equal formulations with distinct codes.
    unique_observations = len({digest(r['entry']) for r in records})
    duplicates = {'repeated_source_memberships':len(memberships)-len(records),
                  'exact_repeated_fact_records':len(records)-unique_observations,
                  'possible_same_formulation_groups':sum(len(g)>1 for g in possible.values()),
                  'possible_same_formulation_extra_presentations':sum(len(g)-1 for g in possible.values() if len(g)>1),
                  'conflicting_record_identities':len(conflicts),
                  'policy':'Only identical supported source presentation identities are grouped; distinct NDCs/devices/registrations remain separate.'}
    summary = {'source_memberships':len(memberships),'source_presentations':len(records),
               'unique_medication_products':len({r['normalized']['product_key'] for r in records}),
               'product_presentations':len({r['normalized']['presentation_key'] for r in records}),
               'complete_parsing':sum(r['parser']['status']=='PARSED' for r in records),
               'complete_mappings':sum(r['complete_mapping'] for r in records),
               'module3_ready_presentations':sum(r['ready'] for r in records),
               'ingredient_name_keys':len(ingredient_names),'verified_ddinter_identities':len(ddinter_ids),
               'unresolved_ingredient_name_keys':len(unresolved),'unresolved_names':dict(unresolved),
               'missing_fields':dict(missing),'quality_issue_counts':dict(warnings),'ingredient_formats':dict(formats),
               'duplicates':duplicates,'sources':sources,'bulk_dav_persistence':'LIMITED_AUDIT_ONLY',
               'supported_registered_fact_presentations':sum(bool(r['entry']['product'].get('registration_number')) for r in records),
               'clinical_accuracy_validated':False}
    engine_hashes = {str(Path(__file__).resolve()):file_hash(__file__),
                     str(Path(__file__).with_name('ingredients.py')):file_hash(Path(__file__).with_name('ingredients.py')),
                     str(Path(__file__).with_name('terminology.py')):file_hash(Path(__file__).with_name('terminology.py'))}
    index_hash = file_hash(dataset.path)
    fingerprint = digest({'version':VERSION,'sources':sources,'records':[(r['id'],r['sha256']) for r in records],
                          'equivalences':entries,'index':index_hash,'engines':engine_hashes})
    progress('[6/6] Building unified reference...')
    database.parent.mkdir(parents=True,exist_ok=True)
    unchanged = False; upserted = 0
    if database.exists():
        if config.exists() and file_hash(database) != read(config).get('database_sha256'):
            raise ValueError('Refusing to reseal a modified processed database')
        with closing(sqlite3.connect(database.resolve().as_uri()+'?mode=ro',uri=True)) as db:
            try: known = dict(db.execute('SELECT key,value_json FROM u_metadata'))
            except sqlite3.Error as error: raise ValueError('Refusing to modify an unrelated database') from error
            if json.loads(known.get('version','null')) != VERSION: raise ValueError('Unsupported processed database')
            unchanged = config.exists() and json.loads(known.get('fingerprint','null')) == fingerprint
    if not unchanged:
        with closing(sqlite3.connect(database)) as db:
            db.execute('PRAGMA foreign_keys=ON'); db.executescript(SCHEMA)
            with db:
                db.execute('UPDATE u_records SET active=0'); db.execute('UPDATE u_memberships SET active=0')
                for r in records:
                    observation_id = digest({'path':r['path'],'sha256':r['sha256']})
                    db.execute('INSERT OR IGNORE INTO u_observations VALUES(?,?,?,?)',
                               (observation_id,r['path'],r['sha256'],dumps(r['entry'])))
                    record_fingerprint = digest({k:r[k] for k in ('sha256','normalized','parser','mappings','quality','conflict')})
                    old = db.execute('SELECT fingerprint FROM u_records WHERE id=?',(r['id'],)).fetchone()
                    upserted += old is None or old[0] != record_fingerprint
                    p = r['entry']['product']; n = r['normalized']
                    db.execute('INSERT INTO u_records VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET '
                               'observation_id=excluded.observation_id,source_code=excluded.source_code,product_key=excluded.product_key,'
                               'presentation_key=excluded.presentation_key,brand_key=excluded.brand_key,registration_key=excluded.registration_key,'
                               'normalized_json=excluded.normalized_json,parsed_json=excluded.parsed_json,mappings_json=excluded.mappings_json,'
                               'quality_json=excluded.quality_json,identity_conflict=excluded.identity_conflict,fingerprint=excluded.fingerprint,active=1',
                               (r['id'],observation_id,p['source_product_code'],n['product_key'],n['presentation_key'],n['brand_key'],n['registration_key'],
                                dumps(n),dumps(r['parser']),dumps(r['mappings']),dumps(r['quality']),int(r['conflict']),record_fingerprint,1))
                    db.execute('DELETE FROM u_names WHERE record_id=?',(r['id'],))
                    tokens = {('ingredient_raw',key(i['normalized_ingredient'])) for i in r['parser']['ingredients']}
                    tokens |= {('ingredient_id',m['ddinter_id']) for m in r['mappings'] if m['mapping_status']=='VERIFIED'}
                    db.executemany('INSERT INTO u_names VALUES(?,?,?)',[(r['id'],kind,token) for kind,token in tokens])
                for m in memberships:
                    db.execute('INSERT INTO u_memberships VALUES(?,?,?,?,1) ON CONFLICT(record_id,batch,manifest_path) DO UPDATE SET shard_path=excluded.shard_path,active=1',
                               (m['record_id'],m['batch'],m['manifest_path'],m['shard_path']))
                metadata = {'version':VERSION,'fingerprint':fingerprint,'summary':summary,'equivalences':entries,
                            'source_proof_hashes':proofs,'ddinter_index_sha256':index_hash}
                for name,value in metadata.items():
                    db.execute('INSERT INTO u_metadata VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json',(name,dumps(value)))
                db.execute('INSERT OR IGNORE INTO u_builds VALUES(?,?,?)',(fingerprint,datetime.now(timezone.utc).isoformat(),dumps(summary)))
            if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok': raise ValueError('Processed SQLite integrity failure')
    configuration = {'schema_version':CONFIG_VERSION,'reference_kind':'unified_research_reference',
                     'database':str(database),'database_sha256':file_hash(database),'fingerprint':fingerprint,
                     'ddinter_scope':'official-all','ddinter_index':str(dataset.path),'ddinter_index_sha256':index_hash,
                     'sources':sources,'bulk_registry_imported':False,'clinical_verified':False,'regulatory_current_verified':False}
    if not config.exists() or read(config) != configuration: write(config,configuration)
    write(database.parent/'metadata.json',summary)
    if dav is not None: write(database.parent/'dav_audit.json',dav)
    return {'summary':summary,'records':records,'memberships':memberships,'mapper':mapper,'config':config,
            'database':database,'idempotent_no_change':unchanged,'records_upserted':upserted,'dav_audit':dav}

class UnifiedMedicationReference:
    """Indexed research adapter accepted directly by identify/assess_prescriptions."""
    def __init__(self, config):
        self.config_path = Path(config).resolve(); self.config = read(config)
        if self.config.get('schema_version') != CONFIG_VERSION: raise ValueError('Unsupported unified reference configuration')
        self.path = Path(self.config['database'])
        if not self.path.is_absolute(): self.path = self.config_path.parent/self.path
        if file_hash(self.path) != self.config['database_sha256']: raise ValueError('Processed reference hash mismatch')
        self.db = sqlite3.connect(self.path.resolve().as_uri()+'?mode=ro',uri=True); self.db.row_factory = sqlite3.Row
        try:
            self.metadata = {k:json.loads(v) for k,v in self.db.execute('SELECT key,value_json FROM u_metadata')}
            if self.metadata['version'] != VERSION or self.metadata['fingerprint'] != self.config['fingerprint']:
                raise ValueError('Processed reference version/fingerprint mismatch')
            for path, sha in self.metadata['source_proof_hashes'].items():
                if file_hash(path) != sha: raise ValueError('Retained source evidence hash mismatch')
        except Exception: self.db.close(); raise
        self.mapper = None

    def terminology(self,dataset=None):
        dataset = dataset or load_ddinter(PROJECT_ROOT,'official-all',index_path=Path(self.config['ddinter_index']))
        if not hasattr(dataset,'path') or file_hash(dataset.path) != self.config['ddinter_index_sha256']:
            raise ValueError('Unified research reference requires its recorded official DDInter index')
        self.mapper = DirectDDInter(dataset,self.metadata['equivalences']); return self.mapper

    def _generic_tokens(self, value):
        parsed = parse_ingredients(value)
        if parsed['status'] != 'PARSED' or not parsed['ingredients']: return None
        result = []
        for item in parsed['ingredients']:
            name = item['normalized_ingredient']; mapped = self.mapper.match(name)
            # A salt query is constrained to its literal source form. A parent name is
            # searchable, but distinct salts/presentations remain separate candidates.
            if mapped['mapping_status']=='VERIFIED' and mapped['match_method'] in ('EXACT_NORMALIZED_GENERIC','VERIFIED_SOURCE_SYNONYM'):
                result.append(('ingredient_id',mapped['ddinter_id']))
            else: result.append(('ingredient_raw',key(name)))
        return result

    def lookup(self, medication):
        if not isinstance(medication,dict): raise ValueError('Medication input must be an object')
        result = {'identification_status':'UNRESOLVED','lookup_method':'UNIFIED_INDEXED_RESEARCH',
                  'candidates':[],'suggestions':[],'issues':[],'current_authorization':'UNKNOWN',
                  'reference_kind':'unified_research_reference','identity_verification_scope':'source_supported_historical_product_facts_only',
                  'clinical_verified':False,'regulatory_current_verified':False}
        if medication.get('synthetic_fixture'): result['issues'].append('SYNTHETIC_INPUT_BLOCKED'); return result
        explicit_brand = medication.get('brand_name'); brand = explicit_brand or medication.get('name_raw')
        code = medication.get('source_product_code'); reg_raw = medication.get('registration_number')
        reg = registration(reg_raw) if reg_raw else None; generic = medication.get('generic_name')
        if reg_raw and not reg: result['issues'].append('REGISTRATION_UNREADABLE'); return result
        sql = 'SELECT r.*,o.original_json FROM u_records r JOIN u_observations o ON o.id=r.observation_id WHERE r.active=1 AND '
        tokens = None
        if code: rows = self.db.execute(sql+'r.source_code=?',(code,)).fetchall()
        elif reg: rows = self.db.execute(sql+'r.registration_key=?',(reg,)).fetchall()
        elif brand: rows = self.db.execute(sql+'r.brand_key=?',(brand_key(brand),)).fetchall()
        else: rows = []
        if generic is not None or (not rows and brand and not explicit_brand and not code and not reg):
            generic = generic if generic is not None else brand
            if self.mapper is None: self.terminology()
            tokens = self._generic_tokens(generic)
            if tokens:
                if not code and not reg and not explicit_brand:
                    kind, token = tokens[0]
                    rows = self.db.execute(sql+'r.id IN (SELECT record_id FROM u_names WHERE kind=? AND name_key=?)',(kind,token)).fetchall()
                result['lookup_method'] = 'UNIFIED_EXACT_GENERIC_COMPOSITION'
            else: result['issues'].append('GENERIC_COMPOSITION_REVIEW_REQUIRED'); return result
        if not (brand or code or reg or generic): result['issues'].append('BRAND_REGISTRATION_OR_GENERIC_REQUIRED'); return result
        groups = {}
        for row in rows:
            entry = json.loads(row['original_json']); product = entry['product']; n = json.loads(row['normalized_json'])
            quality = json.loads(row['quality_json']); parsed = json.loads(row['parsed_json']); mapped = json.loads(row['mappings_json'])
            if explicit_brand and brand_key(explicit_brand) != row['brand_key']: continue
            if brand and not tokens and brand_key(brand) != row['brand_key']: continue
            if reg and reg != row['registration_key']: continue
            if code and code != row['source_code']: continue
            checks = [('strength','strength_raw',strength_signature,product.get('strength')),
                      ('dosage_form','dosage_form_raw',normalized_form,product.get('dosage_form')),
                      ('manufacturer','manufacturer_raw',key,product.get('manufacturer')),
                      ('route','route_raw',key,product.get('route')),
                      ('source_labeler','source_labeler',key,product.get('source_labeler')),
                      ('source_presentation','source_presentation',key,product.get('source_presentation'))]
            if any((value:=medication.get(field) or medication.get(alternate)) and normalize(value)!=normalize(original)
                   for field,alternate,normalize,original in checks): continue
            if tokens:
                # Require the full composition; one matching component never selects a combination.
                wanted = set(tokens); available_raw = {key(i['normalized_ingredient']) for i in parsed['ingredients']}
                available_ids = {m['ddinter_id'] for m in mapped if m['mapping_status']=='VERIFIED'}
                if any((kind=='ingredient_raw' and token not in available_raw) or (kind=='ingredient_id' and token not in available_ids) for kind,token in tokens): continue
                covered = {i for i,(item,m) in enumerate(zip(parsed['ingredients'],mapped)) if
                           ('ingredient_raw',key(item['normalized_ingredient'])) in wanted or ('ingredient_id',m['ddinter_id']) in wanted}
                if len(covered) != len(parsed['ingredients']): continue
            cid = row['presentation_key']
            memberships = [dict(m) for m in self.db.execute('SELECT batch,manifest_path,shard_path FROM u_memberships WHERE record_id=? AND active=1',(row['id'],))]
            if cid not in groups:
                groups[cid] = {'candidate_key':cid,'product':deepcopy(product), 'registration_number':product.get('registration_number'),
                               'source_evidence':deepcopy(entry['source_evidence']),'synthetic_fixture':False,
                               'independent_review':deepcopy(entry['fact_review']),'ingestion_statuses':['PROCESSED_SUPPORTED_RESEARCH_FACTS'],
                               'registration_description_conflict':bool(row['identity_conflict']), 'current_authorization':'UNKNOWN',
                               'product_review_state':'SOURCE_SUPPORTED','clinical_verified':False,
                               'normalization':n,'data_quality':quality,'source_memberships':memberships,'source_record_ids':[row['id']]}
            else:
                groups[cid]['source_evidence'].extend(deepcopy(entry['source_evidence']))
                groups[cid]['source_memberships'].extend(memberships); groups[cid]['source_record_ids'].append(row['id'])
                groups[cid]['registration_description_conflict'] |= bool(row['identity_conflict'])
                groups[cid]['data_quality']['block_product_identity'] |= quality['block_product_identity']
        result['candidates'] = list(groups.values())
        if len(groups)>1: result.update(identification_status='REVIEW_REQUIRED',issues=['MULTIPLE_SOURCE_SUPPORTED_PRESENTATIONS'])
        elif groups:
            candidate = next(iter(groups.values()))
            if candidate['registration_description_conflict']: result.update(identification_status='REVIEW_REQUIRED',issues=['CONFLICTING_SOURCE_PRODUCT_IDENTITIES'])
            elif candidate['data_quality']['block_product_identity']: result.update(identification_status='REVIEW_REQUIRED',issues=['PRODUCT_DATA_QUALITY_REVIEW_REQUIRED'])
            else: result['identification_status']='VERIFIED'
        else: result['issues'].append('NO_CANDIDATE_SATISFIES_SUPPLIED_IDENTITY')
        return result

    def close(self): self.db.close()
