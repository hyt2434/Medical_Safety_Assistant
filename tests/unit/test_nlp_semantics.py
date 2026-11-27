"""Source-backed intent and timing regressions. All inference here is mocked."""
import json
import unicodedata

import pytest

from module1_intake.nlp.interfaces.interactive import format_understanding
from module1_intake.nlp.models import Administration, Intent, IntentCandidate, Medication, Understanding
from module1_intake.nlp.understanding.providers import InferenceCategory, InferenceError, MockProvider, understand
from module1_intake.nlp.understanding.routing import detect
from module1_intake.nlp.understanding.validation import (
    EvidenceError, align_medication_evidence, validate_medication, validate_understanding,
)
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


@pytest.mark.parametrize('name', ['Panadol', 'Alltrex', 'X'])
def test_attribute_label_in_report_is_not_a_reference_question(name):
    text = f'Tôi đang uống thuốc {name}, hàm lượng 500 mg, dạng viên nén.'
    # A model-proposed QA intent must not override the declarative source text.
    raw = Understanding(intents=[IntentCandidate(intent=Intent.MEDICATION_QA, evidence_text=text)],
        medications=[Medication(name_raw=name, strength_raw='500 mg', dosage_form_raw='viên nén', evidence_text=text)])
    assert detect(text, raw) == [Intent.ADD_MEDICATION]
    repo, bot, reply = conversation(MockProvider([raw.model_dump_json()]))
    reply = send(bot, reply, text)
    assert reply.state == 'AWAITING_CONFIRMATION'
    assert len(repo.tables['medication_entry_versions']) == 1


def test_strength_question_overrides_model_intake_but_preserves_mixed_request():
    question = 'Thuốc X có hàm lượng bao nhiêu?'
    value = Understanding(intents=[IntentCandidate(intent=Intent.ADD_MEDICATION, evidence_text=question)],
        medications=[Medication(name_raw='X', evidence_text=question)])
    assert detect(question, value) == [Intent.MEDICATION_QA]
    _, bot, reply = conversation(MockProvider([value.model_dump_json()]))
    reply = send(bot, reply, question)
    assert bot.store.entries(bot.store.workflow(reply.workflow_id)) == []
    assert set(detect('Tôi đang uống X 500 mg. Thuốc này có hoạt chất là gì?', value)) == {
        Intent.ADD_MEDICATION, Intent.MEDICATION_QA}


@pytest.mark.parametrize('candidate', ['Alpha', 'Alpha Viên Sủi', '"Alpha Viên Sủi"'])
def test_explicit_name_label_keeps_full_source_product_name(candidate):
    text = 'Tôi đang uống thuốc tên "Alpha Viên Sủi", hàm lượng 500 mg, dạng viên sủi.'
    med = validate_medication(Medication(name_raw=candidate, strength_raw='500 mg',
        dosage_form_raw='viên sủi', evidence_text=text), text)
    assert med.name_raw == 'Alpha Viên Sủi' and med.evidence_text == text


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


def test_omitted_duration_preserves_only_an_explicit_grounded_source_span():
    source = unicodedata.normalize('NFD', 'A 500mg, dùng trong 7 ngày.')
    original = Medication(name_raw='A', evidence_text=source)
    med = validate_medication(original, source)
    assert med.duration_raw == unicodedata.normalize('NFD', 'trong 7 ngày')
    assert original.duration_raw is None


@pytest.mark.parametrize('source', ['A 500mg', 'A 500mg, ngày 2 lần', 'A 500mg, 7 ngày',
    'A trong 7 đến 10 ngày', 'A trong 7 ngày hoặc 10 ngày', 'A trong 7 ngày, sau đó trong 3 ngày'])
def test_duration_projection_does_not_invent_or_select_ambiguous_details(source):
    assert validate_medication(Medication(name_raw='A', evidence_text=source), source).duration_raw is None


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


@pytest.mark.parametrize('strength', ['năm trăm miligam', 'hai trăm microgam',
    'mười hai phẩy năm miligam', 'nửa gam', '500 mg'])
def test_spoken_strengths_keep_original_source_and_dose(strength):
    text = f'Tôi đang uống Example {strength}, dạng viên nén, mỗi sáng một viên'
    med = Medication(name_raw='Example', strength_raw=strength, dosage_form_raw='viên nén',
                     dose_raw='một viên', evidence_text=text)
    assert validate_medication(med, text).strength_raw == strength
    assert validate_medication(med, text).dose_raw == 'một viên'


def test_spoken_strength_through_chatbot_and_dose_only_followup():
    text = 'Tôi đang uống Panadol năm trăm miligam, dạng viên nén, mỗi sáng một viên'
    repo, bot, reply = conversation()
    reply = send(bot, reply, text)
    assert reply.state == 'AWAITING_CONFIRMATION'
    med = bot.store.entries(bot.store.workflow(reply.workflow_id))[0]['medication_fields']
    assert med['strength_raw'] == 'năm trăm miligam' and med['dose_raw'] == 'một viên'
    assert med['evidence_text'] == text
    assert all(row['confirmed_at'] is None for row in repo.tables['medication_entry_versions'].values())

    _, bot, reply = conversation()
    reply = send(bot, reply, 'Tôi đang uống Panadol, dạng viên nén')
    reply = send(bot, reply, 'mỗi sáng một viên')
    med = bot.store.entries(bot.store.workflow(reply.workflow_id))[0]['medication_fields']
    assert med['strength_raw'] is None and med['dose_raw'] == 'một viên'
    assert reply.state == 'CLARIFYING'


def test_spoken_strength_preserves_decomposed_accents_and_rejects_invented_normalization():
    text = unicodedata.normalize('NFD', 'Example năm trăm miligam, mỗi sáng một viên')
    strength = unicodedata.normalize('NFD', 'năm trăm miligam')
    assert validate_medication(Medication(strength_raw=strength, evidence_text=text), text).strength_raw == strength
    with pytest.raises(EvidenceError):
        validate_medication(Medication(strength_raw='500 mg', evidence_text=text), text)
    with pytest.raises(EvidenceError):
        validate_medication(Medication(strength_raw='một viên', evidence_text='mỗi sáng một viên'), 'mỗi sáng một viên')


@pytest.mark.parametrize('clauses,fields', [
    (['Tôi đang uống Panadol 500mg, mỗi sáng 1 viên, bác sĩ kê 2 hộp',
      'đang dùng Vitamin C 100mg, mỗi tối 2 viên, bác sĩ kê 1 hộp.'],
     [('Panadol', '500mg', '1 viên', '2 hộp', 'mỗi sáng'),
      ('Vitamin C', '100mg', '2 viên', '1 hộp', 'mỗi tối')]),
    (['Tôi đang uống Core Fixture 0 0,5g', 'đang dùng Core Fixture 2 0,5g'],
     [('Core Fixture 0', '0,5g', None, None, None), ('Core Fixture 2', '0,5g', None, None, None)]),
    (['Không dùng Alpha 500mg, mỗi sáng 1 viên', 'Có lẽ dùng Beta 500mg, mỗi tối 1 viên'],
     [('Alpha', '500mg', '1 viên', None, 'mỗi sáng'), ('Beta', '500mg', '1 viên', None, 'mỗi tối')]),
])
@pytest.mark.parametrize('separator', ['; ', '\n'])
def test_recorded_broad_evidence_is_narrowed_once_without_changing_raw_values(clauses, fields, separator):
    """The two observed Qwen failures plus equal-amount/qualifier regressions."""
    text = separator.join(clauses)
    meds = [Medication(name_raw=name, strength_raw=strength, dose_raw=dose, quantity_raw=quantity,
        administrations=[Administration(timing_raw=timing, dose_raw=dose)] if timing else [],
        evidence_text=text if index == 0 else clauses[index])
        for index, (name, strength, dose, quantity, timing) in enumerate(fields)]
    raw = Understanding(medications=meds)
    before = raw.model_dump_json()
    with pytest.raises(EvidenceError, match='Overlapping'):
        validate_understanding(raw, text)  # The validator itself stays strict.
    provider = MockProvider([before])
    value = understand(provider, text, {}, attempts=1)
    assert provider.calls == 1 and raw.model_dump_json() == before
    assert [m.evidence_text for m in value.medications] == clauses
    for med, (name, strength, dose, quantity, timing) in zip(value.medications, fields):
        assert (med.name_raw, med.strength_raw, med.dose_raw, med.quantity_raw) == (name, strength, dose, quantity)
        assert [a.timing_raw for a in med.administrations] == ([timing] if timing else [])
    if text.startswith('Không'):
        assert value.medications[0].negation_raw == 'Không dùng'
        assert value.medications[1].uncertainty_raw == 'Có lẽ'
    assert validate_understanding(value, text) == value


@pytest.mark.parametrize('case', ['foreign_strength', 'foreign_dose', 'invented_evidence', 'omitted_negation', 'ambiguous_name'])
def test_evidence_alignment_cannot_rescue_wrong_attribution_or_invented_spans(case):
    text = 'Không dùng Alpha 500mg, mỗi sáng 1 viên; Beta 100mg, mỗi tối 2 viên'
    first = Medication(name_raw='Alpha', strength_raw='500mg', dose_raw='1 viên', evidence_text=text)
    second = Medication(name_raw='Beta', strength_raw='100mg', dose_raw='2 viên', evidence_text=text.split('; ')[1])
    if case == 'foreign_strength': first.strength_raw = '100mg'
    if case == 'foreign_dose': first.dose_raw = '2 viên'
    if case == 'invented_evidence': first.evidence_text = 'invented'
    if case == 'omitted_negation': first.evidence_text = 'Alpha 500mg, mỗi sáng 1 viên'
    if case == 'ambiguous_name':
        text = text.replace('Beta', 'Alpha')
        first.evidence_text = text
        second.name_raw, second.evidence_text = 'Alpha', text.split('; ')[1]
    raw = Understanding(medications=[first, second])
    assert align_medication_evidence(raw, text) == raw
    with pytest.raises(InferenceError) as caught:
        understand(MockProvider([raw.model_dump_json()]), text, {}, attempts=1)
    assert caught.value.category == InferenceCategory.EVIDENCE


def test_prescribed_quantity_in_next_sentence_stays_with_its_medication():
    clauses = ['Alpha 10mg. Bác sĩ kê 2 hộp.', 'Beta 10mg. Bác sĩ kê 1 hộp.']
    text = '; '.join(clauses)
    raw = Understanding(medications=[Medication(name_raw=name, strength_raw='10mg',
        quantity_raw=quantity, evidence_text=text) for name, quantity in [('Alpha', '2 hộp'), ('Beta', '1 hộp')]])
    value = understand(MockProvider([raw.model_dump_json()]), text, {}, attempts=1)
    assert [m.evidence_text for m in value.medications] == clauses
    assert [m.quantity_raw for m in value.medications] == ['2 hộp', '1 hộp']


def test_already_bounded_second_span_does_not_block_first_span_repair():
    text = 'Alpha 10mg; đang dùng Beta 20mg.'
    raw = Understanding(medications=[Medication(name_raw='Alpha', strength_raw='10mg', evidence_text=text),
        Medication(name_raw='Beta', strength_raw='20mg', evidence_text='Beta 20mg')])
    value = understand(MockProvider([raw.model_dump_json()]), text, {}, attempts=1)
    assert [m.evidence_text for m in value.medications] == ['Alpha 10mg', 'Beta 20mg']


@pytest.mark.parametrize('text', [
    'Alpha 500mg và Beta 100mg, cả hai mỗi sáng 1 viên',
    'Alpha 500mg; Beta 100mg, cả hai mỗi sáng 1 viên',
])
def test_shared_information_requires_restatement_without_distributing_or_losing_source(text):
    # A genuine shared phrase has no two disjoint, complete per-drug spans in
    # the current DTO. Keep the original message and request explicit per-drug input.
    raw = Understanding(medications=[Medication(name_raw=name, strength_raw=strength,
        dose_raw='1 viên', administrations=[Administration(timing_raw='mỗi sáng', dose_raw='1 viên')],
        evidence_text=text) for name, strength in [('Alpha', '500mg'), ('Beta', '100mg')]])
    held = align_medication_evidence(raw, text)
    assert held.ambiguous and not held.medications
    repo, bot, reply = conversation(MockProvider([raw.model_dump_json()] * 2))
    reply = send(bot, reply, text)
    assert reply.state == 'CLARIFYING' and 'thông tin dùng chung' in reply.text
    assert not repo.tables.get('medication_entry_versions')
    assert not repo.tables.get('entry_matches') and not repo.tables.get('safety_assessments')
    assert any(r['text_content'] == text for r in repo.tables['conversation_messages'].values())


def test_omitted_shared_instruction_is_not_silently_lost_after_clause_alignment():
    text = 'Alpha 500mg; Beta 100mg, cả hai mỗi sáng 1 viên'
    raw = Understanding(medications=[Medication(name_raw='Alpha', strength_raw='500mg', evidence_text='Alpha 500mg'),
        Medication(name_raw='Beta', strength_raw='100mg', evidence_text='Beta 100mg, cả hai mỗi sáng 1 viên')])
    provider = MockProvider([raw.model_dump_json()])
    value = understand(provider, text, {}, attempts=1)
    assert provider.calls == 1 and value.ambiguous and not value.medications


def test_explicit_shared_ambiguity_cannot_make_partial_medication_entries():
    text = 'Alpha và Beta, mỗi thuốc 1 viên mỗi sáng'
    raw = Understanding(ambiguous=True)
    repo, bot, reply = conversation(MockProvider([raw.model_dump_json()]))
    reply = send(bot, reply, text)
    assert reply.state == 'CLARIFYING' and 'thông tin dùng chung' in reply.text
    assert not repo.tables.get('medication_entry_versions')


def test_shared_information_restatement_reaches_review_then_explicit_confirmation():
    shared = 'Alpha và Beta, mỗi thuốc 1 viên mỗi sáng'
    clauses = ['Tôi đang dùng Alpha 500mg, dạng viên nén, mỗi sáng 1 viên',
               'đang dùng Beta 100mg, dạng viên nén, mỗi sáng 1 viên']
    corrected = '; '.join(clauses)
    raw = Understanding(medications=[Medication(name_raw=name, strength_raw=strength,
        dosage_form_raw='viên nén', dose_raw='1 viên', evidence_text=clause,
        administrations=[Administration(timing_raw='mỗi sáng', dose_raw='1 viên')])
        for name, strength, clause in zip(('Alpha', 'Beta'), ('500mg', '100mg'), clauses)])
    repo, bot, reply = conversation(MockProvider([Understanding(ambiguous=True).model_dump_json(), raw.model_dump_json()]))
    reply = send(bot, reply, shared)
    assert reply.state == 'CLARIFYING' and not repo.tables.get('medication_entry_versions')
    reply = send(bot, reply, corrected)
    assert reply.state == 'AWAITING_CONFIRMATION'
    entries = bot.store.entries(bot.store.workflow(reply.workflow_id))
    assert len(entries) == 2 and all(row['confirmed_at'] is None for row in entries)
    assert all(row['medication_fields']['dose_raw'] == '1 viên' for row in entries)
    assert not repo.tables.get('entry_matches') and not repo.tables.get('safety_assessments')
    reply = send(bot, reply, 'xác nhận')
    assert reply.state == 'COMPLETED' and len(reply.handoff.entries) == 2
    assert all(entry.medication.administrations[0].timing_raw == 'mỗi sáng' for entry in reply.handoff.entries)
