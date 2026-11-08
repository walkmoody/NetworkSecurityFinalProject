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

    def test_question_without_keywords_never_contacts_network(self):
        with patch("tutorAgent.web_lookup._fetch") as fetch:
            with self.assertRaises(WebLookupUnavailable):
                lookup_public_sources("What is the difference between them?")
            fetch.assert_not_called()

    def test_search_sends_only_question_keywords(self):
        seen = []
        def fake_fetch(request):
            seen.append(request.full_url)
            return {"query": {"pages": {"1": {"title": "Cryptographic nonce",
                                               "extract": "A nonce is an arbitrary number used once."}}}}
        with patch("tutorAgent.web_lookup._fetch", side_effect=fake_fetch), \
             patch("tutorAgent.web_lookup._best_match", side_effect=lambda q, pages: pages[0]):
            refs = lookup_public_sources("What is a nonce, and why do we use one?")
        self.assertEqual(refs[0]["source"], "Wikipedia: Cryptographic nonce")
        self.assertIn("gsrsearch=nonce+one", seen[0])
        self.assertNotIn("what", seen[0].lower().split("gsrsearch=")[1])

    def test_irrelevant_search_hit_is_discarded(self):
        with patch("tutorAgent.web_lookup._fetch", return_value={"query": {"pages": {
                "1": {"title": "Capital (French magazine)", "extract": "A French magazine."}}}}), \
             patch("tutorAgent.web_lookup._best_match", return_value=None):
            with self.assertRaisesRegex(WebLookupUnavailable, "relevant"):
                lookup_public_sources("What is the capital of France?")

    def test_course_topics_map_to_fixed_articles(self):
        cases = {
            "What is the difference between a block cipher and a stream cipher?": "Block+cipher",
            "Explain the Feistel cipher structure.": "Feistel+cipher",
            "Is Triple DES safer than DES?": "Triple+DES",
            "What does confidentiality mean?": "Information+security",
        }
        for question, title in cases.items():
            seen = []
            def fake_fetch(request):
                seen.append(request.full_url)
                return {"query": {"pages": {"1": {"title": title, "extract": "text"}}}}
            with patch("tutorAgent.web_lookup._fetch", side_effect=fake_fetch):
                lookup_public_sources(question)
            self.assertIn("titles=" + title, seen[0], question)

    def test_mac_address_is_not_a_crypto_topic(self):
        seen = []
        def fake_fetch(request):
            seen.append(request.full_url)
            return {"query": {"pages": {"1": {"title": "MAC address", "extract": "A hardware address."}}}}
        with patch("tutorAgent.web_lookup._fetch", side_effect=fake_fetch), \
             patch("tutorAgent.web_lookup._best_match", side_effect=lambda q, pages: pages[0]):
            lookup_public_sources("What is a MAC address?")
        self.assertNotIn("Message+authentication+code", seen[0])
        self.assertIn("gsrsearch=mac+address", seen[0])

    def test_provider_error_reports_failure(self):
        with patch("tutorAgent.web_lookup._fetch", side_effect=OSError("offline")):
            with self.assertRaisesRegex(WebLookupUnavailable, "failed"):
                lookup_public_sources("Explain AES")
