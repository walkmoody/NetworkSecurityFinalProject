# Dependency contracts; implementations belong to the shared service layer.
# Protocols allow fixtures now and real RAG/model adapters later, without coupling
# the agent to a vector database, HTTP framework, or model vendor.

from typing import Any, Protocol

from .models import AuthorizedScope, EvidenceBundle, QuizRequest


class RagClient(Protocol):
    async def retrieve_quiz_evidence(self, request: QuizRequest, 
        *, scope: AuthorizedScope) -> EvidenceBundle:
        """Return bounded, authorized evidence; sample diverse topics in random mode."""
        ...

    async def get_evidence_by_ids(self, evidence_ids: tuple[str, ...], 
        *, course_id: str, corpus_version: str, scope: AuthorizedScope) -> EvidenceBundle:
        """Return exact authorized versions, or fail if unavailable."""
        ...

class LlmClient(Protocol):
    async def generate_structured(self, *, task: str, system_prompt: str,
        input_data: dict[str, Any], output_schema: dict[str, Any]) -> dict[str, Any]:
        """Call the shared local runtime using a JSON Schema output contract.

        Each call is independent: no shared conversation history between agents.
        The shared adapter owns runtime configuration, timeouts and concurrency.
        Returned content remains untrusted until the calling workflow validates it.
        """
        ...
