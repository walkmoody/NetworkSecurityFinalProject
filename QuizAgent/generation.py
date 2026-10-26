"""Question generation workflow; implementation intentionally left for the next step."""

from .interfaces import LlmClient, RagClient
from .models import AuthorizedScope, QuizDraft, QuizRequest


async def generate_quiz(request: QuizRequest, *, scope: AuthorizedScope, rag: RagClient, llm: LlmClient,) -> QuizDraft:
    # Planned sequence:

    # 1. Validate mode, topic and bounded question counts.
    # 2. Retrieve approved evidence through rag.retrieve_quiz_evidence().
    # 3. Build quiz-specific instructions with evidence isolated as untrusted data.
    # 4. Call llm.generate_structured(task="quiz_generation", ...).
    # 5. Validate structure, counts, keys, rubrics, evidence IDs and factual support.
    # 6. Return a private QuizDraft, or a controlled error for insufficient evidence.
    raise NotImplementedError("Quiz generation is not implemented yet.")
