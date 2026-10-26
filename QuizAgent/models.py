# Proposed internal contracts, not HTTP schemas or runtime validators.
# Drafts and grading requests contain private assessment data. The backend must
# store them privately and construct a separate public response for the browser.

from dataclasses import dataclass
from typing import Literal

QuestionType = Literal["multiple_choice", "true_false", "open_ended"]
Answer = str | bool  # MCQ option ID, true/false Boolean, or free text.


@dataclass(frozen=True)
class AuthorizedScope:
    """Constructed by trusted backend code, never copied from browser input."""

    course_ids: tuple[str, ...]


@dataclass(frozen=True)
class QuizRequest:
    course_id: str
    mode: Literal["random", "topic"]
    topic_id: str | None
    question_counts: dict[QuestionType, int]


@dataclass(frozen=True)
class Evidence:
    chunk_id: str
    document_id: str
    document_version: str
    title: str
    text: str
    topic: str
    page: int | None = None
    source_url: str | None = None


@dataclass(frozen=True)
class EvidenceBundle:
    corpus_version: str
    evidence: tuple[Evidence, ...]


@dataclass(frozen=True)
class RubricCriterion:
    criterion_id: str
    concept: str
    max_points: float


@dataclass(frozen=True)
class QuestionDraft:
    """Private draft; backend assigns authoritative question IDs after validation.

    MCQ uses option IDs such as 'A'; true/false uses bool; open-ended uses a
    reference-answer string and rubric. Type-specific validation is still TODO.
    """

    type: QuestionType
    text: str
    options: dict[str, str]
    correct_answer: Answer
    rubric: tuple[RubricCriterion, ...]
    max_points: float
    explanation: str
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class QuizDraft:
    corpus_version: str
    questions: tuple[QuestionDraft, ...]


@dataclass(frozen=True)
class GradingItem:
    question_id: str
    question: QuestionDraft  # Loaded from protected backend storage.
    student_answer: Answer | None


@dataclass(frozen=True)
class GradingRequest:
    attempt_id: str
    course_id: str
    corpus_version: str
    items: tuple[GradingItem, ...]


@dataclass(frozen=True)
class QuestionGrade:
    question_id: str
    points_awarded: float
    max_points: float
    criteria_scores: dict[str, float]
    feedback: str
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class GradeResult:
    attempt_id: str
    results: tuple[QuestionGrade, ...]
