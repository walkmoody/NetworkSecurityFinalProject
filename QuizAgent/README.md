# Quiz Agent
A proposed quiz generation and grading agent for network security course. This document covers the interfaces, workflows, security boundaries, and integration decisions described in the preliminary design.

## Contents

- [1. Overview](#1-overview)
- [2. Backend ↔ Quiz Agent Interface](#2-backend--quiz-agent-interface)
- [3. Quiz Agent ↔ RAG Interface](#3-quiz-agent--rag-interface)
- [4. Quiz Agent ↔ Local LLM Runtime Integration](#4-quiz-agent--local-llm-runtime-integration)
- [5. External Data → RAG Ingestion Pipeline](#5-external-data--rag-ingestion-pipeline)
- [6. Quiz Agent Attack-Surface Analysis](#6-quiz-agent-attack-surface-analysis)
- [7. Integration Considerations](#7-integration-considerations)

## 1. Overview

The Quiz agent is responsible for:
- generate/grade network security quizzes using information retrieved from the local course knowledge base
- supports two quiz generation modes: random questions and topic-specific questions
- each quiz may contain multiple-choice, true/false, and open-ended questions
- the agent evaluates student answers and generates feedback supported by citations from course materials or approved external documentation.

**General communication flow:**

```text
Frontend → Backend → (Quiz Agent ↔ RAG / Local LLM) → Backend → Frontend
```

## 2. Backend ↔ Quiz Agent Interface

The backend acts as the primary controller of the Quiz Agent. It validates requests, enforces user permissions, manages quiz attempts, stores answer keys, and returns authorized results to the frontend. The Quiz agent exposes two main operations: quiz generation and quiz grading.
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

The Quiz Agent returns an internal quiz draft containing generated questions, proposed correct answers, grading rubrics, explanations, and supporting evidence references. The following abbreviated example illustrates the private response structure:

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

**Security consideration:** This response is private and must not be passed directly to the frontend.

The backend assigns authoritative quiz, question, and attempt IDs. It stores the answer keys and rubrics in protected local storage and constructs a separate public response containing only question identifiers, text, and answer options.

### 2.2 Submission and Grading

**Process:** Student submits answers → backend validates attempt ownership and state → retrieves locked answer keys and rubrics → Quiz Agent grades answers → validates grading output → backend commits the final grade → returns feedback and citations.

The frontend initially submits an attempt ID and student answers. The backend then constructs an internal grading request containing the necessary private assessment information.

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

The Quiz Agent uses different grading methods depending on the question type:
- Multiple choice and true/false: Deterministic Python comparison against the stored answer key.
- Open-ended: Local LLM evaluation against a predefined, locked rubric and supporting source material.
The LLM is only used where semantic assessment is required. This reduces unnecessary inference overhead and grading inconsistency.

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

The backend verifies question IDs, rubric criteria, score limits, and result consistency before computing and committing the final score. Invalid or uncertain grading results should produce a controlled failure or review-required status.

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

This separation ensures that the LLM does not directly manage security-sensitive operations such as changing student grades or accessing unrelated assessment records.

## 3. Quiz Agent ↔ RAG Interface

The Quiz Agent obtains knowledge through a restricted retrieval interface exposed by the shared RAG system. It should not directly access or modify the vector database.
The RAG system is responsible for retrieving authorized, approved course material and returning the relevant source text with provenance metadata.

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

The exact source text is required because embeddings alone are insufficient for generating and verifying factual questions.
The provenance fields allow the agent to associate each answer with a specific lecture slide, textbook page, or approved web document.

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

This prevents grading from silently relying on different reference material if the knowledge base has changed after quiz generation.
If the original evidence is unavailable, grading should fail safely rather than substitute unrelated evidence.

### 3.3 RAG Security Requirements

The shared retrieval layer should enforce the following:
- Only approved and authorized course documents may be retrieved.
- Each evidence chunk must retain stable source and version information.
- Retrieval results must be bounded in number and size.
- The Quiz Agent must have read-only access to the knowledge base.
- Retrieved material must be treated as untrusted data, not executable instructions.
These protections are shared requirements for both the Q&A and Quiz agents, reducing duplicated implementation.

## 4. Quiz Agent ↔ Local LLM Runtime Integration

Both the Q&A Tutor and Quiz Agent may share one local LLM runtime, such as Ollama. The proposed architecture separates the LLM inference service from the agent-specific workflows. Sharing a runtime can reduce memory overhead and avoid unnecessarily loading separate copies of a model.
The Quiz Agent uses two logically independent LLM tasks.

| Question Generator | Open-Ended Grader |
| --- | --- |
| Receives approved RAG evidence | Receives student answer, locked rubric, and evidence |
| Generates questions and proposed keys | Evaluates the answer against rubric criteria |
| Produces a structured quiz draft | Produces structured criterion-level scores |
| Cannot modify student grades | Cannot modify answer keys or rubrics |

Both workflows may call the same local model through separate prompts and structured output schemas.

**Proposed integration**

The Quiz Agent should communicate with the LLM through a shared local inference client or model service.
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

If Ollama is selected, its API supports JSON-schema-constrained responses. However, schema validation verifies data structure, not factual accuracy; generated questions and grades still require application-level checks. Sharing a model does not imply sharing permissions or agent state. Resource scheduling should be coordinated with the Q&A developer to prevent simultaneous workloads from exhausting local RAM or GPU capacity.

## 5. External Data → RAG Ingestion Pipeline

The document ingestion pipeline could be shared by both agents, and the objective is to create a trustworthy local knowledge base from instructor-provided course material and approved official websites.

**Proposed pipeline**

1. Source intake:
   - Approved website → Restricted download gateway → Quarantine storage
   - Lecture PDF / PPTX / Textbook → Quarantine storage
2. Quarantine storage → File validation → Sandboxed text extraction.
3. Extracted content → Source review and approval → Chunking and metadata generation.
4. Chunks → Local embedding model → Staged vector index and integrity check.
5. Verified index → Published approved index → Vector database and source store.

**Design considerations for the ingestion pipeline**

Uploaded and downloaded documents should initially be treated as untrusted. File validation and sandboxed extraction help contain parser vulnerabilities, while content approval reduces the possibility of incorrect or malicious material entering the knowledge base. Embedding generation, storage, and retrieval remain local. Internet access, if supported, is isolated within an optional restricted gateway rather than being available directly to either agent. For official websites, the original URL, document title, publisher, and retrieval timestamp should be retained for future citation verification.

## 6. Quiz Agent Attack-Surface Analysis

The preliminary threat model focuses on network, software, and human attack surfaces. The scope is intentionally limited to threats relevant to the assignment and the proposed Quiz Agent design.
The primary protected assets are approved course materials, embeddings, source metadata, answer keys, grading rubrics, student answers, grades, model configuration, and system credentials.

### 6.1 Network Attack Surface

_Not yet detailed in this preliminary specification._

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

The initial implementation does not aim to build an extensive student-monitoring or anti-cheating system. This would introduce additional complexity beyond the assignment requirements.
Instead, the design focuses on enforcing a small number of predictable policies: restricted access, protected answer keys, bounded resource usage, and validation of grading results.

### 6.4 Overall Security Strategy

The main security principle is that the LLM may generate and evaluate content, but it should not control authorization, database permissions, or authoritative grade commits. Security controls are enforced through trusted backend services, local process restrictions, approved RAG retrieval, and output validation.

Initial security testing should verify that:
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
