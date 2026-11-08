"""Load shared Ollama settings independently of agents and transport."""

import json
import math
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from urllib.parse import urlsplit

DEFAULT_CONFIG_PATH = Path(__file__).with_name("ollama.json")


def validate_base_url(value: str) -> str:
    message = "base_url must be http(s)://HOST:PORT without credentials, path, query, or fragment."
    if not isinstance(value, str) or any(c.isspace() for c in value):
        raise ValueError(message)
    try:
        parsed = urlsplit(value)
        port = parsed.port
        if (parsed.scheme not in ("http", "https") or not parsed.hostname
                or parsed.username is not None or parsed.password is not None
                or parsed.path not in ("", "/") or "?" in value or "#" in value
                or port == 0 or "\\" in value):
            raise ValueError(message)
    except ValueError as exc:
        raise ValueError(message) from exc
    if parsed.hostname in ("0.0.0.0", "::"):
        raise ValueError("Use the reachable host address, not an Ollama wildcard bind address.")
    return value.rstrip("/")


def _number(value, name, minimum, maximum):
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a number, not a Boolean.")
    try:
        number = float(value)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"{name} must be a number.") from exc
    if not math.isfinite(number) or not minimum <= number <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}.")
    return number


@dataclass(frozen=True)
class OllamaSettings:
    # host describes the server binding; it never replaces the client destination.
    host: str = "127.0.0.1:11434"
    base_url: str = "http://127.0.0.1:11434"
    model: str = ""  # no built-in model: set it in llm/ollama.json, OLLAMA_MODEL, or --model
    timeout: float = 120
    temperature: float = 0
    num_predict: int = 4096
    num_ctx: int = 16384
    think: bool = False

    def __post_init__(self):
        if not isinstance(self.host, str) or any(c.isspace() for c in self.host):
            raise ValueError("host must be a server bind address with a port, without a URL scheme.")
        try:
            host = urlsplit("//" + self.host)
            if (not host.hostname or host.port is None or host.port == 0
                    or host.username is not None or host.password is not None
                    or host.path or "?" in self.host or "#" in self.host or "\\" in self.host):
                raise ValueError()
        except ValueError as exc:
            raise ValueError("host must be a server bind address with a valid port, e.g. 0.0.0.0:11434.") from exc
        if not isinstance(self.model, str) or not self.model.strip():
            raise ValueError(
                "No Ollama model is set. Add \"model\" to llm/ollama.json, or set OLLAMA_MODEL."
            )
        object.__setattr__(self, "base_url", validate_base_url(self.base_url))
        object.__setattr__(self, "model", self.model.strip())
        timeout = _number(self.timeout, "timeout", 0, 1800)
        if timeout == 0:
            raise ValueError("timeout must be greater than zero.")
        object.__setattr__(self, "timeout", timeout)
        object.__setattr__(self, "temperature", _number(self.temperature, "temperature", 0, 2))
        tokens = _number(self.num_predict, "num_predict", 1, 32768)
        if not tokens.is_integer():
            raise ValueError("num_predict must be an integer.")
        object.__setattr__(self, "num_predict", int(tokens))
        context = _number(self.num_ctx, "num_ctx", 1024, 131072)
        if not context.is_integer():
            raise ValueError("num_ctx must be an integer.")
        object.__setattr__(self, "num_ctx", int(context))
        if self.num_predict >= self.num_ctx:
            raise ValueError("num_ctx must exceed num_predict to leave room for the prompt.")
        if type(self.think) is not bool:
            raise ValueError("think must be a JSON Boolean (true or false).")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def load(cls, config_path: str | Path | None = None, **overrides):
        """Explicit values > environment > selected JSON file > field defaults.

        The default file is relative to this module. Explicit/OLLAMA_CONFIG paths
        are relative to the caller's working directory and support ~ expansion.
        """
        selected = config_path if config_path is not None else os.environ.get("OLLAMA_CONFIG", DEFAULT_CONFIG_PATH)
        try:
            path = Path(selected).expanduser()
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError) as exc:
            raise ValueError("Cannot read Ollama configuration; check the path and JSON syntax.") from exc
        names = {field.name for field in fields(cls)}
        if not isinstance(data, dict) or set(data) - names:
            raise ValueError("Ollama configuration must be an object with only documented setting names.")
        if set(overrides) - names:
            raise ValueError("Unknown Ollama setting override.")
        for name in names:
            env_name = "OLLAMA_" + name.upper()
            if env_name in os.environ:
                value = os.environ[env_name]
                if name == "think":
                    if value.lower() not in ("true", "false"):
                        raise ValueError("OLLAMA_THINK must be true or false.")
                    value = value.lower() == "true"
                data[name] = value
        data.update({key: value for key, value in overrides.items() if value is not None})
        return cls(**data)
