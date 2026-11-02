from copy import deepcopy
from pathlib import Path

from quizAgent.errors import ValidationError
from .schemas import QUESTION_TYPES, generation_schema
from .validation import validate_draft

PROMPT = (Path(__file__).parent / "prompts" / "generation.txt").read_text()


def generate_quiz(request, rag, llm) -> dict:
    request.validate()
    bundle = rag.retrieve_quiz_evidence(
        course_id=request.course_id, mode=request.mode, topic_id=request.topic_id,
        max_chunks=12, authorized_scope=request.authorized_scope,
    )
    if not bundle.evidence or any(e.course_id != request.course_id for e in bundle.evidence):
        raise ValidationError("Retrieval returned missing or out-of-course evidence.")
    if request.mode == "topic" and any(e.topic != request.topic_id for e in bundle.evidence):
        raise ValidationError("Retrieval returned evidence outside the requested topic.")
    context = {
        "question_counts": dict(request.question_counts),
        "mode": request.mode,
        "topic_id": request.topic_id,
        "evidence": [e.to_dict() for e in bundle.evidence],
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
            validate_draft(draft, request, bundle.evidence)
        except ValidationError as exc:
            if attempt == 1:
                raise ValidationError(f"Quiz generation failed validation after two attempts: {exc}") from exc
            context["validation_feedback"] = str(exc)
            continue
        return {"corpus_version": bundle.corpus_version,
                "questions": deepcopy(draft["questions"])}
    raise AssertionError("Unreachable")
