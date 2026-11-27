"""Offline transport/validation regressions; these never call an Ollama server."""
import json
import traceback

import httpx
import pytest

from module1_intake.nlp.models import Administration, DialogueAct, Intent, IntentCandidate, Medication, Understanding
from module1_intake.nlp.understanding.providers import (
    InferenceCategory as C, InferenceError, MockProvider, OllamaProvider, understand,
)
from module1_intake.nlp.understanding.validation import validate_medication


SECRET = 'SYNTHETIC_PRIVATE_SENTINEL_7823'


def envelope(content, **overrides):
    return dict(done=True, done_reason='stop', message={'content': content}, **overrides)


def assert_private_failure(provider, category, caplog, *, attempts=1, status=None):
    with pytest.raises(InferenceError) as caught:
        understand(provider, SECRET, {'private': SECRET}, attempts=attempts)
    error = caught.value
    assert error.category == category
    assert len(error.diagnostics) == attempts
    assert [d.attempt for d in error.diagnostics] == list(range(1, attempts + 1))
    assert error.http_status == status
    assert SECRET not in str(error)
    assert SECRET not in repr(error.diagnostics)
    assert SECRET not in ''.join(traceback.format_exception(error))
    assert SECRET not in caplog.text
    assert all(record.exc_info is None for record in caplog.records)
    return error


@pytest.mark.parametrize('body,category', [
    # Actual Qwen failure: generation budget exhausted entirely in thinking.
    ({'done': True, 'done_reason': 'length', 'message': {'content': '', 'thinking': SECRET}}, C.INCOMPLETE_RESPONSE),
    ({'done': True, 'done_reason': 'length', 'message': {'content': '{}'}}, C.INCOMPLETE_RESPONSE),
    ({'done': False, 'message': {'content': '{}'}}, C.INCOMPLETE_RESPONSE),
    ({'message': {'content': '{}'}}, C.INCOMPLETE_RESPONSE),
    (envelope(''), C.EMPTY_RESPONSE),
    (envelope(' \n'), C.EMPTY_RESPONSE),
    (envelope(None), C.HTTP_RESPONSE),
    ({'done': True, 'message': []}, C.HTTP_RESPONSE),
    ([], C.HTTP_RESPONSE),
    ({'error': SECRET}, C.HTTP_RESPONSE),
])
def test_ollama_envelope_failures_are_categorized_without_content(body, category, caplog):
    provider = OllamaProvider('test', transport=httpx.MockTransport(lambda r: httpx.Response(200, json=body)))
    assert_private_failure(provider, category, caplog)


def test_invalid_http_json_is_distinct_from_model_json(caplog):
    provider = OllamaProvider('test', transport=httpx.MockTransport(lambda r: httpx.Response(200, text=SECRET)))
    assert_private_failure(provider, C.HTTP_RESPONSE, caplog)


@pytest.mark.parametrize('status', [400, 404, 500, 503])
def test_http_status_is_safe_and_preserved(status, caplog):
    provider = OllamaProvider('test', transport=httpx.MockTransport(lambda r: httpx.Response(status, text=SECRET)))
    assert_private_failure(provider, C.HTTP_STATUS, caplog, status=status)


@pytest.mark.parametrize('error_type,category', [
    (httpx.ConnectError, C.CONNECTIVITY),
    (httpx.ReadTimeout, C.TIMEOUT),
    (httpx.ConnectTimeout, C.TIMEOUT),
    (httpx.RemoteProtocolError, C.HTTP_RESPONSE),
])
def test_transport_errors_do_not_expose_exception_text(error_type, category, caplog):
    def fail(request):
        raise error_type(SECRET, request=request)
    provider = OllamaProvider('test', transport=httpx.MockTransport(fail))
    assert_private_failure(provider, category, caplog)
    with pytest.raises(InferenceError) as caught:
        provider.infer(SECRET, {})
    assert SECRET not in ''.join(traceback.format_exception(caught.value))


@pytest.mark.parametrize('raw,category', [
    (SECRET, C.JSON),
    (json.dumps({SECRET: SECRET}), C.SCHEMA),
    (json.dumps({'medications': [{'evidence_text': SECRET, 'name_raw': 123}]}), C.SCHEMA),
    (Understanding(medications=[Medication(name_raw='invented', evidence_text=SECRET)]).model_dump_json(), C.EVIDENCE),
    ('', C.EMPTY_RESPONSE),
    ('x' * 200001, C.RESPONSE_SIZE),
    (ValueError(SECRET), C.PROVIDER),
    (TypeError(SECRET), C.PROVIDER),
    (InferenceError(SECRET), C.PROVIDER),
])
def test_json_schema_evidence_and_provider_errors_are_distinct(raw, category, caplog):
    assert_private_failure(MockProvider([raw]), category, caplog)


def test_retry_history_is_bounded_and_preserves_categories(caplog):
    error = assert_private_failure(MockProvider(['not json', json.dumps({SECRET: SECRET})]),
                                   C.SCHEMA, caplog, attempts=2)
    assert [d.category for d in error.diagnostics] == [C.JSON, C.SCHEMA]


def test_retry_can_recover_without_skipping_grounding():
    good = Understanding(medications=[Medication(name_raw='Panadol', evidence_text='Panadol')]).model_dump_json()
    provider = MockProvider(['not json', good])
    assert understand(provider, 'Panadol', {}).medications[0].name_raw == 'Panadol'
    assert provider.calls == 2


def test_vietnamese_dose_timing_and_prescribed_quantity_transport():
    text = 'Tôi đang uống Panadol 500mg, mỗi sáng 1 viên. Bác sĩ kê 2 hộp.'
    expected = Understanding(medications=[Medication(
        name_raw='Panadol', strength_raw='500mg', dose_raw='1 viên', quantity_raw='2 hộp',
        administrations=[Administration(timing_raw='mỗi sáng', dose_raw='1 viên')], evidence_text=text,
    )])
    def handler(request):
        body = json.loads(request.content)
        assert body['think'] is False
        schema = body['format']
        assert schema['additionalProperties'] is False
        assert 'timing_slots_raw' not in schema['$defs']['Administration']['properties']
        assert schema['$defs']['Administration']['additionalProperties'] is False
        assert set(schema['$defs']['Medication']['properties']['uncertain_fields']['items']['enum']) == (
            set(Medication.model_fields) - {'uncertain_fields', 'evidence_text'})
        assert json.loads(body['messages'][1]['content'])['text'] == text
        return httpx.Response(200, json=envelope(expected.model_dump_json()))
    value = understand(OllamaProvider('test', transport=httpx.MockTransport(handler)), text, {})
    expected.intents = [IntentCandidate(intent=Intent.ADD_MEDICATION, evidence_text=text)]
    expected.dialogue_act = DialogueAct.PROVIDE_INFO
    expected.medications[0].administrations[0].timing_slots_raw = ['mỗi sáng']
    assert value == expected


@pytest.mark.parametrize('patch', [
    {'dose_raw': '2 hộp'}, {'dose_raw': '500mg'}, {'strength_raw': '250mg'},
    {'name_raw': 'paracetamol'}, {'quantity_raw': '1 viên'},
])
def test_fix_preserves_strict_medication_safety(patch):
    text = 'Panadol 500mg, uống 1 viên, bác sĩ kê 2 hộp'
    values = dict(name_raw='Panadol', strength_raw='500mg', dose_raw='1 viên', quantity_raw='2 hộp', evidence_text=text)
    values.update(patch)
    raw = Understanding(medications=[Medication(**values)]).model_dump_json()
    with pytest.raises(InferenceError) as caught:
        understand(MockProvider([raw]), text, {}, attempts=1)
    assert caught.value.category == C.EVIDENCE


@pytest.mark.parametrize('model_fields', [[], ['strength_raw'], ['quantity_raw']])
def test_model_uncertainty_list_cannot_suppress_backend_flags(model_fields):
    text = 'Có lẽ tôi đang dùng Panadol, không nhớ hàm lượng.'
    original = Medication(name_raw='Panadol', evidence_text=text, uncertain_fields=model_fields)
    med = validate_medication(original, text)
    assert med.uncertainty_raw == 'Có lẽ'
    assert 'name_raw' in med.uncertain_fields
    assert set(model_fields) <= set(med.uncertain_fields)
    assert original.uncertainty_raw is None  # Validation does not mutate input.
    assert med.strength_raw is None


def test_source_uncertainty_marks_all_present_core_fields_even_with_partial_model_list():
    text = 'Hình như đang dùng Panadol 500mg, 1 viên'
    med = validate_medication(Medication(name_raw='Panadol', strength_raw='500mg', dose_raw='1 viên',
                                        evidence_text=text, uncertain_fields=['dose_raw']), text)
    assert set(med.uncertain_fields) == {'name_raw', 'strength_raw', 'dose_raw'}
    assert validate_medication(med, text) == med
