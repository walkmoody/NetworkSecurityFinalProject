"""HTTP API tests through rag_pipeline against a throwaway Chroma collection and the mock model (no Ollama)."""

import os
import unittest
from unittest.mock import patch

# backend.app reads these at import time.
os.environ["QUIZ_LLM"] = "mock"

from fastapi.testclient import TestClient  # noqa: E402

import backend.app as app_module  # noqa: E402
from llm.contracts import ModelError  # noqa: E402
from .helpers import answers_for, events, final, knowledge_base  # noqa: E402

COUNTS = {"multiple_choice": 3, "true_false": 2, "open_ended": 1}


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.kb = knowledge_base()
        self.kb.__enter__()
        self.addCleanup(self.kb.__exit__, None, None, None)
        # Each client keeps its own cookies, so each test starts a new session.
        self.client = TestClient(app_module.app)

    def create(self, client=None, **overrides):
        body = {"course_id": "CS5342", "mode": "random", "topic_id": None, "question_counts": COUNTS}
        return (client or self.client).post("/api/quiz", json={**body, **overrides})

    def create_quiz(self):
        event = final(self.create())
        self.assertEqual(event["type"], "result", event)
        return event["data"]

    def submit(self, quiz, client=None):
        return (client or self.client).post(f"/api/quiz/{quiz['attempt_id']}/submit",
                                            json={"answers": answers_for(quiz)})

    def test_health_reports_mock_mode(self):
        self.assertEqual(self.client.get("/api/health").json(), {"mode": "mock"})

    def test_courses_come_from_the_corpus(self):
        self.assertEqual(self.client.get("/api/courses").json(), {"courses": ["CS5342"]})

    def test_create_streams_steps_then_public_quiz(self):
        response = self.create(mode="topic", topic_id="firewall")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["content-type"].startswith("application/x-ndjson"))
        stream = events(response)
        steps, last = stream[:-1], stream[-1]
        self.assertTrue(steps and all(e["type"] == "step" for e in steps))
        self.assertEqual(last["type"], "result")
        # Every step that starts also finishes.
        started = {e["id"] for e in steps if not e.get("done")}
        finished = {e["id"] for e in steps if e.get("done")}
        self.assertEqual(started, finished)
        texts = " | ".join(e["text"] for e in steps)
        for call in ("MockBackend.create_quiz", "QuizAgent.generate_quiz(mode=topic, topic=firewall)",
                     "rag_pipeline.retrieve_documents", "generate_structured(task=quiz_generation)",
                     "validate_draft", "passed"):
            self.assertIn(call, texts)
        quiz = last["data"]
        self.assertEqual(len(quiz["questions"]), 6)
        self.assertNotIn("answer_key", str(quiz))

    def test_session_cookie_is_httponly_and_strict(self):
        cookie = self.create().headers["set-cookie"].lower()
        self.assertIn("quiz_session=", cookie)
        self.assertIn("httponly", cookie)
        self.assertIn("samesite=strict", cookie)

    def test_submit_grades_with_citations(self):
        quiz = self.create_quiz()
        response = self.submit(quiz)
        texts = " | ".join(e["text"] for e in events(response) if e["type"] == "step")
        self.assertIn("QuizAgent.grade_quiz", texts)
        self.assertIn("attaching citations", texts)
        result = final(response)["data"]
        self.assertEqual(result["status"], "graded")
        self.assertEqual(len(result["results"]), 6)
        self.assertEqual(result["max_points"], sum(q["max_points"] for q in quiz["questions"]))
        for item in result["results"]:
            self.assertTrue(item["citations"])
            self.assertLessEqual(item["points_awarded"], item["max_points"])

    def test_second_submit_is_a_conflict(self):
        quiz = self.create_quiz()
        self.submit(quiz)
        self.assertEqual(final(self.submit(quiz)), {
            "type": "error", "status": 409, "detail": "This attempt has already been submitted."})

    def test_another_session_cannot_submit_the_attempt(self):
        quiz = self.create_quiz()
        event = final(self.submit(quiz, client=TestClient(app_module.app)))
        self.assertEqual((event["type"], event["status"]), ("error", 403))

    def test_unknown_course_is_forbidden(self):
        event = final(self.create(course_id="ArtHistory"))
        self.assertEqual((event["type"], event["status"]), ("error", 403))

    def test_invalid_mode_is_a_bad_request(self):
        event = final(self.create(mode="everything"))
        self.assertEqual(event, {"type": "error", "status": 400, "detail": "mode must be random or topic."})

    def test_malformed_body_is_rejected_before_streaming(self):
        response = self.client.post("/api/quiz", json={"mode": "random"})
        self.assertEqual(response.status_code, 422)
        self.assertIn("detail", response.json())

    def test_retry_requires_a_failed_grade(self):
        quiz = self.create_quiz()
        event = final(self.client.post(f"/api/quiz/{quiz['attempt_id']}/retry"))
        self.assertEqual((event["type"], event["status"]), ("error", 409))

    def test_model_errors_hide_internal_details(self):
        failure = ModelError("Cannot reach Ollama at http://10.0.0.5:11434")
        with patch.object(app_module.model, "generate_structured", side_effect=failure):
            event = final(self.create())
        self.assertEqual(event["status"], 502)
        self.assertNotIn("10.0.0.5", event["detail"])

    def test_failed_grading_can_be_retried(self):
        quiz = self.create_quiz()
        with patch.object(app_module.model, "generate_structured", side_effect=ModelError("down")):
            failed = self.submit(quiz)
        self.assertEqual(final(failed)["status"], 502)
        self.assertIn("failed", " | ".join(e["text"] for e in events(failed) if e["type"] == "step"))
        retried = final(self.client.post(f"/api/quiz/{quiz['attempt_id']}/retry"))
        self.assertEqual(retried["type"], "result")
        self.assertEqual(retried["data"]["status"], "graded")


if __name__ == "__main__":
    unittest.main()
