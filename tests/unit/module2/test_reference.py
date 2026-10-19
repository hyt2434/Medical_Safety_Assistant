"""Synthetic product facts and official terminology fixtures; networking is forbidden."""
from copy import deepcopy
import json
from shared.paths import ProjectPath as Path, PROJECT_ROOT
import socket
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from shared.dav_import.common import file_hash, digest
from module3_interactions.engine import BoundedDataset, load_existing_dataset
from module2_medications.audit import audit_dataset
from module2_medications.ingredients import parse_ingredients
from module2_medications.reference import (
    build_reference, MedicationReference, review_product, add_alias)
from module2_medications.service import identify, from_module1, assess_prescriptions
from module2_medications.terminology import DirectDDInter, load_ddinter
from module2_medications.fixtures import synthetic_rows, fixture_db

ROOT = PROJECT_ROOT
EVIDENCE = [{'locator': 'synthetic://independently-authored-test-expectation', 'sha256': '0'*64}]


class ParserTests(unittest.TestCase):
    def test_inline_single(self):
        p = parse_ingredients('Paracetamol 500 mg')
        self.assertEqual(p['ingredients'][0]['normalized_ingredient'], 'Paracetamol')
        self.assertEqual(p['ingredients'][0]['strength']['amount'], '500')

    def test_decimal_comma_and_combination(self):
        p = parse_ingredients('Paracetamol 0,5g, Dolutegravir 50mg')
        self.assertEqual(p['status'], 'PARSED')
        self.assertEqual(len(p['ingredients']), 2)
        self.assertEqual(p['ingredients'][0]['strength']['amount'], '500')

    def test_source_base_declaration_preserved(self):
        p = parse_ingredients('Sitagliptin (dưới dạng sitagliptin phosphate monohydrate 64,25mg) 50mg')
        self.assertEqual(p['ingredients'][0]['normalized_ingredient'], 'Sitagliptin')
        self.assertIn('64,25mg', p['ingredients'][0]['source_form_declaration'])

    def test_salt_is_not_stripped(self):
        self.assertEqual(parse_ingredients('Metformin hydrochloride')['ingredients'][0]['normalized_ingredient'],
                         'Metformin hydrochloride')

    def test_slash_ambiguous_no_component_removed(self):
        p = parse_ingredients('Paracetamol/Dolutegravir')
        self.assertEqual(p['status'], 'REVIEW_REQUIRED')
        self.assertIn('Dolutegravir', p['ingredients'][0]['normalized_ingredient'])

    def test_unbalanced(self):
        self.assertEqual(parse_ingredients('Paracetamol (salt')['status'], 'REVIEW_REQUIRED')

    def test_missing(self):
        self.assertEqual(parse_ingredients(None)['status'], 'UNRESOLVED')

    def test_strength_conflict(self):
        self.assertEqual(parse_ingredients('Paracetamol 500mg', '250mg')['status'], 'REVIEW_REQUIRED')

    def test_missing_strength_does_not_destroy_ingredient(self):
        p = parse_ingredients('Paracetamol')
        self.assertEqual(p['status'], 'PARSED')
        self.assertIn('STRENGTH_MISSING_OR_UNRESOLVED', p['issues'])

    def test_concentration(self):
        p = parse_ingredients('Semaglutide', '1,34mg/ml')
        self.assertEqual(p['ingredients'][0]['strength']['denominator_unit'], 'mL')

    def test_structured_combo_and_units(self):
        p = parse_ingredients([{'name': 'Paracetamol', 'strength': '0.5g'},
                               {'name': 'Dolutegravir', 'strength': '50000mcg'}])
        self.assertEqual([x['strength']['amount'] for x in p['ingredients']], ['500', '50'])

    def test_duplicate_and_descriptive_comma(self):
        self.assertEqual(parse_ingredients('Paracetamol; Paracetamol')['status'], 'REVIEW_REQUIRED')
        self.assertEqual(parse_ingredients('estradiol, micronized 0,5mg')['status'], 'REVIEW_REQUIRED')


class ReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.network = patch.object(socket, 'socket', side_effect=AssertionError('Network disabled'))
        cls.network.start()
        cls.dataset = load_existing_dataset(ROOT)
        cls.terminology = DirectDDInter(cls.dataset)

    @classmethod
    def tearDownClass(cls):
        cls.network.stop()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db, self.source, self.manifest = fixture_db(self.temp.name)
        self.reference = MedicationReference(self.db, allow_synthetic=True)

    def tearDown(self):
        self.reference.close()
        self.temp.cleanup()

    def query(self, brand, **extra):
        return {'brand_name': brand, 'synthetic_fixture': True,
                'transcription_status': 'USER_CONFIRMED_TRANSCRIPTION', **extra}

    def reviewed(self, brand, **extra):
        q = self.query(brand, **extra)
        c = self.reference.lookup(q)['candidates'][0]['candidate_key']
        review_product(self.db, c, status='VERIFIED', reviewer='Synthetic test adjudication', evidence=EVIDENCE)
        return q

    def test_ambiguous_brand(self):
        r = self.reference.lookup(self.query('Fixture Para'))
        self.assertEqual(r['identification_status'], 'REVIEW_REQUIRED')
        self.assertEqual(len(r['candidates']), 2)

    def test_strength_equivalence_and_punctuation(self):
        r = self.reference.lookup(self.query('FIXTURE-PARA', strength='0,5g'))
        self.assertEqual(len(r['candidates']), 1)
        self.assertEqual(r['candidates'][0]['registration_number'], 'VD-100-26')

    def test_registration_qualifier_conflict(self):
        r = self.reference.lookup(self.query('Fixture Para', registration_number='VD-100-26', strength='1g'))
        self.assertEqual(r['candidates'], [])

    def test_registration_annotations(self):
        r = self.reference.lookup(self.query('Fixture Para', registration_number='VD-100-26 (Hiệu lực)', strength='500mg'))
        self.assertEqual(len(r['candidates']), 1)
        self.assertEqual(r['current_authorization'], 'UNKNOWN')

    def test_inline_strength_disambiguates(self):
        r = self.reference.lookup(self.query('Fixture Inline', strength='10mg'))
        self.assertEqual(len(r['candidates']), 1)
        self.assertEqual(r['candidates'][0]['registration_number'], 'VD-107-26')

    def test_missing_strength_unique_is_candidate(self):
        r = identify(self.query('Fixture Missing'), self.reference, self.terminology)
        self.assertEqual(r['ingredients'][0]['ddinter_id'], 'DDInter14')
        self.assertEqual(r['identification_status'], 'REVIEW_REQUIRED')

    def test_fuzzy_suggestions_never_identify(self):
        r = self.reference.lookup(self.query('Fixture Parra'))
        self.assertEqual(r['identification_status'], 'UNRESOLVED')
        self.assertTrue(r['suggestions'])
        self.assertEqual(r['candidates'], [])

    def test_unicode_composition_accents_retained(self):
        import unicodedata
        self.assertEqual(len(self.reference.lookup(self.query(unicodedata.normalize('NFD', 'Thuốc Thử')))['candidates']), 1)
        self.assertEqual(self.reference.lookup(self.query('Thuoc Thu'))['candidates'], [])

    def test_form_manufacturer_constraints(self):
        self.assertEqual(self.reference.lookup(self.query('Fixture Missing', dosage_form='injection'))['candidates'], [])
        self.assertEqual(self.reference.lookup(self.query('Fixture Missing', manufacturer='Other'))['candidates'], [])

    def test_verified_alias(self):
        c = self.reference.lookup(self.query('Fixture Missing'))['candidates'][0]['candidate_key']
        add_alias(self.db, 'Fixture Known Alias', c, reviewer='Synthetic test', evidence=EVIDENCE)
        self.assertEqual(self.reference.lookup(self.query('Fixture Known Alias'))['lookup_method'], 'VERIFIED_ALIAS')

    def test_real_input_cannot_use_synthetic_products(self):
        self.assertEqual(self.reference.lookup({'brand_name': 'Fixture Missing'})['candidates'], [])

    def test_unknown_mapping_remains_unresolved(self):
        r = identify(self.query('Fixture Unknown'), self.reference, self.terminology)
        self.assertEqual(r['ingredients'][0]['mapping_status'], 'UNRESOLVED')
        self.assertEqual(r['verified_ddinter_ids'], [])

    def test_verified_synonym_direct_without_rxnorm(self):
        r = identify(self.reviewed('Fixture Para', strength='500mg'), self.reference, self.terminology)
        self.assertEqual(r['ingredients'][0]['ddinter_generic_name'], 'Acetaminophen')
        self.assertEqual(r['ingredients'][0]['match_method'], 'VERIFIED_SOURCE_SYNONYM')
        self.assertTrue(r['ready_for_identifier_handoff'])
        self.assertNotIn('rxnorm', json.dumps(r).lower())

    def test_product_review_separate_from_mapping(self):
        r = identify(self.query('Fixture Para', strength='500mg'), self.reference, self.terminology)
        self.assertEqual(r['mapping_status'], 'VERIFIED')
        self.assertEqual(r['identification_status'], 'REVIEW_REQUIRED')
        self.assertFalse(r['ready_for_identifier_handoff'])

    def test_combination_preserves_all_components(self):
        r = identify(self.reviewed('Fixture Combination'), self.reference, self.terminology)
        self.assertEqual(r['verified_ddinter_ids'], ['DDInter14', 'DDInter582'])
        self.assertTrue(r['ready_for_identifier_handoff'])

    def test_conflicting_history_remains_review(self):
        r = identify(self.reviewed('Fixture Conflict', strength='500mg'), self.reference, self.terminology)
        self.assertEqual(r['identification_status'], 'REVIEW_REQUIRED')
        self.assertIn('CONFLICTING_REGISTRATION_OBSERVATIONS', r['issues'])

    def test_major_warning_end_to_end(self):
        meds = [self.reviewed('Fixture Dolutegravir'), self.reviewed('Fixture Antacid')]
        r = assess_prescriptions({'medications': meds}, self.reference, self.terminology)
        self.assertEqual(r['module3']['matched_interactions'][0]['original_level'], 'Major')
        self.assertTrue(any(a['routing_priority'] == 'PROMPT' for a in r['module3']['review_alerts']))
        self.assertIsNone(r['module3']['safe_to_take'])
        self.assertTrue(r['module3']['requires_hcp_review'])

    def test_multiple_prescriptions_preserve_context(self):
        extraction = {'prescriptions': [
            {'prescription_id': 'rx-left', 'medications': [self.reviewed('Fixture Dolutegravir')]},
            {'prescription_id': 'rx-right', 'medications': [self.reviewed('Fixture Antacid')]}]}
        r = assess_prescriptions(extraction, self.reference, self.terminology)
        self.assertEqual(r['module3']['checked_medication_pairs'][0]['prescription_ids'], ['rx-left', 'rx-right'])
        self.assertEqual(r['module3']['matched_interactions'][0]['original_level'], 'Major')

    def test_invalid_prescription_context_rejected(self):
        with self.assertRaises(ValueError):
            from_module1({'prescriptions': [{'prescription_id': '', 'medications': []}]}, self.reference, self.terminology)

    def test_rejected_review_does_not_verify_product(self):
        q = self.query('Fixture Missing')
        cid = self.reference.lookup(q)['candidates'][0]['candidate_key']
        review_product(self.db, cid, status='REJECTED', reviewer='Synthetic case reviewer', evidence=EVIDENCE)
        self.assertFalse(identify(q, self.reference, self.terminology)['ready_for_identifier_handoff'])

    def test_absent_pair_not_safe(self):
        meds = [self.reviewed('Fixture Para', strength='500mg'), self.reviewed('Fixture Dolutegravir')]
        r = assess_prescriptions({'medications': meds}, self.reference, self.terminology)['module3']
        self.assertEqual(r['checked_ingredient_pairs'][0]['status'], 'NO_RECORD_IN_LOADED_SUBSET')
        self.assertIsNone(r['safe_to_take'])

    def test_transcription_confirmation_not_identity_review(self):
        r = from_module1({'medications': [self.query('Fixture Missing')]}, self.reference, self.terminology, confirmed=True)
        self.assertEqual(r[0]['identification_status'], 'REVIEW_REQUIRED')

    def test_module1_uncertainty_blocks_reviewed_product(self):
        q = self.reviewed('Fixture Missing')
        q['uncertain_fields'] = ['name_raw']
        r = from_module1({'medications': [q]}, self.reference, self.terminology, confirmed=True)
        self.assertFalse(r[0]['ready_for_identifier_handoff'])

    def test_unknown_and_ambiguous_not_silently_dropped(self):
        r = assess_prescriptions({'medications': [self.reviewed('Fixture Dolutegravir'), self.query('Fixture Unknown'),
            self.query('Fixture Para')]}, self.reference, self.terminology)['module3']
        self.assertEqual(len(r['checked_medication_pairs']), 3)
        self.assertTrue(r['unresolved_mappings'])

    def test_unsupported_combo_blocks_product(self):
        r = identify(self.reviewed('Fixture Slash'), self.reference, self.terminology)
        self.assertFalse(r['ready_for_identifier_handoff'])

    def test_raw_immutable_and_import_idempotent(self):
        before = file_hash(self.source)
        built = build_reference(self.source, self.manifest, self.db, as_of='2026-10-13')
        self.assertEqual(built['observations'], len(synthetic_rows()))
        self.assertEqual(file_hash(self.source), before)

    def test_pending_real_grant_rejected_before_creating_db(self):
        manifest = json.loads(self.manifest.read_text())
        manifest.update(source_kind='dav', synthetic_fixture=False,
                        source_url='https://dav.gov.vn', acquisition_method='approved_file_export')
        manifest['authorization'] = {'status': 'PENDING'}
        pending = Path(self.temp.name) / 'pending.json'
        pending.write_text(json.dumps(manifest))
        target = Path(self.temp.name) / 'forbidden.sqlite'
        with self.assertRaisesRegex(ValueError, 'authorization'):
            build_reference(self.source, pending, target, as_of='2026-10-13')
        self.assertFalse(target.exists())

    def test_review_needs_hash_linked_evidence(self):
        with self.assertRaises(ValueError):
            review_product(self.db, 'missing', status='VERIFIED', reviewer='Test', evidence=['assertion'])

    def test_vietnamese_export_headers_reuse_canonicalization(self):
        row = {'Tên thuốc': 'Fixture Vietnamese Export', 'Số đăng ký': 'VD-200-26',
               'Hoạt chất': 'Paracetamol', 'Hàm lượng': '500mg', 'Dạng bào chế': 'Viên nén',
               'Cơ sở sản xuất': 'Synthetic Manufacturer', 'synthetic_fixture': True}
        self.import_extra(row, 'vietnamese')
        r = identify(self.query('Fixture Vietnamese Export'), self.reference, self.terminology)
        self.assertEqual(r['ingredients'][0]['ddinter_id'], 'DDInter14')

    def test_ingestion_quarantine_cannot_be_promoted(self):
        row = {**synthetic_rows()[0], 'brand_name': 'Fixture Quarantine', 'registration_number': 'VD-201-26', 'manufacturer': ''}
        self.import_extra(row, 'quarantine')
        q = self.reviewed('Fixture Quarantine')
        r = identify(q, self.reference, self.terminology)
        self.assertFalse(r['ready_for_identifier_handoff'])
        self.assertIn('SOURCE_OBSERVATION_QUARANTINED', r['issues'])

    def import_extra(self, row, name):
        source = Path(self.temp.name) / (name + '.jsonl')
        source.write_text(json.dumps(row, ensure_ascii=False) + '\n', encoding='utf-8')
        manifest = json.loads(self.manifest.read_text())
        manifest.update(artifact_sha256=file_hash(source), expected_records=1)
        path = Path(self.temp.name) / (name + '.manifest.json')
        path.write_text(json.dumps(manifest), encoding='utf-8')
        build_reference(source, path, self.db, as_of='2026-10-13')


class DictionaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset = load_ddinter(ROOT, 'category-a')
        cls.mapper = DirectDDInter(cls.dataset)

    def test_actual_category_scope(self):
        self.assertEqual(self.dataset.coverage['loaded_rows'], 56367)
        self.assertEqual(len(self.dataset.identities), 1757)
        self.assertFalse(self.dataset.coverage['complete_database_loaded'])

    def test_default_still_bounded(self):
        self.assertEqual(load_ddinter(ROOT).coverage['loaded_rows'], 10)

    def test_diabetes_exact_dictionary_not_fuzzy(self):
        for name in ('Metformin', 'Sitagliptin', 'Empagliflozin', 'Dapagliflozin', 'Linagliptin', 'Glimepiride'):
            self.assertEqual(self.mapper.match(name)['mapping_status'], 'VERIFIED')
        self.assertEqual(self.mapper.match('Metforminn')['mapping_status'], 'UNRESOLVED')
        self.assertEqual(self.mapper.match('Metformin hydrochloride')['mapping_status'], 'UNRESOLVED')
        self.assertEqual(self.mapper.match('Vildagliptin')['mapping_status'], 'UNRESOLVED')

    def test_salt_equivalence_requires_explicit_review(self):
        with self.assertRaises(ValueError):
            DirectDDInter(self.dataset, [{'source_name': 'Metformin hydrochloride', 'ddinter_id': 'DDInter1164'}])

    def test_equivalence_is_cached_and_traceable(self):
        entry = {'source_name': 'Synthetic equivalent spelling', 'ddinter_id': 'DDInter1164', 'status': 'VERIFIED',
                 'reviewer': 'Synthetic engineering adjudication', 'reviewed_at': '2026-10-13', 'evidence': EVIDENCE}
        m = DirectDDInter(self.dataset, [entry])
        r = m.match(entry['source_name'])
        self.assertEqual(r['match_method'], 'REVIEWED_TERMINOLOGY_EQUIVALENCE')
        r['evidence'].clear()
        self.assertTrue(m.match(entry['source_name'])['evidence'])

    def test_ambiguous_synonyms_not_assigned(self):
        d = deepcopy(self.dataset)
        d.identities['DDInter14']['synonyms'] = ['conflicting name']
        d.identities['DDInter1164']['synonyms'] = ['conflicting name']
        self.assertEqual(DirectDDInter(d).match('conflicting name')['mapping_status'], 'REVIEW_REQUIRED')

    def test_default_constructor_refuses_full_rows(self):
        rows = [r['raw_source_row'] for values in self.dataset.records.values() for r in values]
        with self.assertRaises(ValueError):
            BoundedDataset(rows, self.dataset.coverage)

    def test_crosswalk_has_source_evidence(self):
        c = self.mapper.crosswalk()
        self.assertEqual(len(c['entries']), 1757)
        self.assertTrue(all(e['evidence'] for e in c['entries']))


class AuditTests(unittest.TestCase):
    def test_strict_json_and_locators(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / 'input.jsonl'
            p.write_text('{"brand_name":"A","brand_name":"B"}\n{"brand_name":NaN}\n[]\n', encoding='utf-8')
            r = audit_dataset(p, DirectDDInter(load_existing_dataset(ROOT)), as_of='2026-10-13')
            self.assertEqual(r['counts']['invalid_source_observations'], 3)

    def test_review_queue_contains_brand_and_registration_ambiguity(self):
        with tempfile.TemporaryDirectory() as temp:
            rows = synthetic_rows()[:2] + [deepcopy(synthetic_rows()[0])]
            rows[-1]['ingredients'] = 'Dolutegravir'
            for index, row in enumerate(rows, 1):
                fields = {k: v for k, v in row.items() if k != 'verification_status'}
                row['_source_cells'] = []
                row['_source'] = {'source_url': 'https://06dichvucong.dav.gov.vn/congbothuoc/index',
                    'captured_at': '2026-10-13T00:00:00Z', 'page': 1, 'ordinal': index,
                    'raw_page_filename': 'page_00001.json',
                    'row_sha256': digest({'fields': fields, 'cells': [], 'verification_status': 'REVIEW_REQUIRED'})}
            source, queue = Path(temp) / 'input.jsonl', Path(temp) / 'queue.jsonl'
            source.write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in rows), encoding='utf-8')
            result = audit_dataset(source, DirectDDInter(load_existing_dataset(ROOT)), as_of='2026-10-13', review_queue=queue)
            items = [json.loads(line) for line in queue.read_text().splitlines()]
            self.assertEqual(result['counts']['brand_ambiguous_observations'], 3)
            self.assertEqual(result['counts']['registration_conflicting_observations'], 2)
            self.assertIn('BRAND_HAS_MULTIPLE_PRODUCT_CANDIDATES', items[0]['reasons'])
            self.assertIn('CONFLICTING_REGISTRATION_OBSERVATIONS', items[0]['reasons'])
            self.assertNotIn('Fixture Para', queue.read_text())


if __name__ == '__main__':
    unittest.main()
