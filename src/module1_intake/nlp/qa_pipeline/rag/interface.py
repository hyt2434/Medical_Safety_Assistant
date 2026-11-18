"""Shared retrieval seam for structured authorities and local RAG."""
from typing import Protocol

from ..contracts import RetrievalQuery, RetrievalResult



class DocumentRetriever(Protocol):
    """Adapters return bounded, attributed passages through the shared contract."""
    def retrieve(self, query: RetrievalQuery) -> RetrievalResult: ...




class DisabledDocumentRetriever:
    def retrieve(self, query):
        return RetrievalResult(limitations=['Phase B document retrieval is not configured.'])
