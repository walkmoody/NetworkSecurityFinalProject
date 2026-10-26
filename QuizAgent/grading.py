"""Answer evaluation workflow; implementation intentionally left for the next step."""

from .interfaces import LlmClient, RagClient
from .models import AuthorizedScope, GradeResult, GradingRequest


async def grade_quiz(request: GradingRequest, *, scope: AuthorizedScope, rag: RagClient, llm: LlmClient) -> GradeResult:
   #  Planned sequence:

   #  1. Validate answer types and stored assessment structure.
   #  2. Load original evidence with rag.get_evidence_by_ids(); fail if unavailable.
   #  3. Grade MCQ and true/false with strict typed comparisons, without the LLM.
   #  4. Call llm.generate_structured(task="quiz_grading", ...) for open-ended items,
   #     treating student answers and evidence as untrusted data.
   #  5. Validate criterion IDs and finite score bounds; compute totals in code.
   #  6. Return feedback and evidence IDs. Backend commits the final grade.
    raise NotImplementedError("Quiz grading is not implemented yet.")
