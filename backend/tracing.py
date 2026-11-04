"""Live progress for quiz requests.

Wraps the agent's RAG and LLM clients (and QuizAgent itself) so every call is reported
as a step while it runs, then streams those steps to the browser as NDJSON.
quizAgent is unchanged; it only sees clients with the same methods.
"""

import contextvars
import json
import queue
import threading
import time

from fastapi.responses import StreamingResponse

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


def _evidence_summary(bundle) -> str:
    documents = {e.document_id for e in bundle.evidence}
    return f"{len(bundle.evidence)} chunks from {len(documents)} document{'s' if len(documents) != 1 else ''}"


class TracedRAG:
    def __init__(self, inner):
        self._inner = inner
        self._name = type(inner).__name__

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def retrieve_quiz_evidence(self, **kwargs):
        what = f"topic '{kwargs['topic_id']}'" if kwargs.get("topic_id") else "random sample"
        with step(f"{self._name}.retrieve_quiz_evidence — searching course materials ({what})") as s:
            bundle = self._inner.retrieve_quiz_evidence(**kwargs)
            s.result = _evidence_summary(bundle)
        return bundle

    def retrieve(self, **kwargs):
        with step(f"{self._name}.retrieve — searching course materials") as s:
            bundle = self._inner.retrieve(**kwargs)
            s.result = _evidence_summary(bundle)
        return bundle

    def get_evidence_by_ids(self, evidence_ids, corpus_version, authorized_scope):
        # Called once by grading (to check against the source) and once afterwards for citations.
        reporter = _reporter.get()
        purpose = ("loading the original evidence for grading" if reporter and reporter.grading
                   else "attaching citations to your results")
        with step(f"{self._name}.get_evidence_by_ids — {purpose} ({len(set(evidence_ids))} chunks)") as s:
            bundle = self._inner.get_evidence_by_ids(evidence_ids, corpus_version, authorized_scope)
            s.result = _evidence_summary(bundle)
        return bundle


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
    def __init__(self, rag_client, llm_client):
        super().__init__(TracedRAG(rag_client), TracedLLM(llm_client))

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
