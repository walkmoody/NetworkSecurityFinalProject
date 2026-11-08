"""Live progress for quiz requests.

Wraps the LLM client, QuizAgent itself, and the rag_pipeline lookups quizAgent makes
(retrieve_documents, get_evidence_by_ids) so every call is reported as a step while it
runs, then streams those steps to the browser as NDJSON. Without a reporter the wrappers
just pass through.
"""

import contextvars
import json
import queue
import threading
import time

from fastapi.responses import StreamingResponse

import quizAgent.generation
import quizAgent.grading
import quizAgent.mock_backend
from quizAgent import QuizAgent

_reporter = contextvars.ContextVar("reporter", default=None)


class Reporter:
    """Collects the steps of one request; read by the streaming response."""

    def __init__(self):
        self.events = queue.Queue()
        self._next_id = 0
        self.pending_validation = None
        self.grading = False

    def start(self, text: str) -> int:
        self._next_id += 1
        self.events.put({"type": "step", "id": self._next_id, "text": text})
        return self._next_id

    def finish(self, step_id: int, text: str) -> None:
        self.events.put({"type": "step", "id": step_id, "text": text, "done": True})


class _Step:
    """Reports `text` while the block runs, then `text — result (time)` when it ends."""

    def __init__(self, text: str):
        self.text, self.result = text, ""
        self.reporter = _reporter.get()

    def __enter__(self):
        self.started = time.monotonic()
        self.id = self.reporter.start(self.text) if self.reporter else None
        return self

    def __exit__(self, exc_type, *_):
        if self.reporter:
            outcome = "failed" if exc_type else self.result
            elapsed = time.monotonic() - self.started
            self.reporter.finish(self.id, f"{self.text}{' — ' + outcome if outcome else ''} ({elapsed:.1f}s)")


def step(text: str) -> _Step:
    return _Step(text)


def _close_validation(outcome: str) -> None:
    reporter = _reporter.get()
    if reporter and reporter.pending_validation:
        step_id, text = reporter.pending_validation
        reporter.pending_validation = None
        reporter.finish(step_id, f"{text} — {outcome}")


def _evidence_summary(items) -> str:
    documents = {e.get("document_id") or e.get("source") for e in items}
    return f"{len(items)} chunks from {len(documents)} document{'s' if len(documents) != 1 else ''}"


def _traced_retrieve(inner):
    def retrieve_documents(query, top_k=5, course=None):
        with step(f"rag_pipeline.retrieve_documents — searching course materials ('{query}', top {top_k})") as s:
            documents = inner(query, top_k=top_k, course=course)
            s.result = _evidence_summary(documents)
        return documents
    retrieve_documents.__wrapped__ = inner
    return retrieve_documents


def _traced_lookup(inner):
    def get_evidence_by_ids(evidence_ids, version, course_id):
        # Called once by grading (to check against the source) and once afterwards for citations.
        reporter = _reporter.get()
        purpose = ("loading the original evidence for grading" if reporter and reporter.grading
                   else "attaching citations to your results")
        with step(f"rag_pipeline get_evidence_by_ids — {purpose} ({len(set(evidence_ids))} chunks)") as s:
            evidence = inner(evidence_ids, version, course_id)
            s.result = _evidence_summary(evidence)
        return evidence
    get_evidence_by_ids.__wrapped__ = inner
    return get_evidence_by_ids


def _install_retrieval_tracing():
    """quizAgent imports these functions by name, so wrap them where they are looked up."""
    for module, name, wrap in ((quizAgent.generation, "retrieve_documents", _traced_retrieve),
                               (quizAgent.grading, "get_evidence_by_ids", _traced_lookup),
                               (quizAgent.mock_backend, "get_evidence_by_ids", _traced_lookup)):
        current = getattr(module, name)
        if not hasattr(current, "__wrapped__"):
            setattr(module, name, wrap(current))


_install_retrieval_tracing()


class TracedLLM:
    def __init__(self, inner):
        self._inner = inner
        model = getattr(inner, "model", None)
        self._name = type(inner).__name__ + (f" ({model})" if model else "")

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def generate_structured(self, *, task, **kwargs):
        # A second generation call means quizAgent rejected the first draft.
        _close_validation("failed; asking the model again")
        label = {"quiz_generation": "writing quiz questions",
                 "quiz_grading": "grading an open-ended answer against the rubric"}.get(task, task)
        with step(f"{self._name}.generate_structured(task={task}) — {label}"):
            result = self._inner.generate_structured(task=task, **kwargs)
        reporter = _reporter.get()
        if reporter and task == "quiz_generation":
            text = "quizAgent.validation.validate_draft — checking question types, answers, and citations"
            reporter.pending_validation = (reporter.start(text), text)
        return result


class TracedQuizAgent(QuizAgent):
    def __init__(self, llm_client):
        super().__init__(TracedLLM(llm_client))

    def generate_quiz(self, request):
        topic = f", topic={request.topic_id}" if request.topic_id else ""
        total = sum(request.question_counts.values())
        with step(f"QuizAgent.generate_quiz(mode={request.mode}{topic}) — {total} questions for {request.course_id}"):
            try:
                quiz = super().generate_quiz(request)
            except Exception:
                _close_validation("failed")
                raise
            _close_validation("passed")
        return quiz

    def grade_quiz(self, request):
        open_ended = sum(q["type"] == "open_ended" for q in request.questions)
        objective = len(request.questions) - open_ended
        reporter = _reporter.get()
        if reporter:
            reporter.grading = True
        try:
            with step(f"QuizAgent.grade_quiz — {objective} answers checked against the answer key, "
                      f"{open_ended} open-ended sent to the model"):
                return super().grade_quiz(request)
        finally:
            if reporter:
                reporter.grading = False


def stream(work, on_error) -> StreamingResponse:
    """Run `work` in a thread and stream its steps, then its result or error, as NDJSON."""
    reporter = Reporter()

    def run():
        _reporter.set(reporter)
        try:
            reporter.events.put({"type": "result", "data": work()})
        except Exception as exc:
            status, detail = on_error(exc)
            reporter.events.put({"type": "error", "status": status, "detail": detail})
        finally:
            reporter.events.put(None)

    threading.Thread(target=run, daemon=True).start()

    def body():
        while (event := reporter.events.get()) is not None:
            yield json.dumps(event) + "\n"

    return StreamingResponse(body(), media_type="application/x-ndjson")
