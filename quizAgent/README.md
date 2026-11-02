Quiz Agent

Generates and grades random or topic-specific quizzes using the shared RAG and
LLM clients. Supports multiple-choice, true/false, and open-ended questions.

Structure

```text
quizAgent/
├── demo.py         # Terminal entry point
├── mock_backend.py # Attempts, private answer keys, and result storage
├── errors.py       # Quiz validation and attempt errors
├── agent.py        # generate_quiz() and grade_quiz() entry points
├── generation.py   # Retrieve evidence and generate quizzes
├── grading.py      # Compare fixed answers and evaluate open-ended responses
├── schemas.py      # Request and model-output structures
├── validation.py   # Check questions, citations, rubrics, and scores
├── prompts/        # Generation and grading instructions
└── tests/          # Agent and shared-client tests
```

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

The demo uses real Ollama inference with sample course material. The mock backend
lives here; reusable services live in [llm/](../llm/README.md) and
[rag/](../rag/README.md).

Commands

Use Python 3.10+ and run from the repository root. On Windows, replace `python3`
with `py -3`. First follow the [Ollama configuration instructions](../llm/README.md).

```bash
# Take a quiz using the configured Ollama model
python3 -m quizAgent.demo --interactive
python3 -m quizAgent.demo --interactive --topic firewall

# Run without Ollama
python3 -m quizAgent.demo --mock

# Run tests
python3 -m unittest discover -s quizAgent/tests -v
```
