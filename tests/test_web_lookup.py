"""Public lookup privacy checks; offline, no actual network requests."""
import unittest
from unittest.mock import patch
from tutorAgent.web_lookup import lookup_public_sources, WebLookupUnavailable

class WebLookupTests(unittest.TestCase):
    def test_only_fixed_public_topic_transmitted(self):
        seen = []
        def fake_fetch(request):
            seen.append(request.full_url)
            return {"query": {"pages": {"123": {"title": "Advanced Encryption Standard",
                                                 "extract": "AES is a block cipher."}}}}
        with patch("tutorAgent.web_lookup._fetch", side_effect=fake_fetch):
            refs = lookup_public_sources("Explain AES. PRIVATE_COURSE_SECRET_8729")
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0]["source_type"], "web")
        self.assertNotIn("PRIVATE_COURSE_SECRET_8729", seen[0])
        self.assertIn("Advanced+Encryption+Standard", seen[0])

    def test_unknown_topic_never_contacts_network(self):
        with patch("tutorAgent.web_lookup._fetch") as fetch:
            with self.assertRaises(WebLookupUnavailable):
                lookup_public_sources("PRIVATE_COURSE_SECRET_8729")
            fetch.assert_not_called()

    def test_provider_error_reports_failure(self):
        with patch("tutorAgent.web_lookup._fetch", side_effect=OSError("offline")):
            with self.assertRaisesRegex(WebLookupUnavailable, "failed"):
                lookup_public_sources("Explain AES")
