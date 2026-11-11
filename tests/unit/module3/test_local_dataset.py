"""Local full-collection configuration must fail closed and remain read-only."""
import sqlite3

import pytest

from shared.paths import PROJECT_ROOT
from module2_medications.terminology import load_ddinter
from module3_interactions.official_ddinter.dataset import OfficialDataset
from module3_interactions.engine import assess
from tests.unit.module3.test_official import med


def test_official_loader_pins_all_sources_and_index(monkeypatch):
    monkeypatch.setattr('module2_medications.terminology.load_existing_dataset',
                        lambda *a: pytest.fail('Full collection must never invoke bounded loader'))
    dataset = load_ddinter(PROJECT_ROOT, 'official-all')
    assert dataset.coverage['loaded_rows'] == 222383
    assert len(dataset.coverage['source_artifacts']) == 8
    assert all(len(dataset.coverage[key]) == 64 for key in (
        'index_sha256', 'collection_manifest_sha256', 'index_manifest_sha256'))
    with dataset._connect() as db:
        with pytest.raises(sqlite3.OperationalError, match='readonly'):
            db.execute("UPDATE metadata SET value_json='null'")


def test_missing_configured_index_never_uses_sample(monkeypatch, tmp_path):
    monkeypatch.setenv('MSA_DDINTER_INDEX', str(tmp_path / 'missing.sqlite'))
    monkeypatch.setattr('module2_medications.terminology.load_existing_dataset',
                        lambda *a: pytest.fail('Missing real data must never use sample'))
    with pytest.raises(FileNotFoundError):
        load_ddinter(PROJECT_ROOT, 'official-all')


def test_explicit_index_configuration(monkeypatch):
    path = PROJECT_ROOT / 'data/DDInter/official.sqlite'
    monkeypatch.setenv('MSA_DDINTER_INDEX', str(path))
    assert OfficialDataset().path == path


def test_severe_hold_and_single_applicability_are_information_only():
    dataset = OfficialDataset()
    inputs = [med(dataset, i, n) for n, i in enumerate(('DDInter582', 'DDInter725'), 1)]
    result = assess(inputs, dataset)
    assert result['reminder_hold']['required']
    assert result['reminder_hold']['medication_ids'] == ['synthetic-med-1', 'synthetic-med-2']
    assert not result['reminder_hold']['activation_policy_implemented']
    assert result['safe_to_take'] is None
    assert assess(inputs[:1], dataset)['inter_medication_check_applicability'] == 'NOT_APPLICABLE'


def test_verified_ddinter_duplicate_is_separate_from_self_interaction():
    dataset = OfficialDataset()
    result = assess([med(dataset, 'DDInter14', n) for n in (1, 2)], dataset)
    assert len(result['duplicate_ingredients']) == 1
    assert result['duplicate_ingredients'][0]['ddinter_id'] == 'DDInter14'
    assert not result['checked_ingredient_pairs'] and not result['matched_interactions']


def test_mixed_reference_builds_fail_before_lookup():
    dataset = OfficialDataset()
    inputs = [med(dataset, i, n) for n, i in enumerate(('DDInter582', 'DDInter725'), 1)]
    for m, build in zip(inputs, ('a' * 64, 'b' * 64)):
        m['dataset_build'] = build
    with pytest.raises(ValueError, match='consistent reference'):
        assess(inputs, dataset)
