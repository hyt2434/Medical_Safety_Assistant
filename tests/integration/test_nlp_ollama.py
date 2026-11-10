"""Opt-in real local inference on synthetic Vietnamese text. No database access.

Run via src/module1_intake/nlp/test_ollama.ps1 from the repository root.
"""
import os

import pytest

from module1_intake.nlp.models import Intent, Understanding
from module1_intake.nlp.understanding.providers import InferenceCategory, InferenceError, OllamaProvider, understand
from module1_intake.nlp.understanding.validation import validate_understanding


@pytest.fixture(scope='module')
def provider():
    if os.environ.get('NLP_RUN_REAL_OLLAMA') != '1':
        pytest.skip('Opt-in real Ollama inference; NLP_RUN_REAL_OLLAMA=1 required')
    return OllamaProvider(
        os.environ.get('NLP_OLLAMA_MODEL', 'qwen3.5:9b'),
        base_url=os.environ.get('NLP_OLLAMA_URL', 'http://127.0.0.1:11434'),
        timeout=float(os.environ.get('NLP_OLLAMA_TIMEOUT', '60')),
    )


def extract(provider, text, context=None):
    # Exercise the public path including JSON parsing and strict evidence checks.
    value = understand(provider, text, context or {}, attempts=1)
    assert Understanding.model_validate_json(value.model_dump_json()) == value
    assert validate_understanding(value, text) == value
    return value


def test_real_panadol_strength_dose_timing_and_prescribed_quantity(provider):
    value = extract(provider, 'Tôi đang uống Panadol 500mg, mỗi sáng 1 viên. Bác sĩ kê 2 hộp.')
    assert len(value.medications) == 1
    med = value.medications[0]
    assert (med.name_raw, med.strength_raw, med.dose_raw, med.quantity_raw) == ('Panadol', '500mg', '1 viên', '2 hộp')
    assert any(a.timing_raw == 'mỗi sáng' and a.dose_raw == '1 viên' for a in med.administrations)
    assert med.route_raw is None and med.dosage_form_raw is None
    assert med.duration_raw is None and med.negation_raw is None and med.uncertainty_raw is None


def test_real_dose_before_timing(provider):
    med, = extract(provider, 'Tôi đang uống Panadol 500mg, 1 viên mỗi sáng.').medications
    assert (med.name_raw, med.strength_raw, med.dose_raw) == ('Panadol', '500mg', '1 viên')
    assert any(a.timing_raw == 'mỗi sáng' and a.dose_raw == '1 viên' for a in med.administrations)
    assert med.quantity_raw is None


def test_real_multiple_medications_do_not_share_slots(provider):
    text = 'Tôi đang uống Panadol 500mg, mỗi sáng 1 viên, bác sĩ kê 2 hộp; đang dùng Vitamin C 100mg, mỗi tối 2 viên, bác sĩ kê 1 hộp.'
    value = extract(provider, text)
    assert len(value.medications) == 2
    a, b = value.medications
    assert (a.name_raw, a.strength_raw, a.dose_raw, a.quantity_raw) == ('Panadol', '500mg', '1 viên', '2 hộp')
    assert (b.name_raw, b.strength_raw, b.dose_raw, b.quantity_raw) == ('Vitamin C', '100mg', '2 viên', '1 hộp')
    assert any(x.timing_raw == 'mỗi sáng' and x.dose_raw == '1 viên' for x in a.administrations)
    assert any(x.timing_raw == 'mỗi tối' and x.dose_raw == '2 viên' for x in b.administrations)


def test_real_missing_fields_remain_missing(provider):
    med, = extract(provider, 'Tôi đang uống Panadol.').medications
    assert med.name_raw == 'Panadol'
    for field in ('strength_raw', 'dose_raw', 'dosage_form_raw', 'route_raw', 'frequency_raw', 'duration_raw', 'quantity_raw'):
        assert getattr(med, field) is None
    assert med.administrations == []


def test_real_uncertain_medication_is_not_asserted_as_certain(provider):
    med, = extract(provider, 'Có lẽ tôi đang dùng Panadol, không nhớ hàm lượng.').medications
    assert med.name_raw == 'Panadol'
    assert med.uncertainty_raw is not None and 'name_raw' in med.uncertain_fields
    assert med.strength_raw is None and med.dose_raw is None and med.quantity_raw is None


def test_real_negation_is_preserved(provider):
    med, = extract(provider, 'Tôi không dùng Panadol 500mg.').medications
    assert med.name_raw == 'Panadol' and med.strength_raw == '500mg'
    assert med.negation_raw is not None


def test_real_followup_does_not_copy_context_as_current_evidence(provider):
    context = {'entries': [{'name_raw': 'Panadol', 'strength_raw': '500mg'}]}
    med, = extract(provider, 'Mỗi sáng 1 viên. Bác sĩ kê 2 hộp.', context).medications
    assert med.name_raw is None and med.strength_raw is None
    assert med.dose_raw == '1 viên' and med.quantity_raw == '2 hộp'
    assert any(a.timing_raw == 'Mỗi sáng' and a.dose_raw == '1 viên' for a in med.administrations)


def test_real_missing_model_reports_http_status_without_response_body(provider):
    # /api/chat does not pull models. This deliberately nonexistent tag exercises
    # a real local error response without changing the installed model inventory.
    missing = OllamaProvider('nlp-synthetic-nonexistent-model:regression',
                             base_url=provider.base_url, timeout=provider.timeout)
    with pytest.raises(InferenceError) as caught:
        understand(missing, 'Tôi đang uống Panadol.', {}, attempts=1)
    assert caught.value.category == InferenceCategory.HTTP_STATUS
    assert caught.value.http_status == 404
    assert len(caught.value.diagnostics) == 1
    assert 'Panadol' not in str(caught.value)


@pytest.mark.parametrize('text,marker', [
    ('Tôi được kê 2 hộp Panadol 500mg.', None),
    ('Tôi đang uống Panadol 500mg.', None),
    ('Vui lòng lưu Panadol 500mg vào hồ sơ thuốc của tôi.', 'Vui lòng lưu'),
])
def test_real_report_and_explicit_record_request_semantics(provider, text, marker):
    value = extract(provider, text)
    candidate, = value.intents
    assert candidate.intent == Intent.ADD_MEDICATION
    assert candidate.record_request_raw == marker
    med, = value.medications
    assert med.name_raw == 'Panadol' and med.strength_raw == '500mg'
    assert med.quantity_raw == ('2 hộp' if '2 hộp' in text else None)


def test_real_combined_administration_keeps_raw_phrase_and_distinct_slots(provider):
    text = 'Bác sĩ kê Augmentin 625mg, uống 1 viên sáng và tối trong 7 ngày.'
    med, = extract(provider, text).medications
    assert med.name_raw == 'Augmentin' and med.strength_raw == '625mg'
    assert med.dose_raw == '1 viên' and med.duration_raw in {'7 ngày', 'trong 7 ngày'}
    admin, = med.administrations
    assert admin.timing_raw == 'sáng và tối'
    assert admin.timing_slots_raw == ['sáng', 'tối']
    assert admin.dose_raw == '1 viên'
    assert med.frequency_raw is None


def test_real_alternative_timing_is_not_two_administration_slots(provider):
    text = 'Bác sĩ kê Augmentin 625mg, uống 1 viên sáng hoặc tối.'
    med, = extract(provider, text).medications
    admin, = med.administrations
    assert admin.timing_raw == 'sáng hoặc tối'
    assert admin.timing_slots_raw == ['sáng hoặc tối']
    assert admin.dose_raw == '1 viên'


def test_real_information_question_is_not_a_record_request(provider):
    value = extract(provider, 'Tra cứu thành phần Panadol 500mg.')
    assert Intent.MEDICATION_QA in {candidate.intent for candidate in value.intents}
    assert Intent.ADD_MEDICATION not in {candidate.intent for candidate in value.intents}
    assert all(candidate.record_request_raw is None for candidate in value.intents)
