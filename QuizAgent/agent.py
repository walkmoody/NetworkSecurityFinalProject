# Backend-facing entry point. No HTTP routes, database writes, or model loading.
from .generation import generate_quiz
from .grading import grade_quiz
from .interfaces import LlmClient, RagClient
from .models import AuthorizedScope, GradeResult, GradingRequest, QuizDraft, QuizRequest

class QuizAgent:
    def __init__(self, rag: RagClient, llm: LlmClient) -> None:
        self._rag = rag
        self._llm = llm
    # Return a private draft for the backend to validate, assign IDs and store
    async def generate(self, request: QuizRequest, *, scope: AuthorizedScope) -> QuizDraft:
        return await generate_quiz(request, scope=scope, rag=self._rag, llm=self._llm)
    # Backend checks attempt ownership/state and loads stored keys first
    async def grade(self, request: GradingRequest, *, scope: AuthorizedScope) -> GradeResult:
        return await grade_quiz(request, scope=scope, rag=self._rag, llm=self._llm)
