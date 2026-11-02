"""In-process backend stand-in. No HTTP server, real authentication, or persistence.

Callers supply a user ID to simulate an already authenticated session. Never expose
that parameter as an authentication mechanism in a real API.
"""

from copy import deepcopy
from dataclasses import dataclass
from threading import RLock
from uuid import uuid4

from quizAgent.schemas import GenerateQuizRequest, GradeQuizRequest
from quizAgent.validation import validate_answers, validate_open_grade
from rag.contracts import AccessDenied, AuthorizedScope
from .errors import AttemptConflict, ValidationError


@dataclass
class _Attempt:
    owner_id: str
    course_id: str
    quiz_id: str
    draft: dict
    state: str = "ready"
    answers: dict | None = None
    result: dict | None = None


class MockBackend:
    def __init__(self, agent, users: dict[str, tuple[str, ...]] | None = None):
        self.agent = agent
        memberships = users if users is not None else {
            "alice": ("CS5342",), "bob": ("CS5342",), "outsider": (),
        }
        self._users = {user: AuthorizedScope(tuple(courses)) for user, courses in memberships.items()}
        self._attempts: dict[str, _Attempt] = {}
        self._lock = RLock()

    def _scope(self, user_id):
        if user_id not in self._users:
            raise AccessDenied("Unknown mock user.")
        return self._users[user_id]

    def _owned_attempt(self, user_id, attempt_id):
        scope = self._scope(user_id)
        attempt = self._attempts.get(attempt_id)
        if attempt is None or attempt.owner_id != user_id:
            raise AccessDenied("Attempt is unavailable to this user.")
        scope.require(attempt.course_id)
        return attempt

    def create_quiz(self, user_id: str, payload: dict) -> dict:
        scope = self._scope(user_id)
        allowed = {"course_id", "mode", "topic_id", "question_counts"}
        if not isinstance(payload, dict) or set(payload) - allowed:
            raise ValidationError("Unexpected generation fields; scope is backend-controlled.")
        if not {"course_id", "mode", "question_counts"} <= set(payload):
            raise ValidationError("Missing generation settings.")
        request = GenerateQuizRequest(
            payload["course_id"], payload["mode"], payload.get("topic_id"),
            deepcopy(payload["question_counts"]), scope,
        )
        request.validate()
        with self._lock:
            if len(self._attempts) >= 100:
                raise AttemptConflict("Mock storage is full; restart the demo to clear it.")
            draft = deepcopy(self.agent.generate_quiz(request))
            for q in draft["questions"]:
                q["question_id"] = "q_" + uuid4().hex
            attempt_id = "attempt_" + uuid4().hex
            self._attempts[attempt_id] = _Attempt(
                user_id, request.course_id, "quiz_" + uuid4().hex, draft,
            )
            return self.get_quiz(user_id, attempt_id)

    def get_quiz(self, user_id: str, attempt_id: str) -> dict:
        with self._lock:
            attempt = self._owned_attempt(user_id, attempt_id)
            # Explicit public allowlist: never serialize the internal record.
            return {
                "quiz_id": attempt.quiz_id, "attempt_id": attempt_id,
                "course_id": attempt.course_id, "status": attempt.state,
                "questions": [{
                    "question_id": q["question_id"], "type": q["type"],
                    "text": q["text"], "options": deepcopy(q["options"]),
                    "max_points": q["max_points"],
                } for q in attempt.draft["questions"]],
            }

    def submit_answers(self, user_id: str, attempt_id: str, answers: dict) -> dict:
        with self._lock:
            attempt = self._owned_attempt(user_id, attempt_id)
            if attempt.state != "ready":
                raise AttemptConflict("This attempt has already been submitted.")
            validate_answers(attempt.draft["questions"], answers)
            # Lock submitted answers even if model grading fails. Retry uses this copy.
            attempt.answers = deepcopy(answers)
            attempt.state = "submitted"
            return self._grade(attempt_id, attempt)

    def retry_grading(self, user_id: str, attempt_id: str) -> dict:
        with self._lock:
            attempt = self._owned_attempt(user_id, attempt_id)
            if attempt.state != "review_required":
                raise AttemptConflict("Only failed grading can be retried.")
            return self._grade(attempt_id, attempt)

    def _grade(self, attempt_id, attempt):
        try:
            request = GradeQuizRequest(
                attempt_id, attempt.course_id, attempt.draft["corpus_version"],
                deepcopy(attempt.draft["questions"]), deepcopy(attempt.answers),
                self._scope(attempt.owner_id),
            )
            grade = self.agent.grade_quiz(request)
            self._validate_grade(attempt_id, attempt, grade)
            evidence_ids = list(dict.fromkeys(
                eid for q in attempt.draft["questions"] for eid in q["answer_key"]["evidence_ids"]
            ))
            bundle = self.agent.rag.get_evidence_by_ids(
                evidence_ids, attempt.draft["corpus_version"], request.authorized_scope,
            )
            citations = {e.chunk_id: {
                "chunk_id": e.chunk_id, "document_id": e.document_id,
                "document_version": e.document_version, "title": e.title,
                "page": e.page, "source_type": e.source_type, "source_url": e.source_url,
            } for e in bundle.evidence}
            result = {
                "attempt_id": attempt_id, "status": "graded",
                "points_awarded": sum(r["points_awarded"] for r in grade["results"]),
                "max_points": sum(q["max_points"] for q in attempt.draft["questions"]),
                "results": [{
                    "question_id": r["question_id"], "points_awarded": r["points_awarded"],
                    "max_points": r["max_points"], "feedback": r["feedback"],
                    "criteria_scores": deepcopy(r["criteria_scores"]),
                    "citations": [citations[eid] for eid in r["evidence_ids"]],
                } for r in grade["results"]],
            }
        except Exception:
            # Never commit a partial grade. Preserve the exact submitted answers.
            attempt.state = "review_required"
            raise
        attempt.result = deepcopy(result)
        attempt.state = "graded"
        return deepcopy(result)

    def get_result(self, user_id: str, attempt_id: str) -> dict:
        with self._lock:
            attempt = self._owned_attempt(user_id, attempt_id)
            if attempt.state != "graded":
                raise AttemptConflict("No committed grade is available.")
            return deepcopy(attempt.result)

    @staticmethod
    def _validate_grade(attempt_id, attempt, grade):
        if not isinstance(grade, dict) or grade.get("attempt_id") != attempt_id or grade.get("status") != "graded":
            raise ValidationError("Invalid grading envelope.")
        results = grade.get("results")
        questions = {q["question_id"]: q for q in attempt.draft["questions"]}
        if not isinstance(results, list) or len(results) != len(questions):
            raise ValidationError("Grade must contain all questions.")
        seen = set()
        fields = {"question_id", "points_awarded", "max_points", "feedback",
                  "criteria_scores", "evidence_ids"}
        for result in results:
            if not isinstance(result, dict) or set(result) != fields:
                raise ValidationError("Invalid grading result fields.")
            qid = result["question_id"]
            if not isinstance(qid, str) or qid not in questions or qid in seen:
                raise ValidationError("Unexpected or duplicate graded question.")
            seen.add(qid)
            q = questions[qid]
            points = result["points_awarded"]
            if type(points) is not int or not 0 <= points <= q["max_points"]:
                raise ValidationError("Grade exceeds allowed bounds.")
            if type(result["max_points"]) is not int or result["max_points"] != q["max_points"]:
                raise ValidationError("Grade changed the locked maximum.")
            if result["evidence_ids"] != q["answer_key"]["evidence_ids"]:
                raise ValidationError("Grade changed the original citations.")
            if not isinstance(result["feedback"], str) or not 1 <= len(result["feedback"]) <= 8000:
                raise ValidationError("Invalid grading feedback.")
            if q["type"] == "open_ended":
                validate_open_grade({"criteria_scores": result["criteria_scores"],
                                     "feedback": result["feedback"]}, q["answer_key"]["rubric"])
                if points != sum(c["points"] for c in result["criteria_scores"]):
                    raise ValidationError("Grade does not match criterion scores.")
            else:
                expected = q["max_points"] if attempt.answers[qid] == q["answer_key"]["correct_answer"] else 0
                if result["criteria_scores"] != [] or points != expected:
                    raise ValidationError("Objective grade does not match the stored answer key.")
