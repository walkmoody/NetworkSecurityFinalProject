"""HTTP layer between the React frontend and the Quiz Agent.

Run from repository root: uvicorn backend.app:app --host 127.0.0.1 --port 8000
Set QUIZ_LLM=mock to run without Ollama. Quizzes always use the rag_pipeline ChromaDB knowledge base.
"""

import logging
import os
import secrets
from threading import Lock

from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.tracing import TracedQuizAgent, step, stream
from llm import MockLLM, OllamaClient
from llm.contracts import ModelError
from quizAgent.errors import AccessDenied, AttemptConflict, QuizError, ValidationError
from quizAgent.mock_backend import MockBackend
from rag_pipeline.embeddings import get_collection
from tutorAgent import TutorAgent, TutorError

SESSION_COOKIE = "quiz_session"
MAX_SESSIONS = 1000

log = logging.getLogger("backend")
use_mock = os.environ.get("QUIZ_LLM", "ollama").lower() == "mock"
model = MockLLM() if use_mock else OllamaClient()



def list_courses() -> list[str]:
    """Course folders in data/ that rag_pipeline.build_index has indexed."""
    metadatas = get_collection().get(include=["metadatas"])["metadatas"]
    return sorted({m["course"] for m in metadatas if m.get("course")})


# Reports each rag_pipeline, model, and agent call while a request runs (see backend/tracing.py).
agent = TracedQuizAgent(model)

# One MockBackend per browser session keeps attempts isolated between users.
# The user ID inside each backend is fixed server-side, never taken from the client.
_sessions: dict[str, MockBackend] = {}
_sessions_lock = Lock()

app = FastAPI(title="Network Security Tutor API", docs_url=None, redoc_url=None)


def _session(request: Request, response: Response) -> MockBackend:
    token = request.cookies.get(SESSION_COOKIE)
    with _sessions_lock:
        if token in _sessions:
            return _sessions[token]
        if len(_sessions) >= MAX_SESSIONS:
            raise AttemptConflict("Too many active sessions; restart the server.")
        token = secrets.token_urlsafe(32)
        # A session may use every course indexed when it starts; restart to pick up new courses.
        _sessions[token] = MockBackend(agent, {"student": tuple(list_courses())})
    response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="strict")
    return _sessions[token]


def _error(exc: Exception) -> tuple[int, str]:
    """Status and user-safe message for an error, shared by JSON and streamed responses."""
    if isinstance(exc, ValidationError):
        return 400, str(exc)
    if isinstance(exc, AttemptConflict):
        return 409, str(exc)
    if isinstance(exc, AccessDenied):
        return 403, str(exc)
    if isinstance(exc, QuizError):  # EvidenceUnavailable and other quiz workflow failures
        return 422, str(exc)
    if isinstance(exc, ModelError):
        log.warning("Model error: %s", exc)
        return 502, "The local model is unavailable or returned an invalid response."
    log.error("Unexpected error", exc_info=exc)
    return 500, "Unexpected server error."


def _error_response(_, exc):
    status, detail = _error(exc)
    return JSONResponse({"detail": detail}, status_code=status)


for _exc_type in (QuizError, ModelError, Exception):
    app.add_exception_handler(_exc_type, _error_response)


def _streamed(work, response: Response):
    """Stream progress steps, then the result; keep any session cookie set for this request."""
    streaming = stream(work, _error)
    streaming.raw_headers.extend(h for h in response.raw_headers if h[0] == b"set-cookie")
    return streaming


class CreateQuizBody(BaseModel):
    course_id: str
    mode: str
    topic_id: str | None = None
    question_counts: dict[str, int]


class SubmitBody(BaseModel):
    answers: dict[str, str | bool]


@app.get("/api/health")
def health():
    return {"mode": "mock"} if use_mock else model.check_connection()


@app.get("/api/courses")
def courses():
    return {"courses": list_courses()}


# Quiz endpoints stream NDJSON: {"type": "step", ...} lines while the agent works, then one
# {"type": "result", "data": ...} or {"type": "error", "status": ..., "detail": ...} line.
@app.post("/api/quiz")
def create_quiz(body: CreateQuizBody, request: Request, response: Response):
    backend = _session(request, response)

    def work():
        with step("MockBackend.create_quiz — generating the quiz; answer keys stay on the server"):
            return backend.create_quiz("student", {
                "course_id": body.course_id, "mode": body.mode, "topic_id": body.topic_id,
                "question_counts": body.question_counts,
            })
    return _streamed(work, response)


@app.post("/api/quiz/{attempt_id}/submit")
def submit_answers(attempt_id: str, body: SubmitBody, request: Request, response: Response):
    backend = _session(request, response)

    def work():
        with step("MockBackend.submit_answers — locking your answers, grading, and attaching citations"):
            return backend.submit_answers("student", attempt_id, body.answers)
    return _streamed(work, response)


@app.post("/api/quiz/{attempt_id}/retry")
def retry_grading(attempt_id: str, request: Request, response: Response):
    backend = _session(request, response)

    def work():
        with step("MockBackend.retry_grading — grading your locked answers again"):
            return backend.retry_grading("student", attempt_id)
    return _streamed(work, response)


class TutorBody(BaseModel):
    question: str
    course_id: str
    internet_assisted: bool = False


@app.post("/api/tutor/ask")
def ask_tutor(body: TutorBody):
    """Use the same runtime and course index as Quiz, without another server."""
    if body.course_id not in list_courses():
        raise HTTPException(status_code=403, detail="This course is not in the approved knowledge base.")
    if use_mock:
        raise HTTPException(status_code=503, detail="Tutor requires an available local Ollama model.")
    from rag_pipeline.retriever import retrieve_documents

    tutor = TutorAgent(
        course_id=body.course_id, llm_client=model,
        retriever=lambda query, top_k: retrieve_documents(
            query, top_k=top_k, course=body.course_id, expand_titles=True
        ),
    )
    try:
        return tutor.ask(body.question, course_id=body.course_id, internet_assisted=body.internet_assisted)
    except TutorError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
