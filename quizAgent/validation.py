"""Validate the schema subset defined in schemas.py plus quiz invariants.

Structural validation and known citation IDs do not prove factual accuracy.
"""

from collections import Counter

from quizAgent.errors import ValidationError
from .schemas import QUIZ_DRAFT_SCHEMA, OPEN_GRADE_SCHEMA


def validate_schema(value, schema: dict, path: str = "output") -> None:
    """Small strict validator for our contracts, not a general JSON Schema engine."""
    types = {"object": dict, "array": list, "string": str, "integer": int,
             "boolean": bool, "null": type(None)}
    expected = schema.get("type")
    expected = expected if isinstance(expected, list) else [expected]
    if not any(type(value) is types[t] for t in expected):
        raise ValidationError(f"{path}: unexpected type.")
    if "enum" in schema and value not in schema["enum"]:
        raise ValidationError(f"{path}: unexpected value.")
    if isinstance(value, dict):
        props = schema.get("properties", {})
        if set(schema.get("required", [])) - set(value):
            raise ValidationError(f"{path}: missing fields.")
        extra = schema.get("additionalProperties", True)
        if extra is False and set(value) - set(props):
            raise ValidationError(f"{path}: unexpected fields.")
        for key, item in value.items():
            rule = props.get(key, extra)
            if isinstance(rule, dict):
                validate_schema(item, rule, f"{path}.{key}")
    elif isinstance(value, list):
        if not schema.get("minItems", 0) <= len(value) <= schema.get("maxItems", 1000):
            raise ValidationError(f"{path}: invalid item count.")
        for item in value:
            validate_schema(item, schema["items"], path + "[]")
    elif isinstance(value, str):
        if not schema.get("minLength", 0) <= len(value) <= schema.get("maxLength", 10000):
            raise ValidationError(f"{path}: invalid text length.")
        if schema.get("minLength", 0) and not value.strip():
            raise ValidationError(f"{path}: blank text.")
    elif type(value) is int:
        if not schema.get("minimum", value) <= value <= schema.get("maximum", value):
            raise ValidationError(f"{path}: number outside bounds.")


def validate_draft(draft: dict, request, evidence) -> None:
    validate_schema(draft, QUIZ_DRAFT_SCHEMA)
    counts = Counter(q["type"] for q in draft["questions"])
    if counts != Counter({k: v for k, v in request.question_counts.items() if v}):
        raise ValidationError("Generated question counts do not match the request.")
    available = {e.chunk_id for e in evidence}
    texts = set()
    for q in draft["questions"]:
        normalized = " ".join(q["text"].lower().split())
        if normalized in texts:
            raise ValidationError("Duplicate question text.")
        texts.add(normalized)
        key = q["answer_key"]
        if not set(key["evidence_ids"]) <= available:
            raise ValidationError("Question cites evidence outside retrieved context.")
        if q["type"] == "multiple_choice":
            if set(q["options"]) != {"A", "B", "C", "D"}:
                raise ValidationError("Multiple-choice questions need options A–D.")
            if len({v.strip().lower() for v in q["options"].values()}) != 4:
                raise ValidationError("Multiple-choice options must be distinct.")
            if type(key["correct_answer"]) is not str or key["correct_answer"] not in q["options"]:
                raise ValidationError("Invalid multiple-choice answer key.")
        elif q["type"] == "true_false":
            if q["options"] or type(key["correct_answer"]) is not bool:
                raise ValidationError("True/false needs a Boolean key and no options.")
        else:
            if q["options"] or key["correct_answer"] is not None:
                raise ValidationError("Open-ended questions cannot have fixed options/keys.")
            if not key["reference_answer"] or not key["reference_answer"].strip() or not key["rubric"]:
                raise ValidationError("Open-ended questions require a reference answer and rubric.")
            ids = [c["criterion_id"] for c in key["rubric"]]
            if len(set(ids)) != len(ids):
                raise ValidationError("Rubric criterion IDs must be unique.")
            if sum(c["max_points"] for c in key["rubric"]) != q["max_points"]:
                raise ValidationError("Rubric points must equal question maximum.")
        if q["type"] != "open_ended" and (key["rubric"] or key["reference_answer"] is not None):
            raise ValidationError("Objective questions cannot contain an open-ended rubric.")


def validate_open_grade(result: dict, rubric: list[dict]) -> None:
    validate_schema(result, OPEN_GRADE_SCHEMA)
    limits = {c["criterion_id"]: c["max_points"] for c in rubric}
    ids = [c["criterion_id"] for c in result["criteria_scores"]]
    if len(ids) != len(set(ids)) or set(ids) != set(limits):
        raise ValidationError("Grading must cover exactly the locked rubric criteria.")
    if any(c["points"] > limits[c["criterion_id"]] for c in result["criteria_scores"]):
        raise ValidationError("Criterion score exceeds its locked maximum.")


def validate_answers(questions: list[dict], answers: dict) -> None:
    if not isinstance(answers, dict) or set(answers) != {q["question_id"] for q in questions}:
        raise ValidationError("Submit exactly one answer for every question ID.")
    for q in questions:
        answer = answers[q["question_id"]]
        if q["type"] == "multiple_choice":
            if type(answer) is not str or answer not in q["options"]:
                raise ValidationError("Multiple-choice answer must be an option ID.")
        elif q["type"] == "true_false":
            if type(answer) is not bool:
                raise ValidationError("True/false answer must be a JSON Boolean.")
        elif type(answer) is not str or not answer.strip() or len(answer) > 4000:
            raise ValidationError("Open-ended answers must contain 1–4000 characters.")
