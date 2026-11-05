"""PipelineRAG against a throwaway two-course knowledge base built in a temp folder.

The real data/ and vector_db/ are never touched. Needs the embedding model, which is
downloaded on first use; the tests are skipped if it cannot be loaded.
"""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import backend.pipeline_rag as pipeline_rag
import rag_pipeline.embeddings as embeddings
import rag_pipeline.ingestion as ingestion
import rag_pipeline.integrity as integrity
from backend.pipeline_rag import MAX_CHUNKS, PipelineRAG
from llm import MockLLM
from quizAgent import QuizAgent
from quizAgent.mock_backend import MockBackend
from rag.contracts import AccessDenied, AuthorizedScope, EvidenceUnavailable
from .helpers import answers_for

DOCUMENTS = {
    "NetworkSecurity/firewalls.txt": "A firewall filters network traffic according to a security policy.",
    "NetworkSecurity/stateful.txt": "Stateful firewalls track connection state when deciding whether to allow packets.",
    "NetworkSecurity/symmetric.txt": "Symmetric encryption uses the same secret key to encrypt and decrypt.",
    "NetworkSecurity/public_key.txt": "Public-key cryptography uses a related public key and private key.",
    "NetworkSecurity/salts.txt": "Passwords should be stored as salted hashes so identical passwords differ.",
    "NetworkSecurity/mfa.txt": "Multi-factor authentication combines something you know, have, and are.",
    "NetworkSecurity/ids.txt": "An intrusion detection system raises alerts on suspicious traffic patterns.",
    "NetworkSecurity/tls.txt": "TLS protects data in transit with authenticated encryption.",
    "ArtHistory/baroque.txt": "Baroque painters used dramatic light, rich color, and movement.",
    "ArtHistory/impressionism.txt": "Impressionists like Monet painted light outdoors with loose brushwork.",
}
BOTH = AuthorizedScope(("NetworkSecurity", "ArtHistory"))
NETWORK_ONLY = AuthorizedScope(("NetworkSecurity",))


class PipelineRAGTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        manifest = root / "vector_db" / "hashes.json"
        cls.patches = [
            patch.object(integrity, "DATA_DIR", root / "data"),
            patch.object(ingestion, "DATA_DIR", root / "data"),
            patch.object(integrity, "MANIFEST_FILE", manifest),
            patch.object(pipeline_rag, "MANIFEST_FILE", manifest),
            patch.object(embeddings, "DB_PATH", root / "vector_db"),
        ]
        for p in cls.patches:
            p.start()
        for name, text in DOCUMENTS.items():
            path = root / "data" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                integrity.create_manifest()
                embeddings.build_vector_database()
        except Exception as exc:
            cls.tearDownClass()
            raise unittest.SkipTest(f"Could not build a test knowledge base: {exc}")

    @classmethod
    def tearDownClass(cls):
        for p in cls.patches:
            p.stop()
        cls.tmp.cleanup()

    def setUp(self):
        self.rag = PipelineRAG()

    def quiz_evidence(self, course, mode="random", topic=None, scope=BOTH, max_chunks=12):
        return self.rag.retrieve_quiz_evidence(course_id=course, mode=mode, topic_id=topic,
                                               max_chunks=max_chunks, authorized_scope=scope)

    def test_courses_are_the_data_folders(self):
        self.assertEqual(PipelineRAG.courses(), ["ArtHistory", "NetworkSecurity"])

    def test_random_mode_stays_in_the_course_and_caps_chunks(self):
        bundle = self.quiz_evidence("NetworkSecurity")
        self.assertEqual(len(bundle.evidence), MAX_CHUNKS)
        for e in bundle.evidence:
            self.assertEqual(e.course_id, "NetworkSecurity")
            self.assertTrue(e.document_id.startswith("NetworkSecurity/"))

    def test_topic_mode_searches_only_the_requested_course(self):
        # The art chunks match "painting light" far better, but must never be returned.
        bundle = self.quiz_evidence("NetworkSecurity", mode="topic", topic="painting light")
        self.assertTrue(bundle.evidence)
        self.assertTrue(all(e.course_id == "NetworkSecurity" for e in bundle.evidence))
        self.assertTrue(all(e.topic == "painting light" for e in bundle.evidence))
        art = self.quiz_evidence("ArtHistory", mode="topic", topic="painting light")
        self.assertEqual({e.course_id for e in art.evidence}, {"ArtHistory"})

    def test_evidence_round_trips_by_id(self):
        bundle = self.quiz_evidence("NetworkSecurity")
        ids = [e.chunk_id for e in bundle.evidence]
        again = self.rag.get_evidence_by_ids(ids, bundle.corpus_version, NETWORK_ONLY)
        self.assertEqual([e.chunk_id for e in again.evidence], ids)
        self.assertEqual([e.text for e in again.evidence], [e.text for e in bundle.evidence])

    def test_stale_corpus_version_is_rejected(self):
        ids = [self.quiz_evidence("NetworkSecurity").evidence[0].chunk_id]
        with self.assertRaises(EvidenceUnavailable):
            self.rag.get_evidence_by_ids(ids, "manifest-0000000000000000", NETWORK_ONLY)

    def test_courses_outside_the_scope_are_denied(self):
        with self.assertRaises(AccessDenied):
            self.quiz_evidence("ArtHistory", scope=NETWORK_ONLY)
        art = self.quiz_evidence("ArtHistory")
        with self.assertRaises(AccessDenied):
            self.rag.get_evidence_by_ids([art.evidence[0].chunk_id], art.corpus_version, NETWORK_ONLY)

    def test_course_without_documents_explains_how_to_add_them(self):
        with self.assertRaisesRegex(EvidenceUnavailable, "data/Biology/"):
            self.quiz_evidence("Biology", scope=AuthorizedScope(("Biology",)))

    def test_quiz_generates_and_grades_from_the_knowledge_base(self):
        backend = MockBackend(QuizAgent(self.rag, MockLLM()), {"student": ("NetworkSecurity",)})
        quiz = backend.create_quiz("student", {
            "course_id": "NetworkSecurity", "mode": "random",
            "question_counts": {"multiple_choice": 2, "true_false": 2, "open_ended": 1},
        })
        result = backend.submit_answers("student", quiz["attempt_id"], answers_for(quiz))
        cited = {c["document_id"] for r in result["results"] for c in r["citations"]}
        self.assertTrue(cited)
        self.assertTrue(all(doc.startswith("NetworkSecurity/") for doc in cited))


if __name__ == "__main__":
    unittest.main()
