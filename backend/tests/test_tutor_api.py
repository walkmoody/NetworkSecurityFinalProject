"""Tutor HTTP integration tests without a live model or knowledge base."""
import unittest
from unittest.mock import patch

# backend.tests.test_app loads the app in sample/mock mode before collecting tests.
from fastapi.testclient import TestClient
import backend.app as app_module


class TutorApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app_module.app)

    def test_unknown_course_rejected(self):
        with patch.object(app_module, "list_courses", return_value=["CS5342"]):
            result = self.client.post("/api/tutor/ask", json={"course_id": "OTHER", "question": "AES?"})
        self.assertEqual(result.status_code, 403)

    def test_mock_mode_reports_unavailable(self):
        with patch.object(app_module, "list_courses", return_value=["CS5342"]), patch.object(app_module, "use_mock", True):
            result = self.client.post("/api/tutor/ask", json={"course_id": "CS5342", "question": "AES?"})
        self.assertEqual(result.status_code, 503)

    def test_tutor_uses_existing_model_and_course(self):
        expected = {"answer": "AES uses a shared key.", "supported": True, "citations": []}
        with patch.object(app_module, "list_courses", return_value=["CS5342"]), patch.object(app_module, "use_mock", False), patch.object(app_module, "TutorAgent") as cls:
            cls.return_value.ask.return_value = expected
            result = self.client.post("/api/tutor/ask", json={"course_id": "CS5342", "question": "AES?"})
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json(), expected)
            self.assertIs(cls.call_args.kwargs["llm_client"], app_module.model)
            self.assertEqual(cls.call_args.kwargs["course_id"], "CS5342")


if __name__ == "__main__":
    unittest.main()
