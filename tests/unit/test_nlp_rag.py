"""RAG ingestion, citations and population checks through the existing chatbot."""
import csv
import json
import os
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from module1_intake.nlp.interfaces.application import ApplicationService, ConfirmationRequest, TurnRequest
from module1_intake.nlp.models import Intent
from module1_intake.nlp.qa_pipeline.composition import GroundedComposer
from module1_intake.nlp.qa_pipeline.contracts import RetrievalQuery
from module1_intake.nlp.qa_pipeline.pipeline import HybridQA, document_question
from module1_intake.nlp.qa_pipeline.rag.documents import LocalDocumentRetriever, ROOT
from module1_intake.nlp.understanding.providers import MockProvider, OllamaProvider
from tests.unit.test_nlp import FakeCore


@pytest.fixture
def corpus(tmp_path):
    """Small controlled corpus with real PDF pages and bilingual XML structure."""
    import pymupdf
    raw = tmp_path / 'data/rag/raw'
    raw.mkdir(parents=True)
    sources = [
        ['data/rag/raw/WHO-HIS-SDS-2019.4-eng.pdf', '5 Moments for Medication Safety', '', '', 'en', '2019', 'Patients and caregivers', '', ''],
        ['data/rag/raw/adults.pdf', 'How can I manage my common infection?', '', '', 'en', '2024', 'Adults aged 16 years and over', '16', 'adult'],
        ['data/rag/raw/mplus_topics.xml', 'MedlinePlus Health Topics XML', '', '', 'en;es', '', '', '', ''],
        ['data/rag/raw/NCCIH_Ginger.pdf', 'Ginger', '', '', 'en', '', '', '', ''],
    ]
    with (tmp_path / 'data/rag/sources.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['relative_path', 'title', 'source', 'url', 'language', 'version_or_date', 'audience', 'min_age_years', 'population'])
        writer.writerows(sources)
    with pymupdf.open() as pdf:
        pdf.new_page().insert_text((40, 40), '5 Moments for Medication Safety')
        pdf.new_page().insert_text((40, 40), 'Starting a medication: What is the name of this medication and what is it for?')
        pdf.save(raw / 'WHO-HIS-SDS-2019.4-eng.pdf')
    with pymupdf.open() as pdf:
        pdf.new_page().insert_text((40, 40), 'How can I manage my common infection? A leaflet for adults aged 16 years and over.')
        pdf.save(raw / 'adults.pdf')
    with pymupdf.open() as pdf:
        pdf.new_page()
        pdf.save(raw / 'NCCIH_Ginger.pdf')
    (raw / 'mplus_topics.xml').write_text('''<health-topics>
      <health-topic id="1" language="English" title="Hypothyroidism" url="https://medlineplus.gov/hypothyroidism.html">
      <also-called>Underactive thyroid</also-called><full-summary>&lt;p&gt;Hypothyroidism means your thyroid gland cannot make enough thyroid hormones. It may cause fatigue and weight gain.&lt;/p&gt;</full-summary></health-topic>
      <health-topic id="2" language="Spanish" title="Hipotiroidismo" url="https://medlineplus.gov/spanish/hypothyroidism.html">
      <full-summary>SPANISH_SUMMARY_MUST_NOT_BE_INDEXED and extra words to make a full chunk.</full-summary></health-topic>
      </health-topics>''', encoding='utf-8')
    return tmp_path


def unavailable_html(url):
    raise httpx.ConnectError('offline fixture')


def retriever(corpus, provider=None):
    return LocalDocumentRetriever(root=corpus, provider=provider, fetch_html=unavailable_html)


def turn(service, response, text):
    return service.send(TurnRequest(workflow_id=response.workflow_id, revision=response.revision, text=text))


def test_pdf_page_xml_language_topic_url_and_explicit_skips(corpus):
    docs = retriever(corpus)
    docs._load()
    assert any(p['locator'].endswith('#page=2') for p in docs.passages)
    assert any(p['locator'] == 'https://medlineplus.gov/hypothyroidism.html' for p in docs.passages)
    assert not any('SPANISH_SUMMARY' in p['text'] for p in docs.passages)
    assert any('PDF không có chữ' in issue and 'NCCIH_Ginger.pdf' in issue for issue in docs.issues)
    assert (corpus / 'data/rag/index/corpus.json.gz').is_file()
    answer = docs.retrieve(RetrievalQuery('WHO starting a medication name', 'document'))
    assert answer.facts[0].source.locator.endswith('#page=2')


def test_official_html_replaces_scanned_pdf_and_uses_url(corpus):
    docs = LocalDocumentRetriever(root=corpus, fetch_html=lambda url: '''<html><nav>UNRELATED MENU</nav><main>
      <h2>Background</h2><p>Ginger has been used for health purposes for many years.</p>
      <h2>What Do We Know About Safety?</h2><p>Ginger can cause abdominal discomfort, heartburn, diarrhea,
      and irritation. Talk with your health care provider before using herbal products with any medicine.</p>
      <h2>For More Information</h2>UNRELATED FOOTER</main></html>''')
    docs._load()
    ginger = [p for p in docs.passages if 'NCCIH_Ginger' in p['path']]
    assert ginger and ginger[0]['locator'] == 'https://www.nccih.nih.gov/health/ginger'
    assert not ginger[0]['page'] and 'UNRELATED' not in ginger[0]['text']


def test_vietnamese_search_and_answer_keep_topic_citation(corpus):
    def handler(request):
        payload = json.loads(request.content)
        assert payload['options']['num_ctx'] == 16384
        if 'english_query' in payload['format']['properties']:
            content = {'english_query': 'hypothyroidism underactive thyroid symptoms'}
        elif 'supported' in payload['format']['properties']:
            content = {'supported': [True] * len(json.loads(payload['messages'][1]['content'])['checks'])}
        else:
            quotes = json.loads(payload['messages'][1]['content'])['quotes']
            quote = next(q for q in quotes if 'Hypothyroidism means' in q['text'])
            content = {'statements': [{'quote_id': quote['quote_id'],
                'text_vi': 'Suy giáp là tình trạng tuyến giáp không tạo đủ hormone tuyến giáp.'}]}
        return httpx.Response(200, json={'done': True, 'message': {'content': json.dumps(content)}})
    provider = OllamaProvider('fixture', transport=httpx.MockTransport(handler))
    service = ApplicationService(FakeCore(), provider, documents=retriever(corpus, provider))
    response = turn(service, service.start(), 'Theo MedlinePlus, suy giáp là gì?')
    assert response.qa_results[0].composition == 'QWEN_GROUNDED_DOCUMENT'
    assert 'Suy giáp' in response.assistant_message
    assert response.evidence_refs[0].locator == 'https://medlineplus.gov/hypothyroidism.html'
    assert not response.entries and not response.missing_blockers


@pytest.mark.parametrize('question', [
    'How can I manage my common infection? Bé 3 tuổi dùng được không?',
    'Tài liệu How can I manage my common infection? dành cho người 16 tuổi, áp dụng cho bé 3 tuổi không?',
    'How can I manage my common infection? Trẻ 3 tháng tuổi dùng được không?',
])
def test_child_population_limit_is_backend_enforced(corpus, question):
    service = ApplicationService(FakeCore(), MockProvider(), documents=retriever(corpus))
    response = turn(service, service.start(), question)
    answer = response.qa_results[0]
    assert answer.status == 'UNAVAILABLE' and answer.coverage == 'POPULATION_MISMATCH'
    assert '16 tuổi' in answer.text and 'không áp dụng cho trẻ' in answer.text
    assert answer.evidence_refs[0].locator == 'data/rag/raw/adults.pdf#page=1'


def test_missing_evidence_and_forged_quote_cannot_become_answers(corpus):
    docs = retriever(corpus)
    result = docs.retrieve(RetrievalQuery('quasar galaxy spaceship', 'document'))
    assert not result.facts and result.status == 'UNAVAILABLE'
    result = docs.retrieve(RetrievalQuery('hypothyroidism', 'document'))
    provider = OllamaProvider('fixture', transport=httpx.MockTransport(lambda r: httpx.Response(200,
        json={'done': True, 'message': {'content': json.dumps({'statements': [{'quote_id': 'invented-quote',
            'text_vi': 'KHẲNG ĐỊNH SAI không được xuất hiện.'}]})}})))
    answer = GroundedComposer(provider).compose('Suy giáp là gì?', result)
    assert answer.composition == 'TEMPLATE_FALLBACK' and 'KHẲNG ĐỊNH SAI' not in answer.text


def test_valid_quote_id_with_unsupported_claim_is_rejected(corpus):
    result = retriever(corpus).retrieve(RetrievalQuery('hypothyroidism', 'document'))
    calls = []
    def handler(request):
        payload = json.loads(request.content)
        data = json.loads(payload['messages'][1]['content'])
        calls.append(data)
        if 'checks' in data:
            assert data['checks'][0]['quote'].startswith('Hypothyroidism means')
            content = {'supported': [False]}
        else:
            quote = next(q for q in data['quotes'] if q['text'].startswith('Hypothyroidism means'))
            content = {'statements': [{'quote_id': quote['quote_id'], 'text_vi': 'Uống gừng chữa khỏi suy giáp.'}]}
        return httpx.Response(200, json={'done': True, 'message': {'content': json.dumps(content)}})
    provider = OllamaProvider('fixture', transport=httpx.MockTransport(handler))
    answer = GroundedComposer(provider).compose('Suy giáp là gì?', result)
    assert len(calls) == 2 and answer.status == 'UNAVAILABLE'
    assert answer.composition == 'TEMPLATE_FALLBACK' and 'chữa khỏi' not in answer.text


def test_unnamed_medication_stage_uses_translation_and_specific_section(corpus):
    class SearchProvider:
        def generate_structured(self, *args):
            return json.dumps({'english_query': 'What should I ask the doctor when starting medication?'})
    result = retriever(corpus, SearchProvider()).retrieve(RetrievalQuery(
        'Mới bắt đầu uống thuốc thì mình nên hỏi bác sĩ những gì?', 'document'))
    assert result.facts[0].source.locator.endswith('WHO-HIS-SDS-2019.4-eng.pdf#page=2')
    assert 'Starting a medication' in result.facts[0].text


def test_translated_search_keeps_native_vietnamese_topic_sources(corpus):
    import pymupdf
    manifest = corpus / 'data/rag/sources.csv'
    rows = list(csv.DictReader(manifest.read_text(encoding='utf-8').splitlines()))
    rows[0].update(title='Tìm hiểu bệnh suy giáp', language='vi')
    with manifest.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    with pymupdf.open() as pdf:
        pdf.new_page().insert_text((40, 40), 'Suy giap la tinh trang thieu hormone tuyen giap. Can kham bac si.')
        pdf.save(corpus / rows[0]['relative_path'])
    class SearchProvider:
        def generate_structured(self, *args):
            return json.dumps({'english_query': 'What is hypothyroidism?'})
    result = retriever(corpus, SearchProvider()).retrieve(RetrievalQuery('Suy giáp là gì?', 'document'))
    assert any(f.source.locator.endswith('WHO-HIS-SDS-2019.4-eng.pdf#page=1') for f in result.facts)


def test_child_query_requires_verified_population_not_blank_metadata(corpus):
    # A relevant general topic is still not a verified paediatric care source.
    source = corpus / 'data/rag/raw/mplus_topics.xml'
    source.write_text('<health-topics><health-topic id="3" language="English" title="Cough" '
        'url="https://medlineplus.gov/cough.html"><full-summary>Cough home care for a child: '
        'fluids and rest. Talk to a doctor about persistent cough.</full-summary></health-topic></health-topics>', encoding='utf-8')
    result = retriever(corpus).retrieve(RetrievalQuery('child 3 years old cough home care?', 'document'))
    assert result.status == 'UNAVAILABLE' and not result.facts
    assert any('Chưa đủ bằng chứng' in line for line in result.limitations)


def test_interaction_question_never_queries_rag(corpus):
    class Forbidden:
        def retrieve(self, query):
            pytest.fail('Medication interactions must remain in Module 3')
    text = 'Theo WHO, hai thuốc tôi đang dùng có tương tác không?'
    assert not document_question(text)
    service = ApplicationService(FakeCore(), MockProvider(), documents=Forbidden())
    response = turn(service, service.start(), text)
    assert response.missing_blockers[0]['field_key'] == 'interaction_target'
    answer = HybridQA(documents=Forbidden()).answer(Intent.CHECK_INTERACTION, RetrievalQuery(text, 'document'))
    assert not answer.evidence_refs and answer.status == 'UNAVAILABLE'


def test_document_side_question_preserves_review_and_confirmation(corpus):
    service = ApplicationService(FakeCore(), MockProvider(), documents=retriever(corpus))
    response = turn(service, service.start(task=Intent.ADD_MEDICATION), 'Tôi đang uống Panadol 500mg, dạng viên nén')
    assert response.state == 'AWAITING_CONFIRMATION'
    entry = response.entries[0].entry_version_id
    response = turn(service, response, 'Theo WHO, starting a medication name là gì?')
    assert response.state == 'AWAITING_CONFIRMATION' and response.entries[0].entry_version_id == entry
    confirmed = service.confirm(ConfirmationRequest(workflow_id=response.workflow_id, revision=response.revision,
        request_key=uuid4(), explicit_confirmation=True))
    assert confirmed.entries[0].confirmed
    response = turn(service, confirmed, 'Theo WHO, starting a medication name là gì?')
    assert response.state == 'COMPLETED' and response.entries[0].entry_version_id == entry


@pytest.mark.skipif(os.environ.get('NLP_RUN_REAL_OLLAMA') != '1', reason='Opt-in real Qwen and repository corpus')
@pytest.mark.parametrize('question,locator', [
    ('Mới bắt đầu uống thuốc thì mình nên hỏi bác sĩ những gì?', 'WHO-HIS-SDS-2019.4-eng.pdf#page=6'),
    ('Suy giáp là gì, thường có biểu hiện nào?', 'https://medlineplus.gov/hypothyroidism.html'),
    ('Bé 3 tuổi bị ho thì chăm sóc ở nhà sao?', None),
])
def test_real_qwen_three_questions_through_current_chatbot(question, locator):
    """Real local inference/corpus, existing repository spy; no DB writes."""
    class AuditedQwen(OllamaProvider):
        def generate_structured(self, system, payload, schema):
            raw = super().generate_structured(system, payload, schema)
            plan = json.loads(raw)
            if 'english_query' in plan:
                print('Search translation: ' + plan['english_query'])
            if 'quotes' in payload:
                quotes = {q['quote_id']: q for q in payload['quotes']}
                for statement in plan.get('statements', []):
                    print('Citation audit: ' + json.dumps({
                        'statement': statement, 'quote': quotes.get(statement['quote_id'])}, ensure_ascii=False))
            if 'supported' in plan:
                print('Support verdicts: ' + json.dumps(plan))
            return raw

    provider = AuditedQwen(os.environ.get('NLP_OLLAMA_MODEL', 'qwen3.5:9b'),
        base_url=os.environ.get('NLP_OLLAMA_URL', 'http://127.0.0.1:11434'),
        timeout=float(os.environ.get('NLP_OLLAMA_TIMEOUT', '120')))
    docs = LocalDocumentRetriever(root=ROOT, provider=provider)
    service = ApplicationService(FakeCore(), provider, documents=docs)
    response = turn(service, service.start(), question)
    answer, = response.qa_results
    print('\n' + question + '\n' + answer.text)
    assert not response.entries and not response.missing_blockers
    if locator:
        assert answer.coverage == 'DOCUMENT_EXCERPTS'
        assert any(ref.locator.endswith(locator) for ref in answer.evidence_refs)
        assert answer.composition == 'QWEN_GROUNDED_DOCUMENT'
        if 'Suy giáp' in question:
            assert 'tuyến giáp' in answer.text and any(word in answer.text for word in ('mệt mỏi', 'tăng cân', 'táo bón'))
    else:
        # With no verified paediatric home-care evidence, abstain rather than
        # applying an adult leaflet or an unspecified-age topic to a toddler.
        assert answer.status == 'UNAVAILABLE' and 'chưa đủ bằng chứng' in answer.text.lower()
