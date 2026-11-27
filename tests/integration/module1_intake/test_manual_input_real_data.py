"""Opt-in, read-only autocomplete smoke test against the local medication CSVs.

This checks source-row retention through the shared API, not clinical accuracy.
"""
import csv
from collections import defaultdict
from copy import deepcopy
import json
import os
from pathlib import Path

import pytest

from module1_intake import api
from module1_intake.manual_input.text_utils import compact
from module1_intake.manual_input.dictionary import load_dictionary


@pytest.mark.skipif(
    os.environ.get('MANUAL_INPUT_RUN_REAL_DATA') != '1',
    reason='Opt-in local medication CSVs; no dataset download',
)
def test_local_dictionary_through_shared_api(tmp_path, monkeypatch):
    data_dir = Path(os.environ.get('MEDICATION_DATA_DIR') or api.DEFAULT_MEDICATION_DATA_DIR).resolve()
    with (data_dir / 'medications.csv').open(encoding='utf-8-sig', newline='') as stream:
        source_rows = {row['id']: row for row in csv.DictReader(stream)}

    # Exercise the configured dataset from another CWD, including lazy initialization.
    monkeypatch.setenv('MEDICATION_DATA_DIR', str(data_dir))
    monkeypatch.setattr(api, '_suggester', None)
    monkeypatch.chdir(tmp_path)
    for query, match_type in [('augmen', 'EXACT_PREFIX'), ('augmetnin', 'FUZZY_MATCH')]:
        results = api.suggest_medication_names(query, limit=5)
        assert 1 <= len(results) <= 5
        assert any(
            compact(result['brand_name']).startswith('augmentin')
            and result['match_type'] == match_type
            for result in results
        )
        for result in results:
            # The source algorithm may fill remaining slots with fuzzy matches.
            assert result['match_type'] in {'EXACT_PREFIX', 'FUZZY_MATCH'}
            source = source_rows[result['medication_id']]
            assert result['brand_name'] == source['brand_name'].strip()
            assert result['dosage_form'] == (source['dosage_form'].strip() or None)
        print(f'\nLocal CSV {query!r}: {[row["brand_name"] for row in results]}')

    assert api._suggester is not None


@pytest.mark.skipif(os.environ.get('MANUAL_INPUT_RUN_REAL_DATA') != '1', reason='Opt-in local medication CSV review')
def test_exact_typo_ambiguous_products_and_no_selection(monkeypatch):
    from module1_intake.nlp.interfaces.application import ApplicationService
    from module1_intake.nlp.understanding.providers import MockProvider
    from tests.unit.test_nlp import FakeCore

    root = Path(__file__).resolve().parents[3]
    data_dir = Path(os.environ.get('MEDICATION_DATA_DIR') or api.DEFAULT_MEDICATION_DATA_DIR)
    with (data_dir / 'medications.csv').open(encoding='utf-8-sig', newline='') as stream:
        source_rows = {row['id']: row for row in csv.DictReader(stream)}
    entries = load_dictionary(data_dir)
    monkeypatch.setattr(api, '_suggester', None)
    api.init_suggester(data_dir)
    repo = FakeCore()
    service = ApplicationService(repo, MockProvider())
    current = service.start()
    before = deepcopy(repo.tables)
    cases = []
    for kind, query in [('exact', 'Amoxicillin 250 mg'), ('typo', 'augmetnin'), ('near_products', 'amoxicillin')]:
        results = api.suggest_medication_names(query, limit=5)
        assert results and all(row['medication_id'] for row in results)
        if kind == 'typo':
            assert any(row['match_type'] == 'FUZZY_MATCH' and row['brand_name'] == 'Augmentin ES' for row in results)
        for row in results:
            source = source_rows[row['medication_id']]
            assert row['brand_name'] == source['brand_name'].strip()
            assert row['dosage_form'] == (source['dosage_form'].strip() or None)
        cases.append({'case': kind, 'query': query, 'results': results})

    # Review distinct registered products sharing display fields; retain their IDs.
    groups = defaultdict(list)
    for entry in entries:
        groups[(compact(entry.brand_name), entry.strength, compact(entry.dosage_form))].append(entry)
    duplicate = next(group for group in sorted(groups.values(), key=len, reverse=True)
        if len({source_rows[e.medication_id]['registration_token'] for e in group}) > 1
        and len(compact(group[0].brand_name)) >= 4)
    query = duplicate[0].brand_name
    results = api.suggest_medication_names(query, limit=100)
    shown = {row['medication_id'] for row in results}
    hidden = [entry.medication_id for entry in duplicate if entry.medication_id not in shown]
    report = {'cases': cases, 'automatic_selection': False,
        'duplicate_display_group': {'query': query,
            'source_products': [{'id': e.medication_id, 'brand_name': e.brand_name,
                'strength': e.strength, 'dosage_form': e.dosage_form,
                'registration_token': source_rows[e.medication_id]['registration_token']} for e in duplicate],
            'suggestions': results, 'hidden_product_ids': hidden}}
    assert repo.tables == before and service.resume(current.workflow_id).entries == []
    output = root / 'artifacts/voice_manual_input/manual_input_review.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('\nManual review:', json.dumps(report, ensure_ascii=False))


@pytest.mark.skipif(os.environ.get('MANUAL_INPUT_RUN_REAL_DATA') != '1', reason='Opt-in real CSV acceptance')
def test_lenalimid_ids_and_source_only_amoxicillin_strength(monkeypatch):
    expected_ids = {'PC_010cdfd04f615a42914b4719', 'PC_03b9ee6ccfefa60db000d48f',
                    'PC_3cae488026778623c1b9c223', 'PC_6108f0758c3df7cff2609ff0',
                    'PC_f55e22692f69802f49539fe6'}
    data_dir = Path(os.environ.get('MEDICATION_DATA_DIR') or api.DEFAULT_MEDICATION_DATA_DIR)
    monkeypatch.setattr(api, '_suggester', None)
    api.init_suggester(data_dir)
    results = api.suggest_medication_names('Lenalimid', limit=100)
    ids = [row['medication_id'] for row in results]
    assert all(ids.count(product_id) == 1 for product_id in expected_ids)
    assert len(ids) == len(set(ids)) and len(ids) <= 100
    print('\nLenalimid accepted IDs:', sorted(expected_ids & set(ids)))
    entry = next(entry for entry in load_dictionary(data_dir)
                 if entry.medication_id == 'PC_2af7fe7ecdf05a94429a9f5a')
    assert entry.strength is None
    print('Amoxicillin component-only strength:', entry.strength)
