"""Progress steps reported by the traced agent, without HTTP."""

import unittest

from backend.tracing import Reporter, TracedQuizAgent, _reporter
from llm import MockLLM
from quizAgent import GenerateQuizRequest
from quizAgent.mock_backend import MockBackend
from unittest.mock import patch

from quizAgent.errors import EvidenceUnavailable
from .helpers import answers_for, knowledge_base

COUNTS = {"multiple_choice": 3, "true_false": 2, "open_ended": 1}


class RejectedFirstDraftLLM(MockLLM):
    """Returns an invalid first quiz draft, so quizAgent asks the model again."""

    def __init__(self):
        self.generation_calls = 0

    def generate_structured(self, **kwargs):
        if kwargs["task"] == "quiz_generation":
            self.generation_calls += 1
            if self.generation_calls == 1:
                return {"questions": []}
        return super().generate_structured(**kwargs)


class TracingTests(unittest.TestCase):
    def setUp(self):
        self.kb = knowledge_base()
        self.kb.__enter__()
        self.addCleanup(self.kb.__exit__, None, None, None)
        self.reporter = Reporter()
        self.token = _reporter.set(self.reporter)
        self.request = GenerateQuizRequest("CS5342", "random", None, dict(COUNTS))

    def tearDown(self):
        _reporter.reset(self.token)

    def steps(self) -> list[dict]:
        found = []
        while not self.reporter.events.empty():
            found.append(self.reporter.events.get())
        return found

    def final_texts(self) -> list[str]:
        """Each step's last reported text, in start order."""
        latest = {}
        for event in self.steps():
            latest[event["id"]] = event["text"]
        return [latest[i] for i in sorted(latest)]

    def test_generation_reports_each_call_with_results(self):
        agent = TracedQuizAgent(MockLLM())
        agent.generate_quiz(self.request)
        texts = self.final_texts()
        self.assertTrue(texts[0].startswith("QuizAgent.generate_quiz(mode=random) — 6 questions for CS5342"))
        self.assertRegex(texts[1], r"rag_pipeline\.retrieve_documents .* — \d+ chunks from \d+ documents \(\d+\.\ds\)$")
        self.assertIn("MockLLM.generate_structured(task=quiz_generation)", texts[2])
        self.assertTrue(texts[3].startswith("quizAgent.validation.validate_draft"))
        self.assertTrue(texts[3].endswith("— passed"))

    def test_every_started_step_finishes(self):
        agent = TracedQuizAgent(MockLLM())
        agent.generate_quiz(self.request)
        events = self.steps()
        self.assertEqual({e["id"] for e in events if not e.get("done")},
                         {e["id"] for e in events if e.get("done")})

    def test_rejected_draft_is_reported_before_the_retry(self):
        model = RejectedFirstDraftLLM()
        TracedQuizAgent(model).generate_quiz(self.request)
        self.assertEqual(model.generation_calls, 2)
        validations = [t for t in self.final_texts() if "validate_draft" in t]
        self.assertEqual(len(validations), 2)
        self.assertTrue(validations[0].endswith("failed; asking the model again"))
        self.assertTrue(validations[1].endswith("passed"))

    def test_failing_call_is_marked_failed(self):
        agent = TracedQuizAgent(MockLLM())
        failure = EvidenceUnavailable("No approved evidence matches this request.")
        with patch("rag_pipeline.retriever.generate_embeddings", side_effect=failure):
            with self.assertRaises(EvidenceUnavailable):
                agent.generate_quiz(self.request)
        texts = self.final_texts()
        self.assertRegex(texts[0], r"— failed \(\d+\.\ds\)$")
        self.assertRegex(texts[1], r"retrieve_documents .* — failed \(\d+\.\ds\)$")

    def test_grading_labels_evidence_loads_by_purpose(self):
        backend = MockBackend(TracedQuizAgent(MockLLM()))
        quiz = backend.create_quiz("alice", {"course_id": "CS5342", "mode": "random",
                                             "question_counts": dict(COUNTS)})
        self.steps()  # discard generation steps
        backend.submit_answers("alice", quiz["attempt_id"], answers_for(quiz))
        loads = [t for t in self.final_texts() if "get_evidence_by_ids" in t]
        self.assertEqual(len(loads), 2)
        self.assertIn("loading the original evidence for grading", loads[0])
        self.assertIn("attaching citations to your results", loads[1])

    def test_agent_works_without_a_reporter(self):
        _reporter.reset(self.token)
        self.token = _reporter.set(None)
        quiz = TracedQuizAgent(MockLLM()).generate_quiz(self.request)
        self.assertEqual(len(quiz["questions"]), 6)


if __name__ == "__main__":
    unittest.main()
