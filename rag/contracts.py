"""Retrieval interfaces, provenance types, and access scope shared by agents."""

from dataclasses import asdict, dataclass
from typing import Protocol


class RAGError(Exception):
    """Controlled retrieval failure."""


class AccessDenied(RAGError):
    pass


class EvidenceUnavailable(RAGError):
    pass


class RetrievalValidationError(RAGError):
    pass


@dataclass(frozen=True)
class AuthorizedScope:
    course_ids: tuple[str, ...]

    def require(self, course_id: str) -> None:
        if course_id not in self.course_ids:
            raise AccessDenied("Course is outside the authorized scope.")


@dataclass(frozen=True)
class Evidence:
    chunk_id: str
    course_id: str
    document_id: str
    document_version: str
    title: str
    topic: str
    page: int
    text: str
    source_type: str = "sample"
    source_url: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class EvidenceBundle:
    corpus_version: str
    evidence: tuple[Evidence, ...]


class RAGClient(Protocol):
    def retrieve(
        self, *, query: str, course_id: str, max_chunks: int,
        authorized_scope: AuthorizedScope,
    ) -> EvidenceBundle: ...

    def retrieve_quiz_evidence(
        self, *, course_id: str, mode: str, topic_id: str | None,
        max_chunks: int, authorized_scope: AuthorizedScope,
    ) -> EvidenceBundle: ...

    def get_evidence_by_ids(
        self, evidence_ids: list[str], corpus_version: str,
        authorized_scope: AuthorizedScope,
    ) -> EvidenceBundle: ...

