"""Adapts the team's ChromaDB pipeline (rag_pipeline/) to the RAGClient interface.

Each top-level folder in data/ is a course, e.g. data/NetworkSecurity/ is course
"NetworkSecurity". Chunks are only ever returned for the requested course.

Build the index first: python -m rag_pipeline.build_index
"""

import hashlib
import random

from rag.contracts import (
    AuthorizedScope, Evidence, EvidenceBundle, EvidenceUnavailable, RetrievalValidationError,
)
from rag_pipeline.embeddings import get_collection
from rag_pipeline.integrity import MANIFEST_FILE
from rag_pipeline.retriever import retrieve_documents

# 500-word chunks are long; fewer of them keeps the prompt inside the model's context window.
MAX_CHUNKS = 6
MAX_TEXT = 4000


class PipelineRAG:
    @staticmethod
    def courses() -> list[str]:
        """Courses that have chunks in the knowledge base."""
        metadatas = get_collection().get(include=["metadatas"])["metadatas"]
        return sorted({m["course"] for m in metadatas if m.get("course")})

    @staticmethod
    def _corpus_version() -> str:
        # Tied to the approved-document manifest, so a rebuilt knowledge base invalidates old attempts.
        if not MANIFEST_FILE.exists():
            raise EvidenceUnavailable("Knowledge base not built; run python -m rag_pipeline.build_index.")
        return "manifest-" + hashlib.sha256(MANIFEST_FILE.read_bytes()).hexdigest()[:16]

    def _evidence(self, chunk_id, text, meta, topic) -> Evidence:
        return Evidence(
            chunk_id=chunk_id, course_id=meta["course"], document_id=meta["source"],
            document_version=self._corpus_version(), title=meta["source"], topic=topic,
            page=int(meta["page"]), text=text[:MAX_TEXT], source_type="course",
        )

    def _check(self, course_id, max_chunks, authorized_scope: AuthorizedScope):
        authorized_scope.require(course_id)
        if type(max_chunks) is not int or not 1 <= max_chunks <= 12:
            raise RetrievalValidationError("max_chunks must be between 1 and 12.")
        if not get_collection().get(where={"course": course_id}, limit=1)["ids"]:
            raise EvidenceUnavailable(
                f"No documents for {course_id}; add them to data/{course_id}/ "
                "and run python -m rag_pipeline.build_index."
            )
        return self._corpus_version()

    def retrieve_quiz_evidence(self, *, course_id, mode, topic_id, max_chunks, authorized_scope):
        version = self._check(course_id, max_chunks, authorized_scope)
        limit = min(max_chunks, MAX_CHUNKS)
        if mode == "topic" and topic_id:
            # The pipeline has no topic labels; use semantic search on the topic name instead.
            results = retrieve_documents(topic_id, top_k=limit, course=course_id)
            items = [self._evidence(r["id"], r["text"], r, topic_id) for r in results]
        elif mode == "random":
            stored = get_collection().get(where={"course": course_id}, include=["documents", "metadatas"])
            picks = random.sample(range(len(stored["ids"])), min(limit, len(stored["ids"])))
            items = [self._evidence(stored["ids"][i], stored["documents"][i], stored["metadatas"][i],
                                    stored["metadatas"][i]["source"]) for i in picks]
        else:
            raise RetrievalValidationError("Invalid retrieval mode or topic.")
        return EvidenceBundle(version, tuple(items))

    def retrieve(self, *, query, course_id, max_chunks, authorized_scope):
        version = self._check(course_id, max_chunks, authorized_scope)
        results = retrieve_documents(query, top_k=max_chunks, course=course_id)
        return EvidenceBundle(version, tuple(self._evidence(r["id"], r["text"], r, r["source"]) for r in results))

    def get_evidence_by_ids(self, evidence_ids, corpus_version, authorized_scope):
        if corpus_version != self._corpus_version():
            raise EvidenceUnavailable("Original corpus version is unavailable.")
        if not 1 <= len(evidence_ids) <= 12:
            raise RetrievalValidationError("Request between 1 and 12 evidence IDs.")
        ids = list(dict.fromkeys(evidence_ids))
        stored = get_collection().get(ids=ids, include=["documents", "metadatas"])
        found = {i: (d, m) for i, d, m in zip(stored["ids"], stored["documents"], stored["metadatas"])}
        if set(found) != set(ids):
            raise EvidenceUnavailable("Original evidence is unavailable.")
        for _, meta in found.values():
            authorized_scope.require(meta.get("course", ""))
        # Topic is not stored in the index; grading only checks IDs, course, and text.
        return EvidenceBundle(corpus_version, tuple(
            self._evidence(i, found[i][0], found[i][1], found[i][1]["source"]) for i in ids
        ))
