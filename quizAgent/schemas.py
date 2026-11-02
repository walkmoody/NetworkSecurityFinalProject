"""Requests and JSON output contracts used by both mock and real model clients."""

from dataclasses import dataclass
from copy import deepcopy

from rag.contracts import AuthorizedScope
from .errors import ValidationError

QUESTION_TYPES = ("multiple_choice", "true_false", "open_ended")
MAX_QUESTIONS = 12


@dataclass(frozen=True)
class GenerateQuizRequest:
    course_id: str
    mode: str
    topic_id: str | None
    question_counts: dict[str, int]
    authorized_scope: AuthorizedScope

    def validate(self) -> None:
        if not isinstance(self.course_id, str) or not self.course_id.strip():
            raise ValidationError("course_id is required.")
        self.authorized_scope.require(self.course_id)
        if self.mode not in ("random", "topic"):
            raise ValidationError("mode must be random or topic.")
        if self.mode == "topic" and (not isinstance(self.topic_id, str)
                                    or not self.topic_id.strip()):
            raise ValidationError("Topic mode requires topic_id.")
        if self.mode == "random" and self.topic_id is not None:
            raise ValidationError("Random mode requires topic_id=null.")
        if not isinstance(self.question_counts, dict) or not self.question_counts:
            raise ValidationError("question_counts must be a nonempty object.")
        if set(self.question_counts) - set(QUESTION_TYPES):
            raise ValidationError("Unknown question type.")
        if any(type(n) is not int or n < 0 for n in self.question_counts.values()):
            raise ValidationError("Question counts must be nonnegative integers.")
        if not 1 <= sum(self.question_counts.values()) <= MAX_QUESTIONS:
            raise ValidationError("Request between 1 and 12 questions.")


@dataclass(frozen=True)
class GradeQuizRequest:
    attempt_id: str
    course_id: str
    corpus_version: str
    questions: list[dict]  # Private questions loaded by the backend, with authoritative IDs.
    answers: dict
    authorized_scope: AuthorizedScope


def object_schema(properties: dict) -> dict:
    return {"type": "object", "properties": properties,
            "required": list(properties), "additionalProperties": False}


TEXT = {"type": "string", "minLength": 1, "maxLength": 4000}
POINTS = {"type": "integer", "minimum": 1, "maximum": 10}
RUBRIC = {"type": "array", "maxItems": 8, "items": object_schema({
    "criterion_id": TEXT, "concept": TEXT, "max_points": POINTS,
})}
QUESTION_SCHEMA = object_schema({
    "type": {"type": "string", "enum": list(QUESTION_TYPES)},
    "text": TEXT,
    "options": {"type": "object", "additionalProperties": TEXT},
    "max_points": POINTS,
    "answer_key": object_schema({
        "correct_answer": {"type": ["string", "boolean", "null"]},
        "reference_answer": {"type": ["string", "null"], "maxLength": 4000},
        "rubric": RUBRIC,
        "explanation": TEXT,
        "evidence_ids": {"type": "array", "minItems": 1, "maxItems": 12,
                         "items": TEXT},
    }),
})
QUIZ_DRAFT_SCHEMA = object_schema({
    "questions": {"type": "array", "minItems": 1, "maxItems": MAX_QUESTIONS,
                  "items": QUESTION_SCHEMA},
})


def generation_schema(question_counts: dict[str, int]) -> dict:
    """Constrain decoding to the requested total and each question's legal fields.

    The application still checks the distribution of types and rubric point sums.
    """
    variants = []
    for kind in QUESTION_TYPES:
        if not question_counts.get(kind):
            continue
        question = deepcopy(QUESTION_SCHEMA)
        props = question["properties"]
        props["type"] = {"type": "string", "enum": [kind]}
        key = props["answer_key"]["properties"]
        if kind == "multiple_choice":
            props["options"] = object_schema({label: deepcopy(TEXT) for label in "ABCD"})
            key["correct_answer"] = {"type": "string", "enum": list("ABCD")}
        else:
            props["options"] = object_schema({})
            key["correct_answer"] = {"type": "boolean" if kind == "true_false" else "null"}
        if kind == "open_ended":
            key["reference_answer"] = deepcopy(TEXT)
            key["rubric"]["minItems"] = 1
        else:
            key["reference_answer"] = {"type": "null"}
            key["rubric"]["maxItems"] = 0
        variants.append(question)
    total = sum(question_counts.values())
    return object_schema({"questions": {
        "type": "array", "minItems": total, "maxItems": total,
        "items": {"anyOf": variants},
    }})


OPEN_GRADE_SCHEMA = object_schema({
    "criteria_scores": {"type": "array", "minItems": 1, "maxItems": 8,
                        "items": object_schema({
                            "criterion_id": TEXT,
                            "points": {"type": "integer", "minimum": 0, "maximum": 10},
                        })},
    "feedback": TEXT,
})
