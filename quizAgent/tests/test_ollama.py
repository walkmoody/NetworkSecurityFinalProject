import io
import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch
from urllib.error import URLError

from llm.contracts import ModelError
from llm import OllamaClient


class OllamaTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {}, clear=True)
        env.start()
        self.addCleanup(env.stop)
        # Developer edits to the real configuration must not change test behavior.
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        settings_path = Path(folder.name) / "ollama.json"
        settings_path.write_text("{}", encoding="utf-8")
        config = patch("llm.config.DEFAULT_CONFIG_PATH", settings_path)
        config.start()
        self.addCleanup(config.stop)
        self.client = OllamaClient("local-test-model", timeout=1)
        self.client._opener = Mock()
        self.call = dict(task="quiz_grading", instructions="Trusted instructions",
                         input_data={"student_answer": "untrusted text"},
                         output_schema={"type": "object"})

    def respond(self, data):
        self.client._opener.open.return_value = io.BytesIO(data)

    def test_request_format_and_structured_response(self):
        self.respond(json.dumps({"done": True, "message": {"content": '{"ok": true}'}}).encode())
        self.assertEqual(self.client.generate_structured(**self.call), {"ok": True})
        request = self.client._opener.open.call_args.args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:11434/api/chat")
        body = json.loads(request.data)
        self.assertFalse(body["stream"])
        self.assertFalse(body["think"])
        self.assertEqual(body["options"]["num_ctx"], 16384)
        self.assertEqual(body["options"]["num_predict"], 4096)
        self.assertEqual(body["format"], self.call["output_schema"])
        self.assertEqual(body["messages"][0]["role"], "system")
        self.assertIn(json.dumps(self.call["output_schema"], separators=(",", ":")), body["messages"][0]["content"])
        self.assertEqual(json.loads(body["messages"][1]["content"]), self.call["input_data"])

    def test_transport_failure_releases_inference_slot(self):
        self.client._opener.open.side_effect = URLError("offline")
        with self.assertRaises(ModelError):
            self.client.generate_structured(**self.call)
        self.assertTrue(self.client._slot.acquire(blocking=False))
        self.client._slot.release()

    def test_invalid_truncated_and_oversized_responses(self):
        for data in (b"not json", b"[]", b'{"done": false}',
                     b'{"done": true, "done_reason": "length"}',
                     b'{"done": true, "message": {"content": "[]"}}', b"x" * 1_000_001):
            self.respond(data)
            with self.subTest(size=len(data)), self.assertRaises(ModelError):
                self.client.generate_structured(**self.call)

    def test_default_is_real_qwen_model(self):
        client = OllamaClient()
        self.assertEqual(client.model, "qwen3.5:9b")
        self.assertEqual(client.base_url, "http://127.0.0.1:11434")

    def test_environment_settings_and_explicit_overrides(self):
        with patch.dict(os.environ, {
            "OLLAMA_MODEL": "qwen3.5:9b", "OLLAMA_BASE_URL": "http://host.docker.internal:11500/",
            "OLLAMA_TIMEOUT": "300", "OLLAMA_HOST": "0.0.0.0:9999",
        }):
            client = OllamaClient()
            self.assertEqual(client._url, "http://host.docker.internal:11500/api/chat")
            self.assertEqual(client.timeout, 300)
            client = OllamaClient("explicit-model", base_url="http://192.168.1.20:11435", timeout=60)
            self.assertEqual(client.model, "explicit-model")
            self.assertEqual(client.base_url, "http://192.168.1.20:11435")
            self.assertEqual(client.timeout, 60)

    def test_custom_host_and_port_are_used_in_actual_request(self):
        client = OllamaClient(base_url="http://host.docker.internal:11500")
        client._opener = self.client._opener
        self.respond(b'{"done": true, "message": {"content": "{}"}}')
        client.generate_structured(**self.call)
        request = client._opener.open.call_args.args[0]
        self.assertEqual(request.full_url, "http://host.docker.internal:11500/api/chat")
        self.assertEqual(json.loads(request.data)["model"], "qwen3.5:9b")

    def test_invalid_endpoint_configuration_is_rejected(self):
        for url in ("localhost:11434", "ftp://host:11434", "http://0.0.0.0:11434",
                    "http://[::]:11434", "http://host:65536", "http://host:0",
                    "http://user:secret@host:11434", "http://host:11434/api",
                    "http://host:11434?secret=1", "http://host:11434/#fragment",
                    "http://host:11434\n", ""):
            with self.subTest(url=url), self.assertRaises(ValueError):
                OllamaClient(base_url=url)
        self.assertEqual(OllamaClient(base_url="http://[::1]:11434").base_url,
                         "http://[::1]:11434")
        for timeout in ("bad", "nan", "inf", 0, -1, 1801):
            with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                OllamaClient(timeout=timeout)

    def test_connection_check_uses_tags_without_inference(self):
        self.respond(b'{"models": [{"name": "local-test-model:latest"}]}')
        self.assertEqual(self.client.check_connection()["status"], "available")
        request = self.client._opener.open.call_args.args[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(request.full_url, "http://127.0.0.1:11434/api/tags")

    def test_length_stop_reports_counts_and_limits_without_private_content(self):
        self.respond(json.dumps({
            "done": True, "done_reason": "length", "prompt_eval_count": 1093,
            "eval_count": 3002, "message": {"content": '{"secret_key": "private"}',
                                            "thinking": "private reasoning"},
        }).encode())
        with self.assertRaises(ModelError) as error:
            self.client.generate_structured(**self.call)
        message = str(error.exception)
        for fragment in ("token/context limit", "num_ctx=16384", "num_predict=4096",
                         "prompt_eval_count=1093", "eval_count=3002", "--show-config"):
            self.assertIn(fragment, message)
        self.assertNotIn("secret_key", message)
        self.assertNotIn("private", message)
        self.assertTrue(self.client._slot.acquire(blocking=False))
        self.client._slot.release()

    def test_unfinished_response_is_not_misdiagnosed_as_token_limit(self):
        self.respond(b'{"done": false, "message": {"content": "{}"}}')
        with self.assertRaisesRegex(ModelError, "did not finish"):
            self.client.generate_structured(**self.call)

    def test_thinking_only_response_is_not_accepted_as_final_answer(self):
        self.respond(b'{"done": true, "message": {"content": "", "thinking": "private"}}')
        with self.assertRaisesRegex(ModelError, "no final JSON content"):
            self.client.generate_structured(**self.call)

    def test_missing_model_and_malformed_model_list_fail(self):
        for data in (b'{"models": []}', b'{"models": [{}]}', b'{}'):
            self.respond(data)
            with self.subTest(data=data), self.assertRaises(ModelError):
                self.client.check_connection()

    def test_cli_defaults_to_ollama_and_passes_connection_options(self):
        from quizAgent.demo import main
        with patch("sys.argv", ["demo", "--check-connection"]), \
                patch("quizAgent.demo.OllamaClient") as client, patch("builtins.print"):
            client.return_value.check_connection.return_value = {"status": "available"}
            main()
            client.assert_called_once_with(None, base_url=None, timeout=None, config_path=None)
            client.return_value.check_connection.assert_called_once()
        with patch("sys.argv", ["demo", "--check-connection", "--ollama-url",
                                "http://host.docker.internal:11500", "--timeout", "300"]), \
                patch("quizAgent.demo.OllamaClient") as client, patch("builtins.print"):
            client.return_value.check_connection.return_value = {"status": "available"}
            main()
            client.assert_called_once_with(None, base_url="http://host.docker.internal:11500", timeout=300, config_path=None)


if __name__ == "__main__":
    unittest.main()
