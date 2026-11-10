"""Future document retrieval seam; Phase A never calls this adapter."""
from typing import Protocol

from ..contracts import RetrievalQuery, RetrievalResult



class DocumentRetriever(Protocol):
    """Future BGE-M3/FAISS/pgvector adapters return bounded, attributed passages here.

    No documents, indexes, model downloads or clinical authority are supplied by
    this interface. A future document adapter must independently verify its corpus.
    """
    def retrieve(self, query: RetrievalQuery) -> RetrievalResult: ...




class DisabledDocumentRetriever:
    def retrieve(self, query):
        return RetrievalResult(limitations=['Phase B document retrieval is not configured.'])
