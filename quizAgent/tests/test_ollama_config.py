import io
import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from llm import OllamaClient, OllamaSettings


class OllamaConfigTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {}, clear=True)
        env.start()
        self.addCleanup(env.stop)
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / "ollama.json"
        self.data = {
            "host": "0.0.0.0:11500", "base_url": "http://host.docker.internal:11500",
            "model": "qwen3.5:9b", "timeout": 300, "temperature": 0.2, "num_predict": 2048,
            "num_ctx": 8192, "think": False,
        }
        self.write(self.data)

    def write(self, data):
        self.path.write_text(json.dumps(data), encoding="utf-8")

    def test_file_settings_control_client_and_inference(self):
        client = OllamaClient(config_path=self.path)
        self.assertEqual(client.settings.host, "0.0.0.0:11500")
        self.assertEqual(client.base_url, "http://host.docker.internal:11500")
        client._opener = Mock()
        client._opener.open.return_value = io.BytesIO(b'{"done": true, "message": {"content": "{}"}}')
        client.generate_structured(task="test", instructions="test", input_data={}, output_schema={})
        request = client._opener.open.call_args.args[0]
        self.assertEqual(request.full_url, client.base_url + "/api/chat")
        self.assertEqual(json.loads(request.data)["options"], {"temperature": 0.2, "num_predict": 2048, "num_ctx": 8192})
        self.assertFalse(json.loads(request.data)["think"])
        self.assertEqual(client._opener.open.call_args.kwargs["timeout"], 300)

    def test_precedence_and_environment_selected_file(self):
        with patch.dict(os.environ, {
            "OLLAMA_CONFIG": str(self.path), "OLLAMA_MODEL": "env-model",
            "OLLAMA_TIMEOUT": "90", "OLLAMA_TEMPERATURE": "0.5", "OLLAMA_NUM_PREDICT": "512",
            "OLLAMA_NUM_CTX": "32768", "OLLAMA_THINK": "true",
        }):
            settings = OllamaSettings.load(timeout=45)
            self.assertEqual(settings.model, "env-model")
            self.assertEqual(settings.timeout, 45)
            self.assertEqual(settings.base_url, self.data["base_url"])
            self.assertEqual(settings.temperature, 0.5)
            self.assertEqual(settings.num_predict, 512)
            self.assertEqual(settings.num_ctx, 32768)
            self.assertTrue(settings.think)
        with patch.dict(os.environ, {"OLLAMA_CONFIG": "missing.json"}):
            self.assertEqual(OllamaSettings.load(self.path).model, "qwen3.5:9b")

    def test_missing_or_malformed_file_does_not_silently_use_defaults(self):
        for content in ("not JSON", "[]", '{"unknown": 1}', '{"model": null}'):
            self.path.write_text(content, encoding="utf-8")
            with self.subTest(content=content), self.assertRaises(ValueError):
                OllamaSettings.load(self.path)
        self.path.unlink()
        with self.assertRaises(ValueError):
            OllamaSettings.load(self.path)

    def test_invalid_settings_rejected(self):
        for name, value in (("timeout", True), ("timeout", 0), ("temperature", "nan"),
                            ("temperature", 3), ("num_predict", 1.5), ("num_predict", -1),
                            ("num_predict", True), ("host", "http://localhost:11434"),
                            ("host", "localhost"), ("host", "localhost:65536"),
                            ("base_url", "http://0.0.0.0:11434"), ("num_ctx", 0),
                            ("num_ctx", 8192.5), ("num_ctx", True), ("num_ctx", 2048),
                            ("think", "false"), ("think", 0)):
            self.write({**self.data, name: value})
            with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                OllamaSettings.load(self.path)

    def test_thinking_environment_requires_explicit_boolean(self):
        with patch.dict(os.environ, {"OLLAMA_THINK": "false"}):
            self.assertFalse(OllamaSettings.load(self.path).think)
        with patch.dict(os.environ, {"OLLAMA_THINK": "sometimes"}), self.assertRaises(ValueError):
            OllamaSettings.load(self.path)

    def test_partial_file_uses_field_defaults(self):
        self.write({"timeout": 300})
        settings = OllamaSettings.load(self.path)
        self.assertEqual(settings.timeout, 300)
        self.assertEqual(settings.model, "qwen3.5:9b")

    def test_default_file_location_does_not_depend_on_working_directory(self):
        original = Path.cwd()
        expected = OllamaSettings.load()
        try:
            os.chdir(self.path.parent)
            self.assertEqual(OllamaSettings.load(), expected)
        finally:
            os.chdir(original)

    def test_show_config_uses_file_and_cli_overrides_without_network(self):
        from quizAgent.demo import main
        with patch("sys.argv", ["demo", "--config", str(self.path), "--timeout", "60", "--show-config"]), \
                patch("sys.stdout", new_callable=io.StringIO) as output, \
                patch("llm.ollama.build_opener") as opener:
            main()
            settings = json.loads(output.getvalue())
            self.assertEqual(settings["timeout"], 60)
            self.assertEqual(settings["base_url"], self.data["base_url"])
            opener.return_value.open.assert_not_called()


if __name__ == "__main__":
    unittest.main()
