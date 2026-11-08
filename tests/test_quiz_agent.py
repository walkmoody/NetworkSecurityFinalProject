"""Run: python -m pytest tests/test_quiz_agent.py -q (no Ollama server needed)."""

from unittest.mock import Mock
from uuid import uuid4

import chromadb
import pytest
from chromadb.config import Settings

from llm import MockLLM
from quizAgent import QuizAgent
from quizAgent.errors import AccessDenied, AttemptConflict, EvidenceUnavailable, ValidationError
from quizAgent.mock_backend import MockBackend

PAYLOAD = {"course_id": "CS5342", "mode": "random", "topic_id": None,
           "question_counts": {"multiple_choice": 1, "true_false": 1, "open_ended": 1}}


@pytest.fixture
def collection(monkeypatch):
    client = chromadb.EphemeralClient(Settings(anonymized_telemetry=False))
    name = "quiz-test-" + uuid4().hex
    db = client.create_collection(name, embedding_function=None)
    try:
        db.add(ids=["security", "art"], embeddings=[[1., 0.], [0., 1.]],
               documents=["Firewalls filter network traffic.", "Monet painted outdoor light."],
               metadatas=[{"course": course, "source": course + ".txt", "page": 1, "chunk": 1}
                          for course in ("CS5342", "ArtHistory")])
        monkeypatch.setattr("quizAgent.evidence.get_collection", lambda: db)
        monkeypatch.setattr("rag_pipeline.retriever.get_collection", lambda: db)
        monkeypatch.setattr("rag_pipeline.retriever.load_embedding_model", lambda: None)
        monkeypatch.setattr("rag_pipeline.retriever.generate_embeddings", lambda *args: [[1., 0.]])
        yield db
    finally:
        client.delete_collection(name)


@pytest.fixture
def backend(collection, monkeypatch, tmp_path):
    manifest = tmp_path / "hashes.json"
    manifest.write_text('{"CS5342.txt": "approved"}')
    monkeypatch.setattr("quizAgent.evidence.MANIFEST_FILE", manifest)
    return MockBackend(QuizAgent(Mock(wraps=MockLLM())))


def correct_answers(backend, quiz):
    questions = backend._attempts[quiz["attempt_id"]].draft["questions"]
    return {q["question_id"]: q["answer_key"]["reference_answer"] if q["type"] == "open_ended"
            else q["answer_key"]["correct_answer"] for q in questions}


@pytest.mark.parametrize("flat", [False, True])
def test_generate_and_grade(backend, collection, flat):
    if flat:
        collection.delete(ids=["art"])
        collection.update(ids=["security"], metadatas=[{"course": ""}])
    quiz = backend.create_quiz("alice", PAYLOAD)
    assert len(quiz["questions"]) == 3
    for question in quiz["questions"]:
        assert set(question) == {"question_id", "type", "text", "options", "max_points"}
    result = backend.submit_answers("alice", quiz["attempt_id"], correct_answers(backend, quiz))
    assert result["points_awarded"] == result["max_points"] == 8
    assert all(r["citations"][0]["chunk_id"] == "security" for r in result["results"])
    assert backend.get_result("alice", quiz["attempt_id"]) == result
    with pytest.raises(AttemptConflict):
        backend.submit_answers("alice", quiz["attempt_id"], correct_answers(backend, quiz))


def test_topic_generation(backend, monkeypatch):
    from rag_pipeline.retriever import retrieve_documents
    retrieve = Mock(wraps=retrieve_documents)
    monkeypatch.setattr("quizAgent.generation.retrieve_documents", retrieve)
    backend.create_quiz("alice", {**PAYLOAD, "mode": "topic", "topic_id": "firewall"})
    retrieve.assert_called_once_with("firewall", top_k=12, course="CS5342")
    evidence = backend.agent.llm.generate_structured.call_args.kwargs["input_data"]["evidence"]
    assert {e["chunk_id"] for e in evidence} == {"security"}


@pytest.mark.parametrize("counts", [{}, {"true_false": -1}, {"true_false": True}, {"true_false": 13}])
def test_invalid_counts(backend, counts):
    with pytest.raises(ValidationError):
        backend.create_quiz("alice", {**PAYLOAD, "question_counts": counts})
    backend.agent.llm.generate_structured.assert_not_called()


def test_access_control(backend):
    with pytest.raises(AccessDenied):
        backend.create_quiz("outsider", PAYLOAD)
    quiz = backend.create_quiz("alice", PAYLOAD)
    with pytest.raises(AccessDenied):
        backend.get_quiz("bob", quiz["attempt_id"])


def test_fabricated_citations_rejected(backend):
    def fabricate(**kwargs):
        draft = MockLLM().generate_structured(**kwargs)
        draft["questions"][0]["answer_key"]["evidence_ids"] = ["invented"]
        return draft
    backend.agent.llm.generate_structured.side_effect = fabricate
    with pytest.raises(ValidationError, match="after two attempts"):
        backend.create_quiz("alice", PAYLOAD)
    assert backend.agent.llm.generate_structured.call_count == 2
    assert not backend._attempts


@pytest.mark.parametrize("change", ["manifest", "missing_chunk"])
def test_original_evidence_required(backend, collection, tmp_path, change):
    quiz = backend.create_quiz("alice", PAYLOAD)
    if change == "manifest":
        (tmp_path / "hashes.json").write_text("changed")
    else:
        collection.delete(ids=["security"])
    with pytest.raises(EvidenceUnavailable):
        backend.submit_answers("alice", quiz["attempt_id"], correct_answers(backend, quiz))
    assert backend.get_quiz("alice", quiz["attempt_id"])["status"] == "review_required"


def test_retry_uses_locked_answers(backend):
    quiz = backend.create_quiz("alice", PAYLOAD)
    answers = correct_answers(backend, quiz)
    model = backend.agent.llm.generate_structured
    model.side_effect = lambda **kwargs: {"criteria_scores": [], "feedback": "invalid"}
    with pytest.raises(ValidationError):
        backend.submit_answers("alice", quiz["attempt_id"], answers)
    with pytest.raises(AttemptConflict):
        backend.submit_answers("alice", quiz["attempt_id"], answers)
    answers.clear()
    model.side_effect = None
    assert backend.retry_grading("alice", quiz["attempt_id"])["points_awarded"] == 8
