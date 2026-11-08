from collections import Counter
from copy import deepcopy
from pathlib import Path

from quizAgent.errors import ValidationError
from .evidence import get_evidence_by_ids
from .schemas import GenerateQuizRequest, OPEN_GRADE_SCHEMA
from .validation import validate_answers, validate_draft, validate_open_grade

PROMPT = (Path(__file__).parent / "prompts" / "grading.txt").read_text()


def grade_quiz(request, llm) -> dict:
    validate_answers(request.questions, request.answers)
    ids = [q["question_id"] for q in request.questions]
    if not ids or len(ids) != len(set(ids)):
        raise ValidationError("Grading requires unique question IDs.")
    evidence_ids = list(dict.fromkeys(
        eid for q in request.questions for eid in q["answer_key"]["evidence_ids"]
    ))
    sources = get_evidence_by_ids(
        evidence_ids, request.corpus_version, request.course_id,
    )
    evidence = {e["chunk_id"]: e for e in sources}
    if (any(e["document_version"] != request.corpus_version for e in sources)
            or set(evidence) != set(evidence_ids)):
        raise ValidationError("Retrieval did not return the original evidence.")
    if any(e["course_id"] != request.course_id for e in sources):
        raise ValidationError("Grading evidence belongs to another course.")
    # Recheck private contracts as well as public submissions.
    counts = dict(Counter(q["type"] for q in request.questions))
    settings = GenerateQuizRequest(request.course_id, "random", None, counts)
    settings.validate()
    private_draft = {"questions": [
        {k: v for k, v in q.items() if k != "question_id"} for q in request.questions
    ]}
    validate_draft(private_draft, settings, sources)
    results = []
    for q in request.questions:
        key = q["answer_key"]
        answer = request.answers[q["question_id"]]
        if q["type"] == "open_ended":
            evaluation = llm.generate_structured(
                task="quiz_grading", instructions=PROMPT,
                input_data={
                    "question": q["text"], "student_answer": answer,
                    "reference_answer": key["reference_answer"],
                    "rubric": deepcopy(key["rubric"]),
                    "evidence": [deepcopy(evidence[eid]) for eid in key["evidence_ids"]],
                }, output_schema=deepcopy(OPEN_GRADE_SCHEMA),
            )
            validate_open_grade(evaluation, key["rubric"])
            scores = evaluation["criteria_scores"]
            points = sum(c["points"] for c in scores)
            feedback = evaluation["feedback"]
        else:
            points = q["max_points"] if answer == key["correct_answer"] else 0
            scores = []
            feedback = ("Correct. " if points else "Incorrect. ") + key["explanation"]
        results.append({
            "question_id": q["question_id"], "points_awarded": points,
            "max_points": q["max_points"], "criteria_scores": scores,
            "feedback": feedback, "evidence_ids": list(key["evidence_ids"]),
        })
    return {"attempt_id": request.attempt_id, "status": "graded", "results": results}
