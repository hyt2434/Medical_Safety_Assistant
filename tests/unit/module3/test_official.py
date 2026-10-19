"""Offline regressions for actual official rows and clearly synthetic conflict evidence."""
from contextlib import closing
from copy import deepcopy
import csv
import json
from shared.paths import ProjectPath as Path, PROJECT_ROOT
import socket
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from shared.dav_import.common import file_hash
from module2_medications.terminology import DirectDDInter, load_ddinter
from module2_medications.service import assess_prescriptions
from module2_medications.reference import MedicationReference
from module3_interactions.engine import assess, HEADERS
from module3_interactions.official_ddinter.dataset import OfficialDataset, build_index
from module3_interactions.official_ddinter.acquire import statistics
from module3_interactions.official_ddinter.evaluate import FORM_CUE

ROOT = PROJECT_ROOT
COLLECTION = ROOT / 'data/reference/ddinter2/official_20261013'


def med(dataset, identifier, ordinal):
    entry = dataset.identities[identifier]
    return {'medication_id': f'synthetic-med-{ordinal}', 'prescription_ids': [f'synthetic-rx-{ordinal}'],
        'brand_name': 'Invented engineering product', 'identity_status': 'VERIFIED',
        'identity_evidence': [{'kind': 'synthetic_product_identity_fixture'}], 'source_kind': 'synthetic_fixture',
        'ingredients': [{'name': entry['name'], 'ddinter_id': identifier, 'mapping_status': 'VERIFIED',
                         'mapping_evidence': [entry['evidence']]}]}


class OfficialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.network = patch.object(socket, 'socket', side_effect=AssertionError('Offline tests forbid network'))
        cls.network.start()
        cls.dataset = load_ddinter(ROOT, 'official-all')
        cls.mapper = DirectDDInter(cls.dataset)

    @classmethod
    def tearDownClass(cls):
        cls.network.stop()

    def test_actual_collection_counts_and_partial(self):
        c = self.dataset.coverage
        self.assertEqual(c['loaded_rows'], 222383)
        self.assertEqual(c['unique_interaction_pairs'], 160235)
        self.assertEqual(c['identity_evidence_entries'], 1939)
        self.assertEqual(c['dataset_verdict'], 'PARTIAL')
        self.assertFalse(c['complete_database_loaded'])

    def test_original_filenames_provenance_and_reused_a(self):
        manifest = json.loads((COLLECTION / 'manifest.json').read_text())
        self.assertEqual({a['filename'].split('_')[-1][0] for a in manifest['artifacts']}, set('ABDHLPRV'))
        for a in manifest['artifacts']:
            self.assertEqual(file_hash(COLLECTION / a['filename']), a['sha256'])
            self.assertTrue(a['retrieved_at_utc'])
            self.assertEqual(a['license']['name'], 'CC BY-NC-SA 4.0')
        self.assertEqual(manifest['artifacts'][0]['acquisition'], 'reused_existing_original_bytes')

    def test_new_category_major_pairs(self):
        examples = {'B': ('DDInter582', 'DDInter725'), 'D': ('DDInter1008', 'DDInter7'),
                    'H': ('DDInter8', 'DDInter1398'), 'L': ('DDInter1', 'DDInter1033'),
                    'P': ('DDInter852', 'DDInter8'), 'R': ('DDInter884', 'DDInter8'),
                    'V': ('DDInter582', 'DDInter1785')}
        for category, ids in examples.items():
            with self.subTest(category=category):
                result = self.dataset.lookup(*ids)
                self.assertEqual(result['original_level'], 'Major')
                self.assertTrue(any(r['evidence']['filename'] == f'ddinter_downloads_code_{category}.csv'
                                    for r in result['source_records']))
                assessment = assess([med(self.dataset, ids[0], 1), med(self.dataset, ids[1], 2)], self.dataset)
                self.assertTrue(any(a['routing_priority'] == 'PROMPT' for a in assessment['review_alerts']))
                self.assertIsNone(assessment['safe_to_take'])
                self.assertTrue(assessment['requires_hcp_review'])

    def test_duplicate_rows_all_retained(self):
        with closing(sqlite3.connect(self.dataset.path)) as db:
            a, b, count = db.execute('SELECT low_id,high_id,count(*) FROM source_rows GROUP BY low_id,high_id HAVING count(*)>1 LIMIT 1').fetchone()
        self.assertEqual(len(self.dataset.lookup(a, b)['source_records']), count)
        self.assertEqual(self.dataset.coverage['duplicate_pair_occurrences'], 62148)

    def test_reversed_order_identical(self):
        self.assertEqual(self.dataset.lookup('DDInter582', 'DDInter725'), self.dataset.lookup('DDInter725', 'DDInter582'))

    def test_no_actual_conflicting_levels_or_ids(self):
        self.assertEqual(self.dataset.coverage['contradictory_severity_pairs'], 0)
        self.assertEqual(self.dataset.coverage['conflicting_identifier_names'], 0)

    def test_missing_pair_insufficient_evidence(self):
        result = self.dataset.lookup('DDInter1164', 'DDInter1679')
        self.assertEqual(result['status'], 'NO_RECORD_IN_LOADED_SUBSET')
        self.assertIsNone(result['safe'])

    def test_official_synonyms_and_salt_boundaries(self):
        self.assertEqual(self.mapper.match('Aspirin')['ddinter_id'], 'DDInter20')
        self.assertEqual(self.mapper.match('Aspirin')['match_method'], 'VERIFIED_SOURCE_SYNONYM')
        self.assertEqual(self.mapper.match('Paracetamol')['ddinter_id'], 'DDInter14')
        self.assertEqual(self.mapper.match('Metformin hydrochloride')['mapping_status'], 'UNRESOLVED')
        self.assertEqual(self.mapper.match('Vildagliptin')['mapping_status'], 'UNRESOLVED')

    def test_verified_new_dictionary_names(self):
        with closing(sqlite3.connect(self.dataset.path)) as db:
            identifier, name = db.execute("SELECT id_a,name_a FROM source_rows s WHERE NOT EXISTS ("
                "SELECT 1 FROM source_rows a WHERE a.filename='ddinter_downloads_code_A.csv' AND (a.id_a=s.id_a OR a.id_b=s.id_a)) LIMIT 1").fetchone()
        self.assertEqual(self.mapper.match(name)['ddinter_id'], identifier)

    def test_actual_cli_fixture_handoff(self):
        path = ROOT / 'data/reference/test_fixtures/module2_api_quicktest/medication_reference/private_runs/20261013_003/reference.sqlite'
        reference = MedicationReference(path, allow_synthetic=True)
        try:
            data = json.loads((ROOT / 'data/reference/provenance/module2_api_quicktest/medication_reference/examples/pipeline.synthetic.json').read_text())
            result = assess_prescriptions(data, reference, self.mapper)
        finally:
            reference.close()
        self.assertEqual(result['module3']['matched_interactions'][0]['original_level'], 'Major')
        self.assertEqual(result['module3']['checked_medication_pairs'][0]['prescription_ids'], ['synthetic-rx-1', 'synthetic-rx-2'])


class ConflictTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def build(self, rows_by_category, *, bad_header=False):
        artifacts = []
        for cat, rows in rows_by_category.items():
            filename = f'ddinter_downloads_code_{cat}.csv'
            p = self.folder / filename
            with p.open('w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=HEADERS if not bad_header else ['wrong'])
                writer.writeheader()
                if not bad_header:
                    writer.writerows(rows)
            artifacts.append({'filename': filename, 'sha256': file_hash(p), 'source_url': 'synthetic://' + filename})
        manifest = {'schema_version': 'ddinter.official_collection.v1', 'synthetic_fixture': True,
            'artifacts': artifacts, 'published_statistics': {'ddi_records': 100, 'drug_entries': 100, 'distinct_drugs': 100},
            'all_explicit_csv_hyperlinks_acquired': False, 'license': {'name': 'Synthetic engineering fixture'}}
        (self.folder / 'manifest.json').write_text(json.dumps(manifest))
        path = self.folder / 'index.sqlite'
        build_index(self.folder, path)
        return OfficialDataset(path)

    def row(self, level='Major', name='Abacavir'):
        return dict(zip(HEADERS, ('DDInter1', name, 'DDInter1263', 'Naltrexone', level)))

    def test_conflicting_severity_preserved_and_alerted(self):
        d = self.build({'A': [self.row()], 'B': [self.row('Minor')]})
        result = d.lookup('DDInter1', 'DDInter1263')
        self.assertEqual(result['status'], 'CONFLICTING_SOURCE_RECORDS')
        self.assertIsNone(result['original_level'])
        self.assertEqual(result['original_levels'], ['Major', 'Minor'])
        self.assertEqual(len(result['source_records']), 2)
        assessed = assess([med(d, 'DDInter1', 1), med(d, 'DDInter1263', 2)], d)
        self.assertTrue(any(a['kind'] == 'SOURCE_CONFLICT' and a['routing_priority'] == 'PROMPT' for a in assessed['review_alerts']))

    def test_identifier_conflict_not_mapped_or_assessed(self):
        d = self.build({'A': [self.row()], 'B': [self.row(name='Different ingredient')]})
        result = DirectDDInter(d).match('Abacavir')
        self.assertEqual(result['mapping_status'], 'REVIEW_REQUIRED')
        self.assertIsNone(result['ddinter_id'])
        assessed = assess([med(d, 'DDInter1', 1), med(d, 'DDInter1263', 2)], d)
        self.assertEqual(assessed['assessment_status'], 'INCOMPLETE_IDENTITIES')

    def test_duplicate_pair_count_distinct_from_source_rows(self):
        d = self.build({'A': [self.row()], 'B': [self.row()]})
        self.assertEqual(d.coverage['loaded_rows'], 2)
        self.assertEqual(d.coverage['unique_interaction_pairs'], 1)
        self.assertEqual(len(d.lookup('DDInter1', 'DDInter1263')['source_records']), 2)

    def test_unexpected_schema_refused(self):
        with self.assertRaisesRegex(ValueError, 'schema'):
            self.build({'A': []}, bad_header=True)

    def test_artifact_tamper_refused(self):
        d = self.build({'A': [self.row()]})
        with (self.folder / 'ddinter_downloads_code_A.csv').open('a') as f:
            f.write('tamper')
        with self.assertRaisesRegex(ValueError, 'CSV hash'):
            OfficialDataset(d.path)

    def test_index_tamper_refused(self):
        d = self.build({'A': [self.row()]})
        with closing(sqlite3.connect(d.path)) as db, db:
            db.execute("UPDATE source_rows SET level='Minor'")
        with self.assertRaisesRegex(ValueError, 'index schema/hash'):
            OfficialDataset(d.path)

    def test_unknown_label_preserved(self):
        d = self.build({'A': [self.row('Unknown')]})
        self.assertEqual(d.lookup('DDInter1', 'DDInter1263')['original_level'], 'Unknown')

    def test_published_statistics_definitions(self):
        result = statistics('2,310 approved drug entries, 2122 distinct drugs 302,516 DDI records')
        self.assertEqual(result, {'drug_entries': 2310, 'distinct_drugs': 2122, 'ddi_records': 302516})

    def test_salt_review_cues_do_not_confuse_hydrochlorothiazide_name(self):
        self.assertIsNone(FORM_CUE.search('Hydroclorothiazid'))
        self.assertTrue(FORM_CUE.search('Metformin hydrochloride'))
        self.assertTrue(FORM_CUE.search('Fexofenadin hydroclorid'))


if __name__ == '__main__':
    unittest.main()
