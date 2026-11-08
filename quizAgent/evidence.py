"""Original evidence and citations from the shared pipeline's Chroma collection."""

import hashlib

from rag_pipeline.embeddings import get_collection
from rag_pipeline.integrity import MANIFEST_FILE
from .errors import EvidenceUnavailable, ValidationError


def corpus_version():
    try:
        manifest = MANIFEST_FILE.read_bytes()
    except FileNotFoundError as exc:
        raise EvidenceUnavailable("Knowledge base not built; run python -m rag_pipeline.build_index.") from exc
    return "manifest-" + hashlib.sha256(manifest).hexdigest()[:16]


def retrieval_course(course_id, collection=None):
    """Flat data/ files form one corpus; course folders require an exact match."""
    collection = collection if collection is not None else get_collection()
    metadata = collection.get(include=["metadatas"])["metadatas"]
    if not metadata:
        raise EvidenceUnavailable("Vector database is empty; run python -m rag_pipeline.build_index.")
    courses = {m.get("course") for m in metadata if m.get("course")}
    if not courses:
        return None
    if course_id not in courses:
        raise EvidenceUnavailable(
            f"No indexed documents for course {course_id!r}. Available courses: {', '.join(sorted(courses))}."
        )
    return course_id


def as_evidence(documents, version, topic=None, course_id=None):
    return [{
        "chunk_id": d["id"], "course_id": d.get("course") or course_id,
        "document_id": d["source"], "document_version": version,
        "title": d["source"], "topic": topic or d["source"],
        "page": d["page"], "text": d["text"], "source_type": "course",
        "source_url": None,
    } for d in documents]


def get_evidence_by_ids(evidence_ids, version, course_id):
    """Retrieve the quiz's original sources, never substitute a new semantic match."""
    if not isinstance(course_id, str) or not course_id.strip():
        raise ValidationError("course_id is required.")
    if not 1 <= len(evidence_ids) <= 12:
        raise ValidationError("Request between 1 and 12 evidence IDs.")
    if version != corpus_version():
        raise EvidenceUnavailable("Original corpus version is unavailable.")
    ids = list(dict.fromkeys(evidence_ids))
    collection = get_collection()
    course = retrieval_course(course_id, collection)
    stored = collection.get(ids=ids, where={"course": course} if course else None,
                            include=["documents", "metadatas"])
    found = {chunk_id: {**meta, "id": chunk_id, "text": text}
             for chunk_id, text, meta in zip(stored["ids"], stored["documents"], stored["metadatas"])}
    if set(found) != set(ids) or any((d.get("course") or None) != course for d in found.values()):
        raise EvidenceUnavailable("Original evidence is unavailable for this course.")
    return as_evidence([found[chunk_id] for chunk_id in ids], version, course_id=course_id)
