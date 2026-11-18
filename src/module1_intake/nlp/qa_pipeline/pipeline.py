"""Structured authorities and explicit document Q&A share one grounded composer."""
import re

from ..models import Intent, StrictModel
from ..understanding.providers import OllamaProvider
from ..understanding.validation import fold
from .composition import COMPOSITION_SYSTEM, GroundedComposer, GroundedPlan
from .contracts import Answer, EvidenceRef, RetrievalQuery, RetrievalResult, VerifiedFact
from .rag.interface import DocumentRetriever, DisabledDocumentRetriever
from .structured import APP_HELP, DEFERRED, retrieve_structured



def question_kind(text):
    normalized = fold(text)
    for cue, kind in [('hoat chat', 'ingredients'), ('thanh phan', 'ingredients'),
                      ('ham luong', 'strength'), ('dang', 'dosage_form')]:
        if cue in normalized:
            return kind
    return 'general'


def document_question(text):
    """Read-only knowledge questions; never intercept medication actions or DDI."""
    value = fold(text)
    if re.search(r'\b(?:tuong tac|trung hoat chat|uong chung|dung chung|'
                 r'dang (?:uong|dung)|duoc ke|bac si ke|luu|them thuoc|xac nhan|'
                 r'sua thuoc|nhan dien|dinh danh|xac dinh thuoc|hoat chat|thanh phan|'
                 r'ham luong|dang bao che|ke don|doi lieu|ngung thuoc|chan doan)\b', value):
        return False
    if 'an toan' in value and not re.search(r'\b(?:who|medlineplus|nccih|tai lieu)\b', value):
        return False
    if re.search(r'\b(?:app|ung dung|nhac thuoc|lich su|danh sach thuoc)\b', value):
        return False
    return bool(re.search(r'\b(?:who|medlineplus|nccih|tai lieu|la gi|nhu the nao|'
                          r'can hoi|can biet|co nen|co the|tra cuu|giai thich|huong dan)\b', value) or '?' in text)




class HybridQA:
    def __init__(self, *, medication: DocumentRetriever | None = None, safety: DocumentRetriever | None = None,
                 records=None, composer: GroundedComposer | None = None, documents: DocumentRetriever | None = None):
        self.medication, self.safety, self.records = medication, safety, records
        self.composer = composer or GroundedComposer()
        self.documents = documents if documents is not None else DisabledDocumentRetriever()

    def answer(self, intent: Intent, query: RetrievalQuery) -> Answer:
        if intent in {Intent.CREATE_REMINDER, Intent.GENERATE_PATIENT_SUMMARY, Intent.UNSUPPORTED}:
            return Answer(text=DEFERRED, status='DEFERRED', coverage='NOT_IMPLEMENTED')
        if intent == Intent.MEDICATION_QA and query.kind == 'document':
            result = self.documents.retrieve(query)
        else:
            result = retrieve_structured(intent, query, medication=self.medication,
                                         safety=self.safety, records=self.records)
        return self.composer.compose(query.question, result)
