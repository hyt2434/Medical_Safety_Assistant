"""Layer 1: read-only structured authorities, application help and owner records."""
import json
import re
from typing import Protocol

from ..models import EntryView, Intent, Medication, StrictModel
from ..integration.persistence import medication
from ..understanding.validation import fold
from .contracts import EvidenceRef, RetrievalQuery, RetrievalResult, VerifiedFact
from .rag.interface import DocumentRetriever, DisabledDocumentRetriever  # Legacy exports.

APP_HELP = ("Nhập tên thuốc và thông tin trên nhãn/đơn: hàm lượng, dạng thuốc, liều, "
            "lịch dùng nếu biết. Xem lại từng mục rồi gõ 'xác nhận'. Thông tin thiếu "
            "được giữ là chưa rõ. Xác nhận chỉ xác nhận nội dung đã nhập. "
            "Module 2 xác minh thuốc; Module 3 đánh giá tương tác khi đủ dữ liệu.")
DEFERRED = ("MVP chưa kết nối nhắc thuốc, tóm tắt sức khỏe hoặc chia sẻ HCP. "
            "Tính năng này chưa được thực hiện. Không tự đổi liều hay ngừng thuốc.")
SAFETY = ("Yêu cầu tương tác được ghi để chuyển tiếp sau xác nhận qua Module 2 rồi Module 3. "
          "Chưa thực hiện đánh giá tương tác; thiếu dữ liệu không có nghĩa là an toàn.")


class Reference(Protocol):
    def lookup(self, fields: dict) -> dict: ...


def reference_answer(reference: Reference | None, fields: dict) -> str:
    if reference is None:
        return "Chưa cấu hình bản dữ liệu Core được duyệt; chưa tra cứu được thông tin thuốc."
    try:
        result = reference.lookup(fields)
    except Exception:
        return "Tra cứu hiện không khả dụng; chưa xác minh được thông tin thuốc."
    candidates = result.get("candidates", [])
    if not result.get("complete_identity") or len(candidates) != 1:
        return "Tên thuốc chưa đủ rõ hoặc chưa có dữ liệu. Hãy cung cấp tên đầy đủ, hàm lượng và dạng thuốc."
    item = candidates[0]
    # CoreMedicationReference exposes supported candidate provenance, not ingredients.
    # Never fill a missing fact from model knowledge or a parallel CSV/SQLite store.
    return ("Tìm thấy ứng viên tham chiếu Core, chưa xác nhận thuốc bạn đang dùng. "
            f"Mã nguồn: {item.get('source_medication_id')}; "
            f"Nguồn: {item.get('source_locator')}. "
            "Giao diện hiện tại chỉ trả ứng viên và nguồn; chưa hỗ trợ trả hoạt chất/"
            "hàm lượng/dạng thuốc để giải đáp. Cần Module 2 xác minh danh tính thuốc.")


class CoreReferenceRetriever:
    """The current Core adapter supplies candidates/provenance, never fabricated facts."""
    def __init__(self, reference):
        self.reference = reference

    def retrieve(self, query):
        result = self.reference.lookup(query.medication)
        return RetrievalResult(status='PARTIAL', coverage='REFERENCE_CANDIDATES_ONLY',
            candidates=[{**c, 'id': str(c['id'])} for c in result.get('candidates', [])],
            limitations=['Core REF interface supplies candidates, not verified ingredient/strength/form facts.',
                         *result.get('limitations', [])])


class Module2FactRetriever:
    """Reuse an existing Module 2 MedicationReference.lookup(), without a new DB layer."""
    def __init__(self, reference):
        self.reference = reference

    def retrieve(self, query):
        result = self.reference.lookup(query.medication)
        candidates = result.get('candidates', [])
        unavailable = RetrievalResult(status='PARTIAL', coverage='IDENTITY_UNRESOLVED',
            candidates=[{'candidate_key': c.get('candidate_key'),
                         'brand_name': c.get('product', {}).get('brand_name')} for c in candidates],
            limitations=['Product identity is not independently verified; no clinical facts were inferred.'])
        if result.get('identification_status') != 'VERIFIED' or len(candidates) != 1:
            return unavailable
        candidate = candidates[0]
        evidence = candidate.get('source_evidence', [])
        if ((candidate.get('independent_review') or {}).get('status') != 'VERIFIED'
                or candidate.get('registration_description_conflict')
                or 'QUARANTINED' in candidate.get('ingestion_statuses', []) or not evidence):
            return unavailable
        if not all(isinstance(e, dict) and re.fullmatch(r'[0-9a-f]{64}', e.get('raw_sha256', ''))
                   and e.get('locator_json') for e in evidence):
            return unavailable
        product = candidate['product']
        fields = {'ingredients': ('ingredients', 'Hoạt chất theo nguồn'),
                  'strength': ('strength', 'Hàm lượng theo nguồn'),
                  'dosage_form': ('dosage_form', 'Dạng thuốc theo nguồn')}
        requested = [fields[query.kind]] if query.kind in fields else list(fields.values())
        facts = []
        for key, label in requested:
            raw = product.get(key)
            if raw is None or raw == '' or raw == []:
                continue
            source = EvidenceRef(source_id='module2:' + candidate['candidate_key'],
                locator=str(evidence[0]['locator_json']), sha256=evidence[0]['raw_sha256'],
                scope='Independently reviewed historical product identity; not current authorization or patient safety')
            facts.append(VerifiedFact(fact_id=key, text=f'{label}: {json.dumps(raw, ensure_ascii=False)}.', source=source))
        return RetrievalResult(status='WORKING' if facts else 'UNAVAILABLE', coverage='HISTORICAL_PRODUCT_IDENTITY',
            facts=facts, limitations=['Historical reference facts do not establish current product authorization or patient-specific safety.'])


class CoreAssessmentRetriever:
    """Read actual Module 3 assessments only; DDInter mapping IDs are never findings."""
    def __init__(self, repo):
        self.repo = repo

    def retrieve(self, query):
        if query.assessment_id is None or len(query.entry_ids) < 2:
            return RetrievalResult(limitations=['No applicable Module 3 assessment is available.'])
        assessment = self.repo._owned('safety_assessments', query.assessment_id)
        rows = self.repo.snapshot_context(assessment['snapshot_id'])
        if set(query.entry_ids) != {r['entry_version_id'] for r in rows}:
            return RetrievalResult(limitations=['Assessment targets differ from the current request.'])
        checks = assessment['check_results']
        facts = []
        for key in ('ddi', 'duplicate_ingredient'):
            check = checks.get(key, {})
            text = f"Module 3 {key}: execution={check.get('execution', 'NOT_STARTED')}; coverage={check.get('coverage', 'UNASSESSED')}."
            facts.append(VerifiedFact(fact_id=key, text=text, required=True, source=EvidenceRef(
                source_id=str(assessment['id']), locator='msa.safety_assessments/' + str(assessment['id']),
                sha256=assessment.get('result_digest'),
                scope='Exact retained assessment and snapshot; never a general statement of safety')))
        findings = self.repo._all('SELECT * FROM msa.safety_findings WHERE assessment_id=%s AND user_id=%s ORDER BY recorded_at,id',
                                  (assessment['id'], self.repo.owner))
        for number, finding in enumerate(findings):
            if not finding.get('evidence'):
                continue
            facts.append(VerifiedFact(fact_id=f'finding:{number}',
                required=True,
                text=f"{finding['finding_type']} ({finding['severity']}): {finding['explanation']}",
                source=EvidenceRef(source_id=str(finding['id']), locator='msa.safety_findings/' + str(finding['id']),
                                   scope='Source-backed finding for the retained snapshot only')))
        complete = assessment['execution_status'] == 'COMPLETED' and all(
            checks.get(key, {}).get('coverage') in {'ASSESSED', 'NOT_APPLICABLE'} for key in ('ddi', 'duplicate_ingredient'))
        return RetrievalResult(status='WORKING' if complete else 'PARTIAL', coverage='ASSESSMENT_SCOPED', facts=facts,
            limitations=list(dict.fromkeys([
                'Missing findings or incomplete coverage never establish safety. Do not change treatment without qualified review.',
                *[reason for key in ('ddi', 'duplicate_ingredient') for reason in checks.get(key, {}).get('limitations', [])]])))


def identification_result(matches):
    """Render Module 2 backend results as facts about identity, never clinical findings."""
    facts, candidates, limitations = [], [], [
        'Reference identity and DDInter mapping availability do not establish patient safety or loaded interaction coverage.']
    for number, (match, result) in enumerate(matches, 1):
        source = EvidenceRef(source_id=str(match['id']), locator='msa.entry_matches/' + str(match['id']),
                             scope='Confirmed-entry Module 2 match; reference identity only')
        facts.append(VerifiedFact(fact_id=f'identity:{number}', required=True, source=source,
            text=f"Thuốc {number}: {result['original_medication'].get('name_raw')}; "
                 f"identity={result['identification_status']}; mapping={result['mapping_status']}; "
                 f"Core={match['match_status']}; candidates={len(result['candidates'])}; "
                 f"build={result.get('dataset_build')}; ready={result['ready_for_identifier_handoff']}."))
        for index, candidate in enumerate(result['candidates'], 1):
            product = candidate.get('product', {})
            view = {'candidate_key': candidate['candidate_key'], 'brand_name': product.get('brand_name'),
                    'strength': product.get('strength'), 'dosage_form': product.get('dosage_form'),
                    'dataset_build': candidate.get('dataset_build'),
                    'source_evidence': candidate.get('source_evidence', [])}
            candidates.append(view)
            loc = candidate.get('source_locator') or {}
            facts.append(VerifiedFact(fact_id=f'candidate:{number}:{index}', required=True,
                text='Ứng viên tham chiếu (không tự chọn khi chưa rõ): ' + json.dumps(
                    {k: v for k, v in view.items() if k != 'source_evidence'}, ensure_ascii=False),
                source=EvidenceRef(source_id=candidate['candidate_key'],
                    locator='msa_ref.medications/' + candidate['candidate_key'], sha256=loc.get('artifact_sha256'),
                    scope='Source-backed reference candidate; selection status is given separately')))
        for index, ingredient in enumerate(result['ingredients'], 1):
            loc = ingredient.get('component_record', {}).get('source_locator', {})
            facts.append(VerifiedFact(fact_id=f'ingredient:{number}:{index}', required=True,
                text=f"Thành phần {number}.{index}: {ingredient['normalized_ingredient']}; "
                     f"strength_raw={ingredient['strength_raw']}; mapping={ingredient['mapping_status']}; "
                     f"DDInter targets={ingredient.get('candidate_ddinter_ids', [])}; "
                     f"mapping_rows={len(ingredient.get('ddinter_mappings', []))}.",
                source=EvidenceRef(source_id=ingredient.get('component_id') or str(match['id']),
                    locator='msa_ref.medication_ingredients/' + str(ingredient.get('component_id')),
                    sha256=loc.get('artifact_sha256'), scope='Retained component and approved mapping evidence; alternatives are not disambiguated')))
        limitations.extend(f"Thuốc {number}: {issue}" for issue in [*result.get('issues', []),
                           *result.get('ingredient_extraction', {}).get('issues', [])])
        for ingredient in result['ingredients']:
            if ingredient.get('unresolved_reason'):
                limitations.append(f"Thuốc {number}: {ingredient['unresolved_reason']}")
    if not matches:
        limitations.append('No non-negated confirmed medication targets are available.')
    complete = bool(matches) and all(result['ready_for_identifier_handoff'] for match, result in matches)
    return RetrievalResult(status='WORKING' if complete else 'PARTIAL', coverage='MEDICATION_IDENTITY_ONLY',
        facts=facts, candidates=candidates, limitations=list(dict.fromkeys(limitations)))


def entry_view(row):
    med = medication(row)
    statuses = {}
    for name in Medication.model_fields:
        if name.endswith('_raw'):
            statuses[name] = ('AMBIGUOUS' if name in med.uncertain_fields else 'MISSING' if getattr(med, name) is None
                              else 'USER_CONFIRMED' if row['confirmed_at'] else 'PRESENT_RAW')
    return EntryView(entry_version_id=row['id'], item_id=row['item_id'], content_digest=row['content_digest'],
                     confirmed=row['confirmed_at'] is not None, medication=med, slot_status=statuses)


class CoreRecords:
    def __init__(self, repo):
        self.repo = repo

    def list(self, *, history=False, limit=100):
        if not 1 <= limit <= 100:
            raise ValueError('Record limit must be between 1 and 100')
        query = ('SELECT * FROM msa.medication_entry_versions WHERE user_id=%s ORDER BY created_at DESC,id LIMIT %s'
                 if history else 'SELECT * FROM (SELECT DISTINCT ON (item_id) * FROM msa.medication_entry_versions '
                 'WHERE user_id=%s ORDER BY item_id,version_no DESC) latest ORDER BY created_at DESC,id LIMIT %s')
        return [entry_view(row) for row in self.repo._all(query, (self.repo.owner, limit))]

    def retrieve(self, query):
        history = 'lich su' in fold(query.question)
        entries = self.list(history=history)
        facts = [VerifiedFact(fact_id=str(entry.entry_version_id),
            text=('Đã xác nhận bản chép: ' if entry.confirmed else 'Bản nháp chưa xác nhận: ')
                 + entry.medication.model_dump_json(),
            source=EvidenceRef(source_id=str(entry.entry_version_id), locator='msa.medication_entry_versions/' + str(entry.entry_version_id),
                               sha256=entry.content_digest,
                               scope='Authenticated owner transcription record, not product verification or safety')) for entry in entries[:16]]
        if not facts:
            facts = [VerifiedFact(fact_id='empty_records', text='Chưa có bản ghi thuốc trong phạm vi truy vấn này.',
                source=EvidenceRef(source_id='owner-record-query', locator='msa.medication_entry_versions',
                                   scope='Authenticated owner records query'))]
        return RetrievalResult(status='WORKING', coverage='OWNER_SCOPED_HISTORY' if history else 'OWNER_SCOPED_RECORDS', facts=facts,
            limitations=['Shown records: up to 16 of the latest 100 versions.' if history else 'Shown records: up to 16 of the latest 100 items.',
                         'Confirmation verifies transcription only.'])


def retrieve_structured(intent, query, *, medication=None, safety=None, records=None):
    """Select an authoritative Layer 1 service, preserving coverage and safe errors."""
    if intent == Intent.APP_HELP:
        return RetrievalResult(status='WORKING', coverage='APPLICATION_FUNCTIONALITY', facts=[VerifiedFact(
            fact_id='app_help', text=APP_HELP, source=EvidenceRef(source_id='module1-help-v2',
                locator='module1_intake.nlp.qa.APP_HELP', scope='Implemented application behavior, not clinical guidance'))])
    adapter = {Intent.MEDICATION_QA: medication, Intent.CHECK_INTERACTION: safety,
               Intent.VIEW_MEDICATIONS: records}.get(intent)
    if adapter is None:
        return RetrievalResult(limitations=['The authoritative service for this request is not configured.'])
    try:
        return adapter.retrieve(query)
    except PermissionError:
        raise
    except Exception:
        return RetrievalResult(limitations=['The authoritative retrieval service is unavailable.'])
