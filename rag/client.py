"""Read-only fixture retrieval, replaceable with the team's shared vector RAG."""

import json
import random
import re
from pathlib import Path

from .contracts import (
    AuthorizedScope, Evidence, EvidenceBundle, EvidenceUnavailable, RetrievalValidationError,
)


class InMemoryRAG:
    def __init__(self, evidence: list[Evidence], corpus_version: str = "sample-v1",
                 seed: int | None = None):
        if not evidence or len({e.chunk_id for e in evidence}) != len(evidence):
            raise RetrievalValidationError("Corpus must have unique, nonempty evidence.")
        if any(not e.text.strip() or len(e.text) > 4000 for e in evidence):
            raise RetrievalValidationError("Evidence text must contain 1–4000 characters.")
        self._evidence = {e.chunk_id: e for e in evidence}
        self._version = corpus_version
        self._random = random.Random(seed)

    @classmethod
    def sample(cls, seed: int | None = None):
        path = Path(__file__).resolve().parent / "data" / "sample_corpus.json"
        data = json.loads(path.read_text())
        return cls([Evidence(**item) for item in data["evidence"]],
                   data["corpus_version"], seed)

    def retrieve_quiz_evidence(self, *, course_id: str, mode: str,
                              topic_id: str | None, max_chunks: int,
                              authorized_scope: AuthorizedScope) -> EvidenceBundle:
        authorized_scope.require(course_id)
        if type(max_chunks) is not int or not 1 <= max_chunks <= 12:
            raise RetrievalValidationError("max_chunks must be between 1 and 12.")
        if mode not in ("random", "topic") or (mode == "topic" and not topic_id):
            raise RetrievalValidationError("Invalid retrieval mode or topic.")
        candidates = [e for e in self._evidence.values() if e.course_id == course_id
                      and (mode == "random" or e.topic == topic_id)]
        if not candidates:
            raise EvidenceUnavailable("No approved evidence matches this request.")
        # Round-robin shuffled topic groups to avoid one topic dominating random mode.
        groups: dict[str, list[Evidence]] = {}
        for item in candidates:
            groups.setdefault(item.topic, []).append(item)
        topics = list(groups)
        self._random.shuffle(topics)
        for group in groups.values():
            self._random.shuffle(group)
        selected = []
        while topics and len(selected) < max_chunks:
            for topic in topics[:]:
                selected.append(groups[topic].pop())
                if not groups[topic]:
                    topics.remove(topic)
                if len(selected) == max_chunks:
                    break
        return EvidenceBundle(self._version, tuple(selected))

    def retrieve(self, *, query: str, course_id: str, max_chunks: int,
                 authorized_scope: AuthorizedScope) -> EvidenceBundle:
        """Generic Q&A retrieval hook; token overlap substitutes for embeddings."""
        authorized_scope.require(course_id)
        if not isinstance(query, str) or not query.strip() or len(query) > 4000:
            raise RetrievalValidationError("Query must contain 1–4000 characters.")
        if type(max_chunks) is not int or not 1 <= max_chunks <= 12:
            raise RetrievalValidationError("max_chunks must be between 1 and 12.")
        terms = set(re.findall(r"[a-z0-9]+", query.lower()))
        ranked = []
        for item in self._evidence.values():
            if item.course_id == course_id:
                words = set(re.findall(r"[a-z0-9]+", f"{item.topic} {item.text}".lower()))
                score = len(terms & words)
                if score:
                    ranked.append((score, item))
        ranked.sort(key=lambda pair: (-pair[0], pair[1].chunk_id))
        if not ranked:
            raise EvidenceUnavailable("No sample evidence matches the query.")
        return EvidenceBundle(self._version, tuple(e for _, e in ranked[:max_chunks]))

    def get_evidence_by_ids(self, evidence_ids: list[str], corpus_version: str,
                            authorized_scope: AuthorizedScope) -> EvidenceBundle:
        if corpus_version != self._version:
            raise EvidenceUnavailable("Original corpus version is unavailable.")
        if not 1 <= len(evidence_ids) <= 12:
            raise RetrievalValidationError("Request between 1 and 12 evidence IDs.")
        result = []
        for chunk_id in dict.fromkeys(evidence_ids):
            item = self._evidence.get(chunk_id)
            if item is None:
                raise EvidenceUnavailable("Original evidence is unavailable.")
            authorized_scope.require(item.course_id)
            result.append(item)
        return EvidenceBundle(self._version, tuple(result))
