"""Offline tests: no model, index, or external services required."""
import unittest
from llm.contracts import ModelError
from tutorAgent import TutorAgent, TutorError
from tutorAgent.citations import clean_citations

ROWS = [{"id": "course:1", "text": "AES is a symmetric block cipher.",
         "source": "lecture.pdf", "page": 3, "chunk": 1, "similarity": 0.9}]


class FakeLLM:
    def __init__(self, response=None):
        self.response = response if response is not None else {
            "answer": "AES is a symmetric block cipher.",
            "supported": True, "evidence_ids": ["course:1"],
        }
        self.calls = 0

    def generate_structured(self, **kwargs):
        self.calls += 1
        return self.response


class TutorTests(unittest.TestCase):
    def make(self, rows=None, llm=None):
        return TutorAgent(
            retriever=lambda query, top_k: ROWS if rows is None else rows,
            llm_client=llm if llm is not None else FakeLLM(),
        )

    def test_supported_answer_and_citations(self):
        answer = self.make().ask("What is AES?")
        self.assertTrue(answer["supported"])
        self.assertEqual(answer["citations"][0]["source"], "lecture.pdf")

    def test_empty_retrieval(self):
        llm = FakeLLM()
        self.assertFalse(self.make(rows=[], llm=llm).ask("Unknown")["supported"])
        self.assertEqual(llm.calls, 0)

    def test_low_similarity(self):
        llm = FakeLLM()
        self.assertFalse(self.make(rows=[dict(ROWS[0], similarity=0.1)], llm=llm).ask("Unknown")["supported"])
        self.assertEqual(llm.calls, 0)

    def test_reject_fabricated_citation(self):
        llm = FakeLLM({"answer": "A", "supported": True, "evidence_ids": ["fake"]})
        self.assertFalse(self.make(llm=llm).ask("Question")["supported"])

    def test_unsupported_response(self):
        llm = FakeLLM({"answer": "", "supported": False, "evidence_ids": []})
        self.assertFalse(self.make(llm=llm).ask("Question")["supported"])

    def test_input_validation(self):
        agent = self.make()
        for q in ("", " ", "x" * 2001, None):
            with self.assertRaises(TutorError):
                agent.ask(q)
        with self.assertRaises(TutorError):
            agent.ask("AES?", "OTHER")

    def test_duplicate_citation(self):
        self.assertEqual(len(clean_citations(["course:1", "course:1"], ROWS)), 1)

    def test_model_error(self):
        class Broken:
            def generate_structured(self, **kwargs):
                raise ModelError("offline")
        with self.assertRaises(TutorError):
            self.make(llm=Broken()).ask("AES?")

    def test_invalid_course_configuration(self):
        with self.assertRaises(ValueError):
            TutorAgent(course_id="", retriever=lambda **kwargs: [], llm_client=FakeLLM())


    def test_internet_assisted_returns_external_citation(self):
        from unittest.mock import patch
        web = {"id": "web:wikipedia:AES", "text": "AES is a block cipher.",
               "source": "Wikipedia: AES", "source_type": "web",
               "url": "https://en.wikipedia.org/wiki/Advanced_Encryption_Standard",
               "page": 1, "chunk": 1, "similarity": 1.0}
        llm = FakeLLM({"answer": "AES is a block cipher.", "supported": True,
                       "evidence_ids": ["web:wikipedia:AES"]})
        with patch("tutorAgent.tutor_agent.lookup_public_sources", return_value=[web]):
            result = self.make(rows=[], llm=llm).ask("Explain AES", internet_assisted=True)
        self.assertEqual(result["citations"][0]["url"], web["url"])

    def test_internet_lookup_receives_only_the_question(self):
        from unittest.mock import patch
        with patch("tutorAgent.tutor_agent.lookup_public_sources", return_value=[]) as lookup:
            self.make().ask("  AES  ", internet_assisted=True)
        lookup.assert_called_once_with("AES")

    def test_internet_assisted_falls_back_to_course_material(self):
        from unittest.mock import patch
        from tutorAgent.web_lookup import WebLookupUnavailable
        with patch("tutorAgent.tutor_agent.lookup_public_sources",
                   side_effect=WebLookupUnavailable("No approved public lookup topic matched this question.")):
            result = self.make().ask("AES", internet_assisted=True)
        self.assertTrue(result["supported"])
        self.assertTrue(all(c.get("source_type") != "web" for c in result["citations"]))

    def test_local_only_does_not_call_internet(self):
        from unittest.mock import patch
        with patch("tutorAgent.tutor_agent.lookup_public_sources") as lookup:
            self.make().ask("AES")
            lookup.assert_not_called()


if __name__ == "__main__":
    unittest.main()
