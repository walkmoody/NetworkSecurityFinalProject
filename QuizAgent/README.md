# Quiz Agent
The Quiz Agent will generate and grade quizzes using our local Network Security course materials. It supports random and topic-specific quizzes with multiple-choice, true/false, and open-ended questions. This README describes the current code structure and how we plan to connect it to the backend, RAG, and shared LLM.

## Current code

Only the basic Python structure is in place. Generation and grading still raise
`NotImplementedError`, and no RAG or LLM connection has been implemented. There
are no third-party Python dependencies yet.

`models.py` contains the initial data types. The JSON examples later in this file
are design sketches, not exact representations of those classes or finished API
responses. We still need to agree on the final formats with the backend developer.

```text
QuizAgent/
├── __init__.py      # Exports QuizAgent
├── agent.py         # Backend entry points: generate() and grade()
├── models.py        # Internal requests, evidence, private drafts and results
├── interfaces.py    # Contracts for shared RAG and local LLM clients
├── generation.py    # Question-generation workflow placeholder
├── grading.py       # Answer-evaluation workflow placeholder
└── README.md
```

### How the components connect

```text
Backend routes → QuizAgent → generation / grading
                                  ├── RagClient → shared retrieval service
                                  └── LlmClient ─┐
Q&A Agent → its own prompts → LlmClient ──────────┴→ shared local LLM runtime
```

The backend creates a `QuizAgent` and passes it the RAG and LLM clients:

```python
from QuizAgent import QuizAgent
from QuizAgent.models import AuthorizedScope, QuizRequest

# Example only: the shared clients still need to be implemented.
quiz_agent = QuizAgent(rag=shared_rag, llm=shared_llm)

# Inside an authenticated async handler, after request validation:
request = QuizRequest(
    course_id="CS5342",
    mode="topic",
    topic_id="firewall",
    question_counts={"multiple_choice": 3, "true_false": 2, "open_ended": 1},
)
scope = AuthorizedScope(course_ids=authorized_course_ids)  # From backend auth.
draft = await quiz_agent.generate(request, scope=scope)  # Not implemented yet.
# Backend assigns IDs, stores the private draft, and returns public questions only.
```

- **Backend:** checks user access, validates requests, assigns IDs, and stores quiz
  keys and results. It builds the grading request from saved records. The browser
  sends only the attempt ID and student answers.
- **Quiz Agent:** builds prompts, generates questions, checks model output, grades
  answers, and returns feedback.
- **Shared RAG:** retrieves allowed course material, selects topics for random
  quizzes, and keeps source information and document versions. The current scope
  lists allowed courses. Private user uploads would need additional access checks.
- **Shared LLM client:** connects to the local model and handles configuration,
  timeouts, and limits on simultaneous requests. Both agents can use the same
  runtime while keeping their prompts and conversation data separate.

The RAG and LLM implementations should live in the shared part of the project.
When we connect both agents, the common LLM interface should move there too, so
the Q&A Agent does not have to import from `QuizAgent`. The Quiz Agent will use
these services rather than start its own model or manage the vector database.

### Details to agree on before integration

- Use stable MCQ option IDs (`"A"`, `"B"`, etc.), Boolean true/false answers and
  string open-ended answers. Adapt the frontend's current numeric MCQ indexes.
- Preserve chunk IDs, source locations and corpus versions for citations and grading.
- Implement separate public question and post-submission result schemas in the
  backend. Never serialize `QuestionDraft` directly into a pre-submission response.
- Dataclasses and type hints do not validate runtime data. Add explicit validation
  before these contracts process browser input or model output. The dictionaries
  within frozen dataclasses are also mutable; these objects are not storage locks.
- Define failure responses for insufficient evidence, unavailable source versions,
  model timeouts and invalid model output before connecting the frontend.

The next step is to add input/output checks and MCQ/true-false grading. We can
use fake RAG and LLM clients to test the flow while the shared services are being
built, then add question generation and rubric-based grading.

## Contents

- [1. Overview](#1-overview)
- [2. Backend ↔ Quiz Agent Interface](#2-backend--quiz-agent-interface)
- [3. Quiz Agent ↔ RAG Interface](#3-quiz-agent--rag-interface)
- [4. Quiz Agent ↔ Local LLM Runtime Integration](#4-quiz-agent--local-llm-runtime-integration)
- [5. External Data → RAG Ingestion Pipeline](#5-external-data--rag-ingestion-pipeline)
- [6. Quiz Agent Attack-Surface Analysis](#6-quiz-agent-attack-surface-analysis)
- [7. Integration Considerations](#7-integration-considerations)

## 1. Overview

A student chooses a random quiz or a topic, answers the questions, and receives
a score with explanations and citations. Questions and feedback should use the
local course knowledge base, including any approved external documents added to it.

**General communication flow:**

```text
Frontend → Backend → (Quiz Agent ↔ RAG / Local LLM) → Backend → Frontend
```

## 2. Backend ↔ Quiz Agent Interface

The backend calls `generate()` and `grade()`. It checks permissions, manages quiz
attempts, and stores answer keys. The Quiz Agent returns its results to the
backend, which decides what can be sent to the frontend.

### 2.1 Quiz Generation

**Process:** Backend receives quiz request → validates settings and permissions → Quiz Agent retrieves approved evidence → generates questions and internal answer keys → validates questions and citations → backend stores private quiz data → returns sanitized questions to frontend.


**Request from Backend to Quiz Agent**

```json
{
  "course_id": "CS5342",
  "mode": "topic",
  "topic_id": "firewall",
  "question_counts": {
    "multiple_choice": 3,
    "true_false": 2,
    "open_ended": 1
  },
  "authorized_scope": {
    "course_ids": ["CS5342"]
  }
}
```

The request identifies the course, quiz mode, optional topic, and number of questions for each format. In random mode, topic_id could be set to null.


**Response from Quiz Agent to Backend**

The agent returns a private draft with questions, answer keys, rubrics,
explanations, and evidence references. This example shows one MCQ:

```json
{
  "corpus_version": "v3",
  "questions": [
    {
      "type": "multiple_choice",
      "text": "What is the primary purpose of a firewall?",
      "options": {
        "A": "Encrypt data",
        "B": "Filter network traffic",
        "C": "Generate passwords",
        "D": "Resolve domain names"
      },
      "answer_key": {
        "correct_answer": "B",
        "explanation": "A firewall filters traffic according to security policies.",
        "evidence_ids": ["chunk_42"]
      }
    }
  ]
}
```

The example shows one question for readability; the complete response must satisfy the requested question counts.
For true/false questions, the answer key contains a Boolean value. For open-ended questions, it contains a reference answer and a rubric specifying grading criteria and maximum points.

**Do not send this draft directly to the frontend. It contains the answers.**

The backend assigns quiz, question, and attempt IDs, then stores the keys and
rubrics locally. Before submission, the frontend receives only the question IDs,
text, and answer options.

### 2.2 Submission and Grading

**Process:** Student submits answers → backend validates attempt ownership and state → retrieves locked answer keys and rubrics → Quiz Agent grades answers → validates grading output → backend commits the final grade → returns feedback and citations.

The frontend submits an attempt ID and the student’s answers. The backend checks
that the attempt belongs to that student and can still be submitted, then loads
the saved keys and rubrics to build the grading request.

**Request from Backend to Quiz Agent**

```json
{
  "attempt_id": "attempt_73",
  "corpus_version": "v3",
  "items": [
    {
      "question_id": "q101",
      "type": "multiple_choice",
      "student_answer": "B",
      "correct_answer": "B",
      "max_points": 2,
      "evidence_ids": ["chunk_42"]
    },
    {
      "question_id": "q102",
      "type": "open_ended",
      "question": "Explain the purpose of a firewall.",
      "student_answer": "It filters network traffic.",
      "rubric": [
        {
          "criterion_id": "c1",
          "concept": "Traffic filtering",
          "max_points": 3
        },
        {
          "criterion_id": "c2",
          "concept": "Security policy enforcement",
          "max_points": 2
        }
      ],
      "evidence_ids": ["chunk_42"]
    }
  ]
}
```

Grading depends on the question type:

- Multiple choice and true/false: Deterministic Python comparison against the stored answer key.
- Open-ended: Local LLM evaluation against a predefined, locked rubric and supporting source material.

MCQ and true/false answers do not need a model call. Open-ended answers need
rubric-based evaluation, including partial credit.

**Response from Quiz Agent to Backend**

```json
{
  "attempt_id": "attempt_73",
  "status": "graded",
  "results": [
    {
      "question_id": "q101",
      "points_awarded": 2,
      "max_points": 2,
      "feedback": "Correct.",
      "evidence_ids": ["chunk_42"]
    },
    {
      "question_id": "q102",
      "points_awarded": 3,
      "max_points": 5,
      "criteria_scores": [
        {"criterion_id": "c1", "points": 3},
        {"criterion_id": "c2", "points": 0}
      ],
      "feedback": "Traffic filtering was identified, but security policy enforcement was not explained.",
      "evidence_ids": ["chunk_42"]
    }
  ]
}
```

Before saving the final score, the backend checks question IDs, rubric criteria,
and score limits. Invalid results should return an error; uncertain grades should
be marked for review.

### 2.3 Division of Responsibilities

| Backend | Quiz Agent |
| --- | --- |
| Authentication and authorization | Question generation |
| Request validation and resource limits | Generation-quality validation |
| Quiz and attempt ID assignment | Answer-key and rubric proposals |
| Private answer-key storage | Multiple choice/TF deterministic grading |
| Quiz submission state management | Open-ended rubric evaluation |
| Final score computation and commit | Feedback and evidence references |
| Frontend response filtering | Structured grading results |

The model proposes content and scores. Backend code controls access to records
and saves the final grade.

## 3. Quiz Agent ↔ RAG Interface

The Quiz Agent asks the shared RAG system for course passages through `RagClient`.
RAG checks which documents the user may access and returns the text with its source
information. The agent does not read or change the vector database directly.

### 3.1 Evidence Retrieval for Quiz Generation

Example request:

```json
{
  "operation": "retrieve_quiz_evidence",
  "course_id": "CS5342",
  "mode": "topic",
  "topic_id": "firewall",
  "max_chunks": 5,
  "authorized_scope": {
    "course_ids": ["CS5342"]
  }
}
```

For topic-specific generation, retrieval prioritizes approved material related to the requested topic.
For random generation, the retrieval layer selects from different approved course topics. Random sampling should be handled by application logic rather than an LLM-generated search query.
Example RAG response:

```json
{
  "corpus_version": "v3",
  "evidence": [
    {
      "chunk_id": "chunk_42",
      "document_id": "lecture_04",
      "document_version": "1",
      "title": "Network Security Lecture 4",
      "topic": "firewall",
      "page": 12,
      "text": "A firewall filters network traffic according to a defined security policy...",
      "source_url": null,
      "source_type": "lecture"
    }
  ]
}
```

The agent needs the passage text, not just its embedding, to write and check a
question. Document IDs, page numbers, and URLs let us show where an answer came from.

### 3.2 Evidence Retrieval for Grading

For grading, the agent should retrieve the same approved evidence associated with the original question.
The proposed operation is:

```python
get_evidence_by_ids(
    evidence_ids,
    corpus_version,
    authorized_scope
)
```

Grading should use the same source version used to generate the question, even
if the knowledge base has since changed. If that version is missing, return an
error instead of substituting another passage.

### 3.3 RAG Security Requirements

The shared retrieval layer needs to enforce these rules:

- Only approved and authorized course documents may be retrieved.
- Each evidence chunk must retain stable source and version information.
- Retrieval results must be bounded in number and size.
- The Quiz Agent must have read-only access to the knowledge base.
- Retrieved material must be treated as untrusted data, not executable instructions.

Both agents rely on these checks in the shared retrieval layer.

## 4. Quiz Agent ↔ Local LLM Runtime Integration

The plan is to run one local model runtime, such as Ollama, for both agents. Each
agent sends its own prompts through an LLM client. This avoids loading a separate
copy of the model for each agent.

The Quiz Agent has two model tasks:

| Question Generator | Open-Ended Grader |
| --- | --- |
| Receives approved RAG evidence | Receives student answer, locked rubric, and evidence |
| Generates questions and proposed keys | Evaluates the answer against rubric criteria |
| Produces a structured quiz draft | Produces structured criterion-level scores |
| Cannot modify student grades | Cannot modify answer keys or rubrics |

Both workflows may call the same local model through separate prompts and structured output schemas.

**Proposed integration**

The following calls sketch the two tasks; prompt text and output schemas still
need to be defined.

For quiz generation:

```python
llm_client.generate_structured(
    task="quiz_generation",
    input_data=approved_evidence,
    output_schema=QuizDraftSchema
)
```

For grading:

```python
llm_client.generate_structured(
    task="quiz_grading",
    input_data=grading_context,
    output_schema=GradeResultSchema
)
```

We want structured model output so the agent can check required fields and score
limits. A valid structure does not prove that an answer is correct; we still need
to check it against the source material.

We also need to agree with the Q&A developer on request limits. Sharing the model
should not mean sharing conversation history, permissions, or private quiz data.

## 5. External Data → RAG Ingestion Pipeline

Both agents will use the same document ingestion pipeline. It will process course
files and approved website content before either agent retrieves them.

**Proposed pipeline**

1. Source intake:
   - Approved website → Restricted download gateway → Quarantine storage
   - Lecture PDF / PPTX / Textbook → Quarantine storage
2. Quarantine storage → File validation → Sandboxed text extraction.
3. Extracted content → Source review and approval → Chunking and metadata generation.
4. Chunks → Local embedding model → Staged vector index and integrity check.
5. Verified index → Published approved index → Vector database and source store.

**Design considerations for the ingestion pipeline**

Files need validation before extraction, and extracted text needs review before
indexing. Embeddings, stored documents, and retrieval stay local. Any internet
downloads should go through the restricted gateway. For web sources, keep the URL,
title, publisher, and retrieval date so citations can be checked later.

## 6. Quiz Agent Attack-Surface Analysis

We need to protect course documents and embeddings, answer keys and rubrics,
student answers and grades, and system credentials. The tables below list the
risks we have identified and the controls we plan to add.

### 6.1 Network Attack Surface

TODO: document exposed endpoints, local service access, and external lookup traffic.

### 6.2 Software Attack Surface

| Attack Surface | Potential Threat | Proposed Mitigation |
| --- | --- | --- |
| PDF/PPTX parsing | Parser exploitation or decompression bombs | Sandboxed extraction, size/time/memory limits |
| Prompt assembly | Instructions embedded in retrieved documents or student answers | Separate instructions from untrusted data, restrict model capabilities |
| Quiz storage | SQL injection or unauthorized answer-key access | Parameterized queries, protected storage, backend authorization |
| Quiz generator | Incorrect answers, fabricated evidence references | Schema validation, correctness checks, citation verification |
| Open-ended grader | Prompt injection or incorrect rubric evaluation | Locked rubrics, criterion-level scoring, validation and evaluation tests |
| Model runtime | Compromised artifacts or vulnerable dependencies | Trusted downloads, dependency pinning, integrity checks |
| Software updates | Malicious or incompatible packages | Controlled updates and dependency review |

### 6.3 Human Attack Surface

| Actor | Potential Threat | Proposed Mitigation |
| --- | --- | --- |
| Developer | Accidentally exposes API keys or weakens validation logic | Secret scanning, code review, configuration checks |
| Instructor | Uploads incorrect, malicious, or confidential materials | Restricted upload access, extraction preview and source approval |
| Student | Generates excessive quizzes, exhausting resources | Maximum question counts, concurrency limits and timeouts |
| Student | Attempts to manipulate grading through open-ended responses | Fixed rubrics, untrusted-input isolation and grade validation |

For the first version, we will focus on access checks, keeping answer keys private,
limiting resource use, and checking grades. Student monitoring and broader
anti-cheating features are outside the current scope.

### 6.4 Overall Security Strategy

Access checks and grade storage belong in application code. A prompt must not be
able to grant permissions, change a stored answer key, or save an unchecked grade.
The model’s output needs validation before the backend uses it.

Initial security tests should check that:

- Prompt injection cannot alter protected grading rules.
- Answer keys are absent from pre-submission frontend responses.
- Unauthorized users cannot access another student's attempts.
- Invalid source citations are rejected.
- Excessive quiz requests are bounded.
- Offline operation does not transmit private course material externally.

## 7. Integration Considerations

| Topic | Decision Required |
| --- | --- |
| Internal schemas | Agree on JSON(or Pydantic) contracts and validation responsibilities |
| RAG retrieval | Agree on evidence IDs, source metadata, authorization scope, and versioning |
| LLM service | Select the shared runtime, model, and resource-management approach |
| Private assessment data | Confirm backend ownership of answer keys, rubrics, and attempts |
| Error handling | Standardize generation failure, grading failure, and validation error responses |
| Integration testing | Establish sample requests and expected responses for each interface |
