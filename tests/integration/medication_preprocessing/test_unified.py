"""Source fidelity, conservative matching, provenance and incremental regressions."""
from .common import *
from module2_medications.unified import validate_product
from copy import deepcopy
import tempfile
import unittest

class UnifiedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset = load_ddinter(PROJECT,'official-all')
        cls.reference = UnifiedMedicationReference(default_config(PROJECT)); cls.mapper = cls.reference.terminology(cls.dataset)
        cls.legacy = ResearchSupplementReference(discover_sources(PROJECT)[-1]); cls.old_mapper = cls.legacy.terminology(cls.dataset)
        cls.products = [e['product'] for e in cls.legacy.products]

    @classmethod
    def tearDownClass(cls): cls.reference.close(); cls.legacy.close()

    def product(self,name):
        return next(p for p in self.products if key(p['brand_name'])==key(name) or p.get('source_search_priority')==name)

    def result(self,p,**changes):
        return identify(canonical_query(p,transcription_status='VERIFIED',**changes),self.reference,self.mapper)

    def test_every_native_source_presentation_component_and_mapping_is_preserved(self):
        for p in self.products:
            with self.subTest(code=p['source_product_code']):
                q = native_query(p,transcription_status='VERIFIED')
                before = identify(q,self.legacy,self.old_mapper); after = identify(q,self.reference,self.mapper)
                self.assertEqual(after['identified_candidate']['product'],p)
                self.assertEqual(after['identification_status'],before['identification_status'])
                self.assertEqual(after['ingredients'],before['ingredients'])
                self.assertEqual(after['ready_for_identifier_handoff'],before['ready_for_identifier_handoff'])
                self.assertEqual(after['identified_candidate']['source_evidence'],before['identified_candidate']['source_evidence'])
                self.assertFalse(after['clinical_verified']); self.assertFalse(after['regulatory_current_verified'])

    def test_canonical_queries_preserve_every_source_product_and_component(self):
        for p in self.products:
            r = self.result(p)
            self.assertEqual(r['identified_candidate']['product'],p,p['source_product_code'])
            self.assertTrue(r['identified_candidate']['data_quality']['component_count_preserved'])

    def test_generic_lookup_without_brand_or_source_code(self):
        p = self.product('ZOLOFT')
        r = self.result(p,brand_name=None,source_product_code=None,generic_name='Sertraline')
        self.assertEqual(r['identification_status'],'VERIFIED')
        self.assertEqual(r['identified_candidate']['product']['source_product_code'],p['source_product_code'])
        self.assertEqual(r['verified_ddinter_ids'],[self.mapper.match('Sertraline')['ddinter_id']])

    def test_generic_query_requires_full_combination_and_literal_salt(self):
        p = self.product('JANUMET')
        good = self.result(p,brand_name=None,generic_name='Metformin + Sitagliptin')
        self.assertEqual(good['identification_status'],'VERIFIED'); self.assertEqual(len(good['ingredients']),2)
        partial = self.result(p,brand_name=None,generic_name='Metformin')
        self.assertEqual(partial['identification_status'],'UNRESOLVED')
        zoloft = self.product('ZOLOFT')
        self.assertEqual(self.result(zoloft,brand_name=None,generic_name='Sertraline hydrochloride')['identification_status'],'VERIFIED')
        self.assertEqual(self.result(zoloft,brand_name=None,generic_name='Unknown sertraline salt')['identification_status'],'UNRESOLVED')

    def test_equivalent_units_whitespace_case_and_explicit_separators(self):
        p = self.product('ZOLOFT')
        self.assertEqual(self.result(p,strength='0.025 g',brand_name='  zOlOfT  ')['identification_status'],'VERIFIED')
        combo = self.product('SYMBICORT')
        self.assertEqual(self.result(combo,strength=combo['strength'].replace(' + ','; '))['identification_status'],'VERIFIED')
        self.assertEqual(strength_signature('1000 mg'),strength_signature('1 g'))
        self.assertNotEqual(strength_signature('10 mg/mL'),strength_signature('10 mg'))

    def test_strength_release_route_manufacturer_and_registration_constraints(self):
        p = self.product('ZOLOFT')
        for changes in ({'strength':'999 mg'},{'dosage_form':'tablet, extended release'}, {'route':'oral'},
                        {'manufacturer':'Invented manufacturer'},{'registration_number':'VD-99999-26'},
                        {'source_product_code':'UNKNOWN'}):
            self.assertEqual(self.result(p,**changes)['identification_status'],'UNRESOLVED')

    def test_insulin_devices_and_concentrations_never_merge(self):
        p = self.product('RYZODEG')
        r = self.result(p,source_product_code=None)
        self.assertEqual(r['identification_status'],'REVIEW_REQUIRED'); self.assertEqual(len(r['candidates']),2)
        selected = self.result(p,source_product_code=None,source_presentation=p['source_presentation'])
        self.assertEqual(selected['identification_status'],'VERIFIED')
        self.assertEqual(len(selected['ingredients']),2)
        self.assertTrue(all(not i['strength_raw'] for i in selected['ingredients']))
        self.assertIsNone(selected['identified_candidate']['product']['premix_ratio'])
        lantus = self.product('LANTUS'); other = deepcopy(lantus); other['strength']='300 IU/mL'
        other['ingredients'][0]['strength']='300 IU/mL'
        self.assertNotEqual(normalize_product(lantus)[0]['presentation_key'],normalize_product(other)[0]['presentation_key'])

    def test_salts_are_not_collapsed_in_product_inventory(self):
        p = self.product('ZOLOFT'); parent = deepcopy(p)
        parent['ingredients'][0]['name']='SERTRALINE'
        self.assertNotEqual(normalize_product(p)[0]['product_key'],normalize_product(parent)[0]['product_key'])

    def test_missing_and_invalid_fields_are_visible_without_losing_source_text(self):
        p = deepcopy(self.product('JANUMET')); p['dosage_form']=None
        normalized,parsed = normalize_product(p); quality = validate_product(p,parsed)
        self.assertTrue(quality['block_product_identity']); self.assertIn('dosage_form',quality['missing_fields'])
        self.assertEqual(parsed['original_text'],p['ingredients'])
        p['ingredients'][0]['strength']='0 mg'; normalized,parsed = normalize_product(p)
        self.assertIn('COMPONENT_STRENGTH_REVIEW',validate_product(p,parsed)['issues'])

    def test_unknown_and_unconfirmed_and_uncertain_transcription_stay_unassessed(self):
        p = self.product('ZOLOFT')
        for q in ({'brand_name':'UNREADABLE MEDICATION'},canonical_query(p),canonical_query(p,uncertain_fields=['ingredients'])):
            r = assess_prescriptions({'medications':[q]},self.reference,self.mapper)
            self.assertFalse(r['module2'][0]['ready_for_identifier_handoff'])
            self.assertTrue(r['module3']['unresolved_mappings']); self.assertIsNone(r['module3']['safe_to_take'])
        self.assertEqual(self.result(p,synthetic_fixture=True)['identification_status'],'UNRESOLVED')

    def test_unresolved_ingredient_ids_are_not_filled_by_similarity(self):
        for name in ('Tirzepatide','Gliclazide','Vildagliptin','Metformin hydroclorid','Candesartan cilexetil',
                     'Dabigatran etexilate mesylate','Ferrous sulfate'):
            self.assertIsNone(self.mapper.match(name)['ddinter_id'])

    def test_repeated_memberships_share_records_and_keep_all_provenance(self):
        p = self.product('LANTUS'); r = self.result(p)
        memberships = r['identified_candidate']['source_memberships']
        self.assertEqual({m['batch'] for m in memberships},{1,3})
        self.assertEqual(len(r['identified_candidate']['source_record_ids']),1)
        self.assertEqual(self.reference.metadata['summary']['duplicates']['repeated_source_memberships'],243)

    def test_processed_hash_tampering_and_incompatible_dictionary_are_rejected(self):
        with tempfile.TemporaryDirectory(dir=DOCS) as folder:
            path = Path(folder)/'config.json'; cfg = read(default_config(PROJECT)); cfg['database_sha256']='0'*64
            write(path,cfg)
            with self.assertRaisesRegex(ValueError,'hash mismatch'): UnifiedMedicationReference(path)
        with self.assertRaisesRegex(ValueError,'recorded official DDInter'):
            self.reference.terminology(load_ddinter(PROJECT,'bounded'))

    def test_incremental_idempotent_update_and_failed_evidence_keep_existing_reference(self):
        with tempfile.TemporaryDirectory(dir=DOCS) as folder:
            folder = Path(folder); manifest = discover_sources(PROJECT)[0]; source = read(manifest)
            shards = source['shards'][:2]
            artifact = deepcopy(source); artifact['shards']=[dict(shards[0],path=str(manifest.parent/shards[0]['path']))]
            source_path = folder/'supplement.json'; write(source_path,artifact)
            equivalences = read(manifest.parent/'reviewed_equivalences.json')
            write(folder/'reviewed_equivalences.json',equivalences)
            cfg = folder/'config.json'
            options = dict(manifests=[source_path],config=cfg,dataset=self.dataset,progress=lambda s:None,audit_dav=False)
            first = preprocess(PROJECT,**options); before_sha = sha(first['database'])
            again = preprocess(PROJECT,**options)
            self.assertTrue(again['idempotent_no_change']); self.assertEqual(again['records_upserted'],0)
            self.assertEqual(before_sha,sha(again['database']))
            artifact['shards'].append(dict(shards[1],path=str(manifest.parent/shards[1]['path']))); write(source_path,artifact)
            incremental = preprocess(PROJECT,**options)
            self.assertEqual(incremental['summary']['source_presentations'],2); self.assertEqual(incremental['records_upserted'],1)
            self.assertEqual(len(read(cfg)['sources']),1)
            intact = sha(incremental['database']); equivalences[0]['evidence'][0]['sha256']='0'*64
            write(folder/'reviewed_equivalences.json',equivalences)
            with self.assertRaisesRegex(ValueError,'hash mismatch'): preprocess(PROJECT,**options)
            self.assertEqual(intact,sha(incremental['database']))

if __name__ == '__main__': unittest.main()
