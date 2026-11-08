"""The only entry points a backend needs; share client instances with Q&A."""

from llm.contracts import LLMClient
from .generation import generate_quiz
from .grading import grade_quiz
from .schemas import GenerateQuizRequest, GradeQuizRequest


class QuizAgent:
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def generate_quiz(self, request: GenerateQuizRequest) -> dict:
        return generate_quiz(request, self.llm)

    def grade_quiz(self, request: GradeQuizRequest) -> dict:
        return grade_quiz(request, self.llm)
