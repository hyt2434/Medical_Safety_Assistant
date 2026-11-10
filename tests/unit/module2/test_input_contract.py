"""Same shared DTO and Module 2 matcher for synthetic source adapters."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unicodedata
from uuid import uuid4

import pytest

from shared.intake_contracts import Medication, Module2Handoff, ConfirmedEntry
from shared.db.intake_adapter import persist_module1, build_confirmed_handoff
from module2_medications import identify_confirmed
from tests.unit.test_nlp_module2_flow import IdentifyingCore
from tests.unit.module2.test_core import BUILD, component, mapping


class SourceCore(IdentifyingCore):
    """Extend the existing spy's I/O shapes; real confirmation guards are tested on PostgreSQL."""
    def record_input(self, intake, modality, original_bytes, *, payload, content_type=None, message=None):
        self._owned('intake_sessions', intake)
        return self.put('intake_inputs', session_id=intake, modality=modality, content_type=content_type,
                        message_id=message, payload_or_locator=deepcopy(payload),
                        input_digest=hashlib.sha256(original_bytes).hexdigest())

    def record_extraction(self, input_id, name, version, result, **kw):
        return self.put('intake_extractions', input_id=input_id, extractor_name=name, extractor_version=version,
                        attempt_no=1, result=result, **kw)

    def create_item(self, extraction, ordinal, medication_fields, *, locator=None):
        row = super().create_item(extraction, ordinal, medication_fields)
        parent = self._owned('intake_extractions', extraction)
        self.tables['intake_items'][str(row['item_id'])]['origin_evidence'] = {
            'schema': 'item-origin.v4', 'input_id': str(parent['input_id']), 'extraction_id': str(extraction),
            'item_ordinal': ordinal, 'locator': deepcopy(locator or {}), 'text_raw': medication_fields['evidence_text']}
        return row


@pytest.mark.parametrize('kind,modality', [('CHATBOT', 'TEXT'), ('OCR', 'IMAGE'), ('MANUAL', 'MANUAL')])
@pytest.mark.parametrize('scenario', ['exact', 'ambiguous', 'combination', 'missing', 'unmatched'])
def test_source_kind_does_not_change_identity_candidates_or_components(kind, modality, scenario):
    repo = SourceCore(ambiguous=scenario == 'ambiguous')
    for product in repo.references.products:
        product['brand_name'] = 'Thuốc Thử'
    med = repo.references.products[0]
    if scenario == 'combination':
        med['component_count'] = 2
        extra = component(med, name='Source Beta', ordinal=2)
        repo.references.components.append(extra)
        repo.references.mappings.append(mapping(extra, 'DDInter900002', 'Synthetic Beta'))
    name = unicodedata.normalize('NFD', 'THUỐC  THỬ')
    if scenario == 'unmatched': name = 'Không có trong tham chiếu'
    raw = Medication(name_raw=name if scenario != 'missing' else None,
        strength_raw=None if scenario == 'ambiguous' else '0,5g',
        dosage_form_raw=None if scenario == 'ambiguous' else 'tablet', evidence_text=name + ' 0,5g tablet')
    convo = repo.create_conversation()
    intake = repo.create_intake(convo['id'])
    workflow = repo.create_workflow(convo['id'], 'MEDICATION_INTAKE', intake=intake['id'])
    original = raw.model_dump_json().encode('utf-8')
    payload = {'schema': 'input.v4', 'digest_basis': 'ORIGINAL_BYTES', 'source_kind': kind,
               'text': raw.evidence_text, 'synthetic_fixture': True}
    locator = {'synthetic_fixture': True, 'source_kind': kind, 'row': 1}
    saved = persist_module1(repo, intake['id'], original, {'medications': [raw.model_dump()]},
        modality=modality, input_payload=payload, extractor_name='synthetic-' + kind.lower(),
        extractor_version='v1', item_locators=[locator])
    entry = saved['entries'][0]
    with pytest.raises(ValueError): build_confirmed_handoff(repo, workflow['id'])
    # Test double API requires exact digest and explicit action; no confirmation column is assigned.
    repo.confirm_entry(entry['id'], entry['content_digest'], uuid4(), explicit_confirmation=True)
    ctx = deepcopy(workflow['context'])
    ctx['entry_version_ids'] = [str(entry['id'])]
    repo.transition_workflow(workflow['id'], 'COMPLETED', expected_revision=workflow['revision'], context=ctx)
    handoff = build_confirmed_handoff(repo, workflow['id'])
    assert type(handoff) is Module2Handoff and type(handoff.entries[0]) is ConfirmedEntry
    match, result = identify_confirmed(repo, handoff, dataset_build=BUILD)[0]
    if scenario == 'ambiguous':
        assert result['identification_status'] == 'REVIEW_REQUIRED' and len(result['candidates']) == 2
        assert result['identified_candidate'] is None and result['verified_ddinter_ids'] == []
    elif scenario == 'missing':
        assert result['identification_status'] == 'REVIEW_REQUIRED'
        assert not result['ready_for_identifier_handoff'] and result['candidates']
        assert all(not c['establishes_identity'] for c in result['candidates'])
    elif scenario == 'unmatched':
        assert result['identification_status'] == 'UNRESOLVED' and result['candidates'] == []
    else:
        assert result['ready_for_identifier_handoff'] and match['match_status'] == 'SELECTED'
        assert len(result['ingredients']) == (2 if scenario == 'combination' else 1)
    assert result['input_evidence']['inputs'][0]['payload_or_locator'] == payload
    assert result['input_evidence']['origin_evidence']['locator'] == locator
    assert result['input_evidence']['extractions'][0]['extractor_name'] == 'synthetic-' + kind.lower()
    json.dumps(result)


@pytest.mark.parametrize('locators', [[], [{} , {}], [None], 'not-an-array'])
def test_misaligned_locators_are_rejected_before_any_input_is_persisted(locators):
    repo = SourceCore()
    with pytest.raises(ValueError, match='locators'):
        persist_module1(repo, uuid4(), b'fixture', {'medications': [{'name_raw': 'Alpha'}]},
            modality='MANUAL', input_payload={}, extractor_name='synthetic', extractor_version='v1', item_locators=locators)
    assert not repo.tables


def test_nlp_exports_are_aliases_of_the_unchanged_shared_contract():
    from module1_intake.nlp import models
    from shared import intake_contracts
    for name in ('Administration', 'Medication', 'ConfirmedEntry', 'Module2Handoff', 'StrictModel'):
        assert getattr(models, name) is getattr(intake_contracts, name)


def test_module2_and_shared_handoff_can_import_with_all_nlp_modules_blocked():
    code = '''
import builtins, sys
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name == 'module1_intake.nlp' or name.startswith('module1_intake.nlp.'):
        raise AssertionError('Module 2 imported NLP')
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
from module2_medications import identify_confirmed
from shared.intake_contracts import Medication, Module2Handoff
from shared.db.intake_adapter import build_confirmed_handoff, persist_module1
assert not any(n.startswith('module1_intake.nlp') for n in sys.modules)
'''
    env = {**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[3] / 'src')}
    result = subprocess.run([sys.executable, '-B', '-c', code], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
