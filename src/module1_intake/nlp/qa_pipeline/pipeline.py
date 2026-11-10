"""Phase A orchestration: structured retrieval, then grounded composition only."""
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




class HybridQA:
    def __init__(self, *, medication: DocumentRetriever | None = None, safety: DocumentRetriever | None = None,
                 records=None, composer: GroundedComposer | None = None, documents: DocumentRetriever | None = None):
        self.medication, self.safety, self.records = medication, safety, records
        self.composer = composer or GroundedComposer()
        self.documents = documents or DisabledDocumentRetriever()  # Phase B boundary only; not searched in Phase A.

    def answer(self, intent: Intent, query: RetrievalQuery) -> Answer:
        if intent in {Intent.CREATE_REMINDER, Intent.GENERATE_PATIENT_SUMMARY, Intent.UNSUPPORTED}:
            return Answer(text=DEFERRED, status='DEFERRED', coverage='NOT_IMPLEMENTED')
        result = retrieve_structured(intent, query, medication=self.medication,
                                     safety=self.safety, records=self.records)
        return self.composer.compose(query.question, result)
