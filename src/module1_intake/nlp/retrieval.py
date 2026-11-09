"""Read-only adapters over existing authorities; Phase B implements this protocol later."""
from dataclasses import dataclass, field
import json
import re
from typing import Any, Protocol
from uuid import UUID

from pydantic import Field

from .models import StrictModel


class EvidenceRef(StrictModel):
    source_id: str
    locator: str
    scope: str
    sha256: str | None = None


class VerifiedFact(StrictModel):
    fact_id: str
    text: str
    source: EvidenceRef
    required: bool = False  # Backend-only: critical coverage cannot be omitted by composition.


@dataclass(frozen=True)
class RetrievalQuery:
    question: str
    kind: str
    medication: dict[str, Any] = field(default_factory=dict)
    entry_ids: tuple[UUID, ...] = ()
    assessment_id: UUID | None = None


class RetrievalResult(StrictModel):
    status: str = 'UNAVAILABLE'
    coverage: str = 'UNASSESSED'
    facts: list[VerifiedFact] = Field(default_factory=list)
    candidates: list[dict[str, Any]] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class DocumentRetriever(Protocol):
    """Future BGE-M3/FAISS/pgvector adapters return bounded, attributed passages here.

    No documents, indexes, model downloads or clinical authority are supplied by
    this interface. A future document adapter must independently verify its corpus.
    """
    def retrieve(self, query: RetrievalQuery) -> RetrievalResult: ...


class DisabledDocumentRetriever:
    def retrieve(self, query):
        return RetrievalResult(limitations=['Phase B document retrieval is not configured.'])


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
                text=f"{finding['finding_type']} ({finding['severity']}): {finding['explanation']}",
                source=EvidenceRef(source_id=str(finding['id']), locator='msa.safety_findings/' + str(finding['id']),
                                   scope='Source-backed finding for the retained snapshot only')))
        complete = assessment['execution_status'] == 'COMPLETED' and all(
            checks.get(key, {}).get('coverage') in {'ASSESSED', 'NOT_APPLICABLE'} for key in ('ddi', 'duplicate_ingredient'))
        return RetrievalResult(status='WORKING' if complete else 'PARTIAL', coverage='ASSESSMENT_SCOPED', facts=facts,
            limitations=['Missing findings or incomplete coverage never establish safety. Do not change treatment without qualified review.'])
