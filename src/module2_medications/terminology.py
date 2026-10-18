"""Exact identity crosswalk using already-downloaded official evidence only."""
from collections import defaultdict
from copy import deepcopy
from datetime import date
import csv
import json
import re
from shared.paths import ProjectPath as Path, PROJECT_ROOT
from shared.dav_import.common import file_hash, digest
from module3_interactions.engine import BoundedDataset, HEADERS, SOURCE, load_existing_dataset
from .text import key


def load_ddinter(project_root, scope='bounded', *, index_path=None):
    if scope == 'bounded':
        return load_existing_dataset(project_root)
    if scope == 'official-all':
        from module3_interactions.official_ddinter.dataset import OfficialDataset
        return OfficialDataset(index_path or Path(project_root) / 'data/reference/ddinter2/official_20261013/official.sqlite')
    if scope != 'category-a':
        raise ValueError('Use bounded, category-a or official-all; coverage remains explicit')
    # This task explicitly processes the existing local file. No additional download.
    folder = Path(project_root) / 'data/reference/provenance/module2_api_quicktest/ingredient_ddinter_poc/evidence'
    manifest = json.loads((folder / 'approved_download_manifest.json').read_text(encoding='utf-8-sig'))
    source = folder / 'ddinter_downloads_code_A.csv'
    sha = file_hash(source)
    if manifest['source_url'] != SOURCE or sha != manifest['sha256'].lower():
        raise ValueError('Local DDInter artifact identity/hash mismatch')
    with source.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != HEADERS:
            raise ValueError('Unexpected DDInter endpoint CSV schema')
        rows = list(reader)
    # Existing default loader and its ten-row scope remain unchanged.
    additional = load_existing_dataset(project_root).identities
    coverage = {'source_url': SOURCE, 'csv_sha256': sha, 'loaded_rows': len(rows),
        'scope': 'complete existing category-A interaction CSV only; partial DDInter dictionary',
        'complete_database_loaded': False, 'file_release_version_independently_verified': False,
        'advertised_source': 'DDInter 2.0 official download; exact file release unverified',
        'license': 'CC BY-NC-SA 4.0', 'license_url': 'https://ddinter2.scbdd.com/terms/',
        'synthetic_fixture': False, 'processing_context': 'current Module 2 task, local scholarly evaluation'}
    return BoundedDataset(rows, coverage, additional, row_limit=len(rows))


class DirectDDInter:
    """Cached exact, official synonym and explicitly reviewed equivalence lookup."""
    def __init__(self, dataset, equivalences=()):
        equivalences = list(equivalences)
        self.dataset = dataset
        self.exact = defaultdict(set)
        self.synonyms = defaultdict(set)
        self.equivalences = defaultdict(list)
        self.conflicted_names = defaultdict(set)
        self.cache = {}
        for identifier, entry in dataset.identities.items():
            if entry.get('identity_status') == 'REVIEW_REQUIRED':
                for candidate in entry.get('name_candidates', [entry['name']]):
                    self.conflicted_names[key(candidate)].add(identifier)
                continue
            self.exact[key(entry['name'])].add(identifier)
            for synonym in entry.get('synonyms', []):
                self.synonyms[key(synonym)].add(identifier)
        for entry in equivalences:
            if (entry.get('status') != 'VERIFIED' or not entry.get('reviewer') or
                    not entry.get('reviewed_at') or not entry.get('evidence') or
                    entry.get('ddinter_id') not in dataset.identities or not entry.get('source_name')):
                raise ValueError('Equivalence requires reviewed source/target evidence, reviewer and date')
            if dataset.identities[entry['ddinter_id']].get('identity_status') == 'REVIEW_REQUIRED':
                raise ValueError('Equivalence cannot promote a conflicting source identifier')
            date.fromisoformat(entry['reviewed_at'][:10])
            proof = entry['evidence']
            if not isinstance(proof, list) or any(not isinstance(e, dict) or not e.get('locator')
                    or not re.fullmatch(r'[0-9a-f]{64}', e.get('sha256', '')) for e in proof):
                raise ValueError('Equivalence evidence requires artifact SHA-256 values and source locators')
            self.equivalences[key(entry['source_name'])].append(deepcopy(entry))
        self.signature = digest({'identities': dataset.identities, 'equivalences': equivalences})

    def match(self, name):
        normalized = key(name)
        if normalized in self.cache:
            return deepcopy(self.cache[normalized])
        result = {'original_ingredient': name, 'normalized_ingredient': name,
            'ddinter_generic_name': None, 'ddinter_id': None, 'mapping_status': 'UNRESOLVED',
            'match_method': None, 'evidence': [], 'unresolved_reason': 'NO_MATCH_IN_LOADED_DICTIONARY',
            'coverage_scope': self.dataset.coverage['scope'], 'candidate_ddinter_ids': [],
            'verification_scope': 'terminology_identity_only; not DAV product or clinical verification'}
        equivalent = self.equivalences.get(normalized, [])
        ids, method = self.exact.get(normalized, set()), 'EXACT_NORMALIZED_GENERIC'
        if not ids:
            ids, method = self.synonyms.get(normalized, set()), 'VERIFIED_SOURCE_SYNONYM'
        if not ids:
            ids, method = {x['ddinter_id'] for x in equivalent}, 'REVIEWED_TERMINOLOGY_EQUIVALENCE'
        if self.conflicted_names.get(normalized):
            result.update(mapping_status='REVIEW_REQUIRED', unresolved_reason='CONFLICTING_SOURCE_IDENTIFIER_NAMES',
                          candidate_ddinter_ids=sorted(set(ids) | self.conflicted_names[normalized]))
            self.cache[normalized] = deepcopy(result)
            return result
        result['candidate_ddinter_ids'] = sorted(ids)
        if len(ids) > 1:
            result.update(mapping_status='REVIEW_REQUIRED', unresolved_reason='AMBIGUOUS_DDINTER_IDENTITY')
        elif ids:
            identifier = next(iter(ids))
            entry = self.dataset.identities[identifier]
            result.update(ddinter_id=identifier, ddinter_generic_name=entry['name'],
                mapping_status='VERIFIED', match_method=method, unresolved_reason=None,
                evidence=[deepcopy(entry['evidence'])])
            if method == 'REVIEWED_TERMINOLOGY_EQUIVALENCE':
                result['evidence'].extend(deepcopy(equivalent))
        self.cache[normalized] = deepcopy(result)
        return result

    def crosswalk(self):
        return {'schema_version': 'module2.direct_crosswalk.v1', 'sha256': self.signature,
            'coverage': deepcopy(self.dataset.coverage), 'entries': [
                {'ddinter_id': identifier, 'ddinter_generic_name': entry['name'],
                 'identity_status': entry.get('identity_status', 'VERIFIED'),
                 'verified_synonyms': entry.get('synonyms', []), 'evidence': entry['evidence']}
                for identifier, entry in sorted(self.dataset.identities.items())],
            'reviewed_equivalences': [e for values in self.equivalences.values() for e in values]}
