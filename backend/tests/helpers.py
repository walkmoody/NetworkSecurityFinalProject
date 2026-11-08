"""Shared helpers for backend tests."""

import json
import tempfile
from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import chromadb
from chromadb.config import Settings


def events(response) -> list[dict]:
    """Parse a streamed NDJSON response into its events."""
    return [json.loads(line) for line in response.text.splitlines() if line.strip()]


def final(response) -> dict:
    """The last event of a stream: the result or the error."""
    return events(response)[-1]


def answers_for(quiz: dict) -> dict:
    """Valid (not necessarily correct) answers for every question in a public quiz."""
    by_type = {"multiple_choice": "A", "true_false": True,
               "open_ended": "A firewall filters traffic according to a security policy."}
    return {q["question_id"]: by_type[q["type"]] for q in quiz["questions"]}


CHUNKS = {
    "fw-1": ("Firewalls filter network traffic according to a security policy.", "firewalls.pdf"),
    "fw-2": ("Stateful firewalls track connection state to allow return traffic.", "firewalls.pdf"),
    "tls-1": ("TLS uses certificates to authenticate the server to the client.", "tls.pdf"),
    "auth-1": ("Passwords are stored as salted hashes so equal passwords differ.", "auth.pdf"),
}


@contextmanager
def knowledge_base(course="CS5342"):
    """A throwaway rag_pipeline collection holding one course, with embeddings stubbed out.

    quizAgent and backend.app still go through rag_pipeline.retriever and the Chroma
    collection API; only the persistent database and the embedding model are replaced.
    """
    client = chromadb.EphemeralClient(Settings(anonymized_telemetry=False))
    name = "backend-test-" + uuid4().hex
    db = client.create_collection(name, embedding_function=None)
    db.add(ids=list(CHUNKS), embeddings=[[1.0, i / 10] for i in range(len(CHUNKS))],
           documents=[text for text, _ in CHUNKS.values()],
           metadatas=[{"course": course, "source": source, "page": i + 1, "chunk": i}
                      for i, (_, source) in enumerate(CHUNKS.values())])
    with tempfile.TemporaryDirectory() as tmp:
        manifest = Path(tmp) / "hashes.json"
        manifest.write_text('{"firewalls.pdf": "approved"}')
        with ExitStack() as stack:
            for target in ("rag_pipeline.retriever.get_collection", "quizAgent.evidence.get_collection",
                           "backend.app.get_collection"):
                stack.enter_context(patch(target, lambda: db))
            stack.enter_context(patch("rag_pipeline.retriever.load_embedding_model", lambda: None))
            stack.enter_context(patch("rag_pipeline.retriever.generate_embeddings", lambda *a: [[1.0, 0.0]]))
            stack.enter_context(patch("quizAgent.evidence.MANIFEST_FILE", manifest))
            try:
                yield db
            finally:
                client.delete_collection(name)
