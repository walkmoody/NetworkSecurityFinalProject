from copy import deepcopy
from pathlib import Path

from quizAgent.errors import ValidationError
from .schemas import QUESTION_TYPES, generation_schema
from .validation import validate_draft
from .evidence import as_evidence, corpus_version, retrieval_course
from rag_pipeline.retriever import retrieve_documents

PROMPT = (Path(__file__).parent / "prompts" / "generation.txt").read_text()


def generate_quiz(request, llm) -> dict:
    request.validate()
    query = request.topic_id if request.mode == "topic" else (
        f"Key concepts and principles in {request.course_id}"
    )
    # Files directly in data/ have no course label; only filter a folder-based index.
    course = retrieval_course(request.course_id)
    documents = retrieve_documents(query, top_k=12, course=course)
    if not documents:
        raise ValidationError("Retrieval returned no evidence for the requested course.")
    if any((d.get("course") or None) != course for d in documents):
        raise ValidationError("Retrieval returned out-of-course evidence.")
    # Preserve the manifest version used by the pipeline's quiz storage contract.
    version = corpus_version()
    evidence = as_evidence(documents, version, request.topic_id, request.course_id)
    context = {
        "question_counts": dict(request.question_counts),
        "mode": request.mode,
        "topic_id": request.topic_id,
        "evidence": evidence,
    }
    plan = [kind for kind in QUESTION_TYPES for _ in range(request.question_counts.get(kind, 0))]
    instructions = PROMPT + "\nRequired question types in order: " + ", ".join(plan)
    instructions += f". Return exactly {len(plan)} questions."
    # One retry for malformed output. Infrastructure errors propagate immediately.
    for attempt in range(2):
        draft = llm.generate_structured(
            task="quiz_generation", instructions=instructions,
            input_data=deepcopy(context), output_schema=generation_schema(request.question_counts),
        )
        try:
            validate_draft(draft, request, evidence)
        except ValidationError as exc:
            if attempt == 1:
                raise ValidationError(f"Quiz generation failed validation after two attempts: {exc}") from exc
            context["validation_feedback"] = str(exc)
            continue
        return {"corpus_version": version,
                "questions": deepcopy(draft["questions"])}
    raise AssertionError("Unreachable")
