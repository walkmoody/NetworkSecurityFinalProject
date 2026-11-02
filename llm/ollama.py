"""Host-configurable Ollama adapter shared by Quiz and Q&A workflows."""

import json
from threading import BoundedSemaphore
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from llm.contracts import ModelError
from .config import OllamaSettings


class _NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ModelError("Local model endpoint attempted a redirect.")


class OllamaClient:
    """Reuse this instance for Q&A and quizzes to serialize local inference.

    Assumes the runtime and model are already installed and locally configured.
    It never downloads models or falls back to a mock or another service.
    The operator configures the host URL, never the student or the model.
    """

    def __init__(self, model: str | None = None, *, base_url: str | None = None,
                 timeout: float | None = None, config_path: str | None = None):
        self.settings = OllamaSettings.load(config_path, model=model, base_url=base_url, timeout=timeout)
        self.model = self.settings.model
        self.timeout = self.settings.timeout
        self.base_url = self.settings.base_url
        self._url = self.base_url + "/api/chat"
        self._opener = build_opener(ProxyHandler({}), _NoRedirects())
        self._slot = BoundedSemaphore(1)

    def _request_json(self, request: Request) -> dict:
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                raw = response.read(1_000_001)
            if len(raw) > 1_000_000:
                raise ModelError("Model response exceeded the size limit.")
            result = json.loads(raw)
            if not isinstance(result, dict):
                raise ModelError("Ollama returned an invalid JSON envelope.")
            return result
        except HTTPError as exc:
            raise ModelError(
                f"Ollama at {self.base_url} returned HTTP {exc.code}; check the API and installed model."
            ) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise ModelError(
                f"Cannot reach Ollama at {self.base_url}; check host binding, port, firewall, and timeout."
            ) from exc
        except (ValueError, TypeError) as exc:
            raise ModelError("Ollama returned invalid JSON.") from exc

    def check_connection(self) -> dict:
        """Check server reachability and model installation without inference."""
        response = self._request_json(Request(self.base_url + "/api/tags"))
        models = response.get("models")
        if not isinstance(models, list) or any(
            not isinstance(item, dict) or not isinstance(item.get("name"), str)
            for item in models
        ):
            raise ModelError("Ollama returned an invalid model list.")
        names = {item["name"] for item in models}
        canonical = self.model if ":" in self.model.rsplit("/", 1)[-1] else self.model + ":latest"
        if self.model not in names and canonical not in names:
            raise ModelError(f"Ollama is reachable, but {self.model} is not installed on that host.")
        return {"base_url": self.base_url, "model": self.model, "status": "available"}

    def generate_structured(self, *, task, instructions, input_data, output_schema):
        payload = json.dumps({
            "model": self.model, "stream": False, "format": output_schema,
            "think": self.settings.think,
            "options": {"temperature": self.settings.temperature,
                        "num_predict": self.settings.num_predict,
                        "num_ctx": self.settings.num_ctx},
            "messages": [
                {"role": "system", "content": instructions + "\nReturn JSON matching this output schema:\n"
                 + json.dumps(output_schema, separators=(",", ":"))},
                {"role": "user", "content": json.dumps(input_data)},
            ],
        }).encode()
        if len(payload) > 200_000:
            raise ModelError("Model request exceeds the prototype size limit.")
        if not self._slot.acquire(timeout=self.timeout):
            raise ModelError("Local model is busy; try again later.")
        try:
            request = Request(self._url, data=payload,
                              headers={"Content-Type": "application/json"})
            envelope = self._request_json(request)
            if envelope.get("done_reason") == "length":
                # Report limits/counts only: responses can contain private answer keys.
                counts = []
                for key in ("prompt_eval_count", "eval_count"):
                    if type(envelope.get(key)) is int:
                        counts.append(f"{key}={envelope[key]}")
                details = ", ".join([
                    f"num_ctx={self.settings.num_ctx}",
                    f"num_predict={self.settings.num_predict}",
                    f"think={str(self.settings.think).lower()}", *counts,
                ])
                raise ModelError(
                    f"Ollama stopped at a token/context limit ({details}); no partial result was accepted. "
                    "Increase num_ctx if the context filled up, or num_predict if the output cap was reached "
                    "(leave context space for the prompt). Keep think=false for quiz JSON output, "
                    "or request fewer questions. Check the effective settings with --show-config."
                )
            if envelope.get("done") is not True:
                raise ModelError("Ollama did not finish its non-streaming response (done is not true); no partial result was accepted.")
            content = envelope["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise ModelError("Ollama returned no final JSON content. Check think=false and the context/output limits.")
            result = json.loads(content)
            if not isinstance(result, dict):
                raise ModelError("Model did not return a JSON object.")
            return result
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise ModelError("Local model returned an invalid response.") from exc
        finally:
            self._slot.release()
