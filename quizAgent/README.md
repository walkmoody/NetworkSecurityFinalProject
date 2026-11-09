Quiz Agent

Generates and grades random or topic-specific quizzes using `rag_pipeline` and
the shared LLM client. Supports multiple-choice, true/false, and open-ended questions.
Random mode retrieves course key concepts through semantic search; it does not
randomly sample documents.

Structure

```text
quizAgent/
├── demo.py         # Terminal entry point
├── mock_backend.py # Attempts, private answer keys, and result storage
├── errors.py       # Quiz validation and attempt errors
├── agent.py        # generate_quiz() and grade_quiz() entry points
├── generation.py   # Retrieve evidence and generate quizzes
├── evidence.py     # Load original pipeline chunks and check the corpus version
├── grading.py      # Compare fixed answers and evaluate open-ended responses
├── schemas.py      # Request and model-output structures
├── validation.py   # Check questions, citations, rubrics, and scores
└── prompts/        # Generation and grading instructions
```

Tests live in [`../tests/test_quiz_agent.py`](../tests/test_quiz_agent.py).

Flow

```text
Generation:
Request → Retrieve evidence → LLM generates quiz → Validate → Mock backend stores keys
                                                         → Return public questions

Grading:
Submission → Load stored keys and original evidence
           → MCQ / true-false: compare answers
           → Open-ended: LLM evaluates the locked rubric
           → Validate scores → Mock backend stores results → Return feedback and citations
```

The demo uses real Ollama inference with indexed course material. The mock backend
lives here; reusable services live in [llm/](../llm/README.md) and
[rag_pipeline/](../rag_pipeline/README.md).

If every indexed document is directly under `data/`, the pipeline stores blank
course labels. The quiz treats that index as one corpus and uses the requested
course name as its label. When course folders are indexed, `--course` must match
an indexed folder; retrieval and grading stay within that course.

`MockBackend` simulates the HTTP backend's quiz response bodies and workflow in
process. Create one instance per session and pass course memberships selected by
the backend, for example `MockBackend(QuizAgent(model), {"student": ("NetworkSecurity",)})`.
Use `create_quiz`, `submit_answers`, and `retry_grading` with that server-selected
user ID. Public quizzes omit answer keys; grading uses the original chunk IDs and
manifest version. Storage is in memory, and user IDs simulate authentication.
Failed grading marks the attempt `review_required`; retries reuse the locked
submitted answers. A changed manifest or missing original chunks prevents grading
existing attempts. For HTTP integration, see the [backend README](../backend/README.md).

Commands

Use Python 3.10+ and run from the repository root. On Windows, replace `python3`
with `py -3`. First follow the [Ollama configuration instructions](../llm/README.md).
Install dependencies, create the approved-document manifest, and build the index
using the [RAG pipeline setup instructions](../rag_pipeline/README.md#installation).
`--mock` skips Ollama but still uses the index and embedding model.

```bash
# Take a quiz using the configured Ollama model
python3 -m quizAgent.demo --interactive --course NetworkSecurity
python3 -m quizAgent.demo --interactive --course NetworkSecurity --topic firewall

# Run without Ollama
python3 -m quizAgent.demo --mock

# Inspect Ollama settings or check connectivity
python3 -m quizAgent.demo --show-config
python3 -m quizAgent.demo --check-connection

# Run tests
python3 -m pytest tests/test_quiz_agent.py -q
```
