"""Inference interface shared by the Quiz and Q&A agents."""

from typing import Any, Protocol


class ModelError(Exception):
    """Controlled model transport or response failure."""


class LLMClient(Protocol):
    def generate_structured(
        self, *, task: str, instructions: str, input_data: dict,
        output_schema: dict,
    ) -> dict[str, Any]: ...
