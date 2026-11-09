"""Source-backed intent and timing regressions. All inference here is mocked."""
import json
import unicodedata

import pytest

from module1_intake.nlp.interactive import format_understanding
from module1_intake.nlp.models import Administration, Intent, IntentCandidate, Medication, Understanding
from module1_intake.nlp.providers import InferenceCategory, InferenceError, MockProvider, understand
from module1_intake.nlp.routing import detect
from module1_intake.nlp.validation import EvidenceError, validate_medication, validate_understanding
from tests.unit.test_nlp import conversation, send


REPORT = 'Tôi được kê 2 hộp Panadol 500mg.'
REQUEST = 'Vui lòng lưu Panadol 500mg vào hồ sơ thuốc của tôi.'
SCHEDULE = 'Bác sĩ kê Augmentin 625mg, uống 1 viên sáng và tối trong 7 ngày.'


@pytest.mark.parametrize('text,marker', [(REPORT, None), ('Tôi đang uống Panadol 500mg.', None),
                                       (REQUEST, 'Vui lòng lưu')])
def test_missing_model_intent_uses_same_intake_semantics_as_routing(text, marker):
    raw = Understanding(medications=[Medication(name_raw='Panadol', strength_raw='500mg', evidence_text=text)])
    value = understand(MockProvider([raw.model_dump_json()]), text, {}, attempts=1)
    assert [candidate.intent for candidate in value.intents] == [Intent.ADD_MEDICATION]
    candidate, = value.intents
    assert candidate.record_request_raw == marker
    assert candidate.evidence_text in text
    assert detect(text, value) == [Intent.ADD_MEDICATION]
    assert validate_understanding(value, text) == value
    assert f'record_request_raw: {json.dumps(marker, ensure_ascii=False)}' in format_understanding(value)


@pytest.mark.parametrize('text,intent', [
    ('Tra cứu thành phần Panadol 500mg.', Intent.MEDICATION_QA),
    ('Hãy kê đơn Panadol 500mg.', Intent.UNSUPPORTED),
    ('Cách thêm thuốc Panadol 500mg?', Intent.APP_HELP),
])
def test_questions_and_new_prescription_requests_are_not_reports(text, intent):
    raw = Understanding(medications=[Medication(name_raw='Panadol', strength_raw='500mg', evidence_text=text)])
    value = understand(MockProvider([raw.model_dump_json()]), text, {}, attempts=1)
    assert [candidate.intent for candidate in value.intents] == [intent]
    assert value.intents[0].record_request_raw is None


def test_prescription_report_combines_with_safety_request():
    text = REPORT + ' Kiểm tra tương tác.'
    raw = Understanding(medications=[Medication(name_raw='Panadol', evidence_text=REPORT)])
    value = understand(MockProvider([raw.model_dump_json()]), text, {}, attempts=1)
    assert {candidate.intent for candidate in value.intents} == {Intent.ADD_MEDICATION, Intent.CHECK_INTERACTION}


@pytest.mark.parametrize('text,raw', [(REPORT, 'được kê'), ('Tôi không yêu cầu lưu Panadol.', 'lưu'),
                                    ('Có nên lưu Panadol?', 'lưu')])
def test_report_question_or_negation_cannot_claim_explicit_record_request(text, raw):
    value = Understanding(intents=[IntentCandidate(intent=Intent.ADD_MEDICATION, evidence_text=text, record_request_raw=raw)])
    with pytest.raises(EvidenceError, match='record request'):
        validate_understanding(value, text)


def test_ungrounded_intent_is_rejected_before_backend_completion():
    raw = Understanding(intents=[IntentCandidate(intent=Intent.ADD_MEDICATION, evidence_text='invented')],
                        medications=[Medication(name_raw='Panadol', evidence_text=REPORT)])
    with pytest.raises(InferenceError) as caught:
        understand(MockProvider([raw.model_dump_json()]), REPORT, {}, attempts=1)
    assert caught.value.category == InferenceCategory.EVIDENCE


@pytest.mark.parametrize('text', [REPORT, REQUEST])
def test_report_and_save_request_both_require_review_and_explicit_confirmation(text):
    raw = Understanding(medications=[Medication(name_raw='Panadol', strength_raw='500mg', evidence_text=text)])
    repo, bot, reply = conversation(MockProvider([raw.model_dump_json()]))
    reply = send(bot, reply, text)
    assert reply.state == 'CLARIFYING' and reply.handoff is None
    reply = send(bot, reply, 'không rõ')
    assert reply.state == 'AWAITING_CONFIRMATION' and reply.handoff is None
    assert all(row['confirmed_at'] is None for row in repo.tables['medication_entry_versions'].values())


def test_combined_timing_retains_parent_phrase_dose_and_duration():
    original = Medication(name_raw='Augmentin', strength_raw='625mg', dose_raw='1 viên', duration_raw='trong 7 ngày',
                          evidence_text=SCHEDULE, administrations=[Administration(timing_raw='sáng và tối', dose_raw='1 viên')])
    med = validate_medication(original, SCHEDULE)
    admin, = med.administrations
    assert admin.timing_raw == 'sáng và tối'
    assert admin.timing_slots_raw == ['sáng', 'tối']
    assert admin.dose_raw == med.dose_raw == '1 viên'
    assert med.duration_raw == 'trong 7 ngày'
    assert med.frequency_raw is None
    assert original.administrations[0].timing_slots_raw == []
    assert validate_medication(med, SCHEDULE) == med
    assert Medication.model_validate_json(med.model_dump_json()) == med


@pytest.mark.parametrize('timing,slots', [('sáng và tối', ['sáng', 'tối']), ('Sáng và Tối', ['Sáng', 'Tối']),
                                       ('sáng hoặc tối', ['sáng hoặc tối']), ('sáng đến tối', ['sáng đến tối']),
                                       ('trước ăn sáng và tối', ['trước ăn sáng và tối']),
                                       ('sáng sớm và tối muộn', ['sáng sớm và tối muộn']),
                                       ('mỗi sáng', ['mỗi sáng'])])
def test_projection_only_splits_explicit_bare_daypart_conjunction(timing, slots):
    text = f'Panadol 500mg, uống 1 viên {timing}.'
    med = validate_medication(Medication(name_raw='Panadol', evidence_text=text,
                                        administrations=[Administration(timing_raw=timing, dose_raw='1 viên')]), text)
    assert med.administrations[0].timing_slots_raw == slots


def test_decomposed_unicode_timing_slots_are_original_source_spans():
    timing = unicodedata.normalize('NFD', 'sáng và tối')
    text = f'Augmentin 625mg, 1 viên {timing}'
    med = validate_medication(Medication(evidence_text=text, administrations=[Administration(timing_raw=timing)]), text)
    assert med.administrations[0].timing_slots_raw == [unicodedata.normalize('NFD', word) for word in ('sáng', 'tối')]


@pytest.mark.parametrize('slots', [['08:00', '20:00'], ['sáng', 'trưa'], ['tối', 'sáng'],
                                  ['sáng', 'sáng', 'tối'], ['sáng']])
def test_invented_or_incomplete_timing_slots_are_rejected(slots):
    med = Medication(evidence_text=SCHEDULE, administrations=[
        Administration(timing_raw='sáng và tối', timing_slots_raw=slots)])
    with pytest.raises(EvidenceError):
        validate_medication(med, SCHEDULE)


@pytest.mark.parametrize('connector', ['và', 'hoặc', 'đến'])
def test_grouped_evidence_cannot_be_lost_in_independent_administrations(connector):
    text = f'Augmentin 625mg, uống 1 viên sáng {connector} tối.'
    med = Medication(evidence_text=text, administrations=[Administration(timing_raw='sáng', dose_raw='1 viên'),
                                                         Administration(timing_raw='tối', dose_raw='1 viên')])
    with pytest.raises(EvidenceError, match='Grouped timing'):
        validate_medication(med, text)


def test_source_evidence_from_another_drug_cannot_supply_timing_slots():
    text = 'Panadol mỗi sáng; Augmentin sáng và tối'
    med = Medication(name_raw='Panadol', evidence_text='Panadol mỗi sáng',
                     administrations=[Administration(timing_raw='mỗi sáng', timing_slots_raw=['sáng', 'tối'])])
    with pytest.raises(EvidenceError):
        validate_medication(med, text)
