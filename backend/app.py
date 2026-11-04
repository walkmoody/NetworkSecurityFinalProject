"""HTTP layer between the React frontend and the Quiz Agent.

Run from repository root: uvicorn backend.app:app --host 127.0.0.1 --port 8000
Set QUIZ_LLM=mock to run without Ollama, and QUIZ_RAG=sample to skip the ChromaDB knowledge base.
"""

import json
import logging
import os
import secrets
from pathlib import Path
from threading import Lock

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.tracing import TracedQuizAgent, step, stream
from llm import MockLLM, OllamaClient
from llm.contracts import ModelError
from quizAgent.errors import AttemptConflict, ValidationError
from quizAgent.mock_backend import MockBackend
import rag as rag_package
from rag import InMemoryRAG
from rag.contracts import AccessDenied, RAGError

SESSION_COOKIE = "quiz_session"
MAX_SESSIONS = 1000

log = logging.getLogger("backend")
use_mock = os.environ.get("QUIZ_LLM", "ollama").lower() == "mock"
model = MockLLM() if use_mock else OllamaClient()

# QUIZ_RAG=sample uses the built-in fixture corpus instead of the ChromaDB knowledge base.
if os.environ.get("QUIZ_RAG", "pipeline").lower() == "sample":
    rag = InMemoryRAG.sample()
    _sample = json.loads((Path(rag_package.__file__).parent / "data" / "sample_corpus.json").read_text())
    _sample_courses = sorted({e["course_id"] for e in _sample["evidence"]})
    list_courses = lambda: _sample_courses
else:
    from backend.pipeline_rag import PipelineRAG
    rag = PipelineRAG()
    # Courses are the folders in data/ that have been indexed by rag_pipeline.build_index.
    list_courses = PipelineRAG.courses
# Reports each RAG, model, and agent call while a request runs (see backend/tracing.py).
agent = TracedQuizAgent(rag, model)

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
    if isinstance(exc, RAGError):
        return (403 if isinstance(exc, AccessDenied) else 422), str(exc)
    if isinstance(exc, ModelError):
        log.warning("Model error: %s", exc)
        return 502, "The local model is unavailable or returned an invalid response."
    log.error("Unexpected error", exc_info=exc)
    return 500, "Unexpected server error."


def _error_response(_, exc):
    status, detail = _error(exc)
    return JSONResponse({"detail": detail}, status_code=status)


for _exc_type in (ValidationError, AttemptConflict, RAGError, ModelError, Exception):
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
