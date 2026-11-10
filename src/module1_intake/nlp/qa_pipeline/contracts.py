"""Shared Q&A data contracts, without database or model dependencies."""
from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import UUID

from pydantic import Field

from ..models import StrictModel



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
    status: Literal['WORKING', 'PARTIAL', 'UNAVAILABLE', 'DEFERRED'] = 'UNAVAILABLE'
    coverage: str = 'UNASSESSED'
    facts: list[VerifiedFact] = Field(default_factory=list)
    candidates: list[dict[str, Any]] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)




class Answer(StrictModel):
    text: str
    status: Literal['WORKING', 'PARTIAL', 'UNAVAILABLE', 'DEFERRED']
    coverage: str
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    candidates: list[dict] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    composition: str = 'TEMPLATE'
