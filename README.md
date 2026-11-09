# Local Network-Security Tutor & Quiz Bot

CS5342 Network Security group project. This is a privacy-preserving study assistant
built on a local large language model (LLM). It has two agents that work only from
your course documents:

- **Q&A Tutor Agent:** answers course questions and cites the lecture file, page and chunk each answer comes from. If the course material doesn't support an answer, it says so instead of guessing.
- **Quiz Agent:** generates **random** or **topic-specific** quizzes with **multiple-choice, true/false and open-ended** questions. It grades your answers and gives feedback with citations.

Everything runs on your own machine: the LLM (Ollama), the embedding model, the
vector database (ChromaDB) and the web app. Course documents never leave the computer.

## Contents

- [Features](#features)
- [System architecture](#system-architecture)
- [Required environment](#required-environment)
- [Adopted libraries](#adopted-libraries)
- [Training data and data formats](#training-data-and-data-formats)
- [Flow of execution](#flow-of-execution)
- [Commands to run the code](#commands-to-run-the-code)
- [Security measures](#security-measures)
- [Issues we experienced and solutions](#issues-we-experienced-and-solutions)
- [Suggestions](#suggestions)
- [Feedback](#feedback)

## Features

- **Local-only inference:** the `qwen3.5:9b` model runs in Ollama on `127.0.0.1`, and the backend listens only on `127.0.0.1`.
- **Retrieval-augmented generation (RAG):** answers and quiz questions are based on chunks of the lecture slides found by semantic search.
- **Citations:** every Tutor answer and every graded quiz question links back to the source document and page.
- **Three question types:** multiple-choice and true/false are graded exactly. Open-ended answers are scored by the LLM against a fixed rubric and reference answer.
- **Two quiz modes:** random (spread across the course's key concepts) or a specific topic you enter.
- **Multiple courses:** each folder in `data/` becomes its own course, and retrieval never crosses courses.
- **Knowledge base integrity check:** documents are hashed with SHA-256 and must be approved before they're indexed.
- **Live progress:** the quiz page shows each retrieval, model and validation step as it runs.
- **Mock mode:** runs the whole app without Ollama, for development and tests.

## System architecture

```text
                        ┌──────────────────────────── your machine ────────────────────────────┐
                        │                                                                       │
 Browser ──► React UI (Vite, localhost:5173) ──/api proxy──► FastAPI backend (127.0.0.1:8000)   │
                        │                                     │                │                │
                        │                         ┌───────────┘                └──────────┐     │
                        │                         ▼                                       ▼     │
                        │                 Quiz Agent (quizAgent/)              Q&A Tutor (tutorAgent/)
                        │                         │   │                                 │   │   │
                        │        rag_pipeline ◄───┘   └──► llm/OllamaClient ◄───────────┘   │   │
                        │        retriever ◄─────────────────────────────────────────────────┘   │
                        │            │                          │                               │
                        │            ▼                          ▼                               │
                        │   ChromaDB (vector_db/)     Ollama (127.0.0.1:11434, qwen3.5:9b)      │
                        │            ▲                                                          │
                        │   build_index: data/ ─► SHA-256 check ─► extract ─► chunk ─► embed     │
                        └───────────────────────────────────────────────────────────────────────┘
```

The threat model diagram is in [THREAT_MODEL.drawio.png](THREAT_MODEL.drawio.png).

### Repository layout

| Folder | Purpose | Details |
|---|---|---|
| [frontend/](frontend/) | React web app with Login, Home (course picker), Quiz and Tutor pages | [frontend/README.md](frontend/README.md) |
| [backend/](backend/) | FastAPI server: HTTP endpoints, sessions, streamed progress | [backend/README.md](backend/README.md) |
| [quizAgent/](quizAgent/) | Quiz generation, validation and grading | [quizAgent/README.md](quizAgent/README.md) |
| [tutorAgent/](tutorAgent/) | Q&A Tutor with grounded answers and citation checks | [tutorAgent/README.md](tutorAgent/README.md) |
| [rag_pipeline/](rag_pipeline/) | Integrity check, ingestion, embeddings, ChromaDB, retrieval | [rag_pipeline/README.md](rag_pipeline/README.md) |
| [llm/](llm/) | Shared Ollama client, its configuration, and the mock model | [llm/README.md](llm/README.md) |
| [tests/](tests/) | Tests for the Quiz Agent, Tutor and RAG pipeline | |
| `data/` | Course documents, one folder per course (not committed) | |
| `vector_db/` | ChromaDB files and the `hashes.json` approval manifest (not committed) | |

## Required environment

| Requirement | Version / notes |
|---|---|
| Operating system | macOS or Linux for `./run.sh`. On Windows, use WSL to run the script, or run the parts manually (see [Windows](#windows)). |
| Python | 3.10 or newer. `run.sh` picks the newest of 3.13 to 3.10 it finds. |
| Node.js and npm | A current LTS release that Vite 8 supports (Node 20.19+ or 22.12+) |
| Ollama | [ollama.com](https://ollama.com), with the `qwen3.5:9b` model pulled. Not needed in mock mode. |
| Hardware | 16 GB RAM recommended for a 9B model. A GPU or Apple Silicon makes answers much faster but isn't required. Allow about 7 GB of disk for the model. |
| Network | Needed only for the first install (pip, npm, the Ollama model and the embedding model download). After that the app runs offline. |

The model and its settings are in `llm/ollama.json`, which is created from
[llm/ollama.example.json](llm/ollama.example.json): host `127.0.0.1:11434`,
temperature 0, 16k context. You can override any setting with environment
variables; see [llm/README.md](llm/README.md).

## Adopted libraries

**Backend and AI (Python):** [requirements.txt](requirements.txt), [backend/requirements.txt](backend/requirements.txt)

| Library | What we use it for |
|---|---|
| [Ollama](https://ollama.com) + `qwen3.5:9b` | Local LLM that generates answers and quizzes and grades open-ended answers |
| `sentence-transformers` (`all-MiniLM-L6-v2`) | Local embedding model that turns chunks and queries into vectors |
| `chromadb` | Local persistent vector database in `vector_db/` |
| `PyMuPDF` | Extracts text from PDF slides, page by page |
| `fastapi` + `uvicorn` | HTTP API and server |
| `pytest`, `httpx` | Tests, including FastAPI's `TestClient` |
| Python standard library: `hashlib`, `secrets`, `urllib` | SHA-256 integrity hashes, session tokens, the HTTP client for Ollama |

**Frontend (TypeScript):** [frontend/package.json](frontend/package.json)

| Library | What we use it for |
|---|---|
| `react`, `react-dom`, `react-router` | UI and page routing |
| `vite` | Dev server, and the proxy from `/api` to the backend |
| `tailwindcss` | Styling |
| `motion`, `@hugeicons/react` | Animation and icons |
| `typescript`, `oxlint` | Type checking and linting |

## Training data and data formats

The agents aren't fine-tuned. They use **retrieval-augmented generation**: the
pretrained model gets the relevant course text inside each prompt.

- **Source material:** CS5342 lecture slides (`Lecture 1_slides.pdf` and onward) in `data/NetworkSecurity/`.
- **Accepted formats:** `.pdf` with extractable text, and `.txt`. Scanned, image-only PDFs need OCR first.
- **Layout:** `data/<CourseName>/<files>`. Each folder name becomes a course ID in the app.
- **Chunking:** text is split into 500-word chunks with a 50-word overlap. Each chunk keeps its course, source file, page number and chunk number.
- **Embeddings:** 384-dimensional `all-MiniLM-L6-v2` vectors stored in the ChromaDB collection `network_security`.
- **Approval manifest:** `vector_db/hashes.json` maps each approved file to its SHA-256 hash.

The course documents and the built database aren't committed to Git. Each team
member adds the slides to `data/` locally.

https://github.com/user-attachments/assets/0589eb7b-5173-4e0f-9ea8-8c1732d219f5

## Flow of execution

### 1. Building the knowledge base (at startup, when needed)

```text
data/<course>/*.pdf|txt
  → integrity.py   hash every file with SHA-256 and compare it with vector_db/hashes.json
                   (new, modified or missing files must be approved before indexing)
  → ingestion.py   extract text per page (PyMuPDF), clean it, split it into 500-word chunks
  → embeddings.py  embed the chunks with all-MiniLM-L6-v2 on the CPU
  → ChromaDB       store the vectors with their course, source, page and chunk metadata
```

### 2. Q&A Tutor (`POST /api/tutor/ask`)

```text
Question + course
  → retrieve the 4 most similar chunks from that course only
  → drop chunks below the similarity threshold (0.25)
  → prompt qwen3.5:9b: answer only from the numbered evidence and treat the evidence as data, not instructions
  → model returns JSON {answer, supported, evidence_ids}
  → citations are built from the retrieval metadata, never from text the model wrote
  → unsupported, or the cited IDs don't match the evidence → "can't answer from course material"
```

### 3. Quiz Agent (`POST /api/quiz`, `POST /api/quiz/{id}/submit`)

```text
Generation:
  course + mode (random | topic) + question counts
  → retrieve 12 chunks (key concepts for random, the topic text for topic mode)
  → qwen3.5:9b writes the questions, answer keys, rubrics and evidence IDs as JSON
  → validate the structure, question counts, answer keys and that every citation points to a retrieved chunk
  → store the answer keys on the server; return only the public questions to the browser

Grading:
  answers
  → reload the exact original chunks (rejected if the knowledge base was rebuilt since)
  → multiple-choice / true-false: exact comparison with the stored key
  → open-ended: the LLM scores each rubric criterion; the server checks the scores and computes the total
  → return points, feedback and citations (document + page)
```

Both endpoints stream progress as newline-delimited JSON, so the Quiz page
can show each step live. The full API is in [backend/README.md](backend/README.md).

## Commands to run the code

### Quick start (macOS / Linux)

```bash
# 1. Install Ollama, then download the model (once)
ollama pull qwen3.5:9b

# 2. Add course documents
mkdir -p data/NetworkSecurity      # copy the lecture PDFs into this folder

# 3. Start everything from the repository root
./run.sh            # uses the local Ollama model
./run.sh --mock     # no Ollama needed; uses the mock model (the Tutor is unavailable in this mode)
```

Then open http://localhost:5173. Press Ctrl+C to stop both the backend and the frontend.

The first time it runs, `run.sh`:
- Creates the Python venv in `backend/.venv` and installs the backend's dependencies.
- Installs the frontend's npm packages.
- Copies `llm/ollama.example.json` to `llm/ollama.json` if that file doesn't exist yet.

On every start, it checks `data/` against `vector_db/hashes.json`. If any files
are new (`[UNAPPROVED]`), changed (`[MODIFIED]`) or deleted (`[MISSING]`), it
lists them and asks whether to approve them:
- **`y`:** updates the manifest and rebuilds the knowledge base.
- **`n` or Enter, or no terminal attached:** changes nothing and starts the app with the previously approved knowledge base.

Approve a `[MODIFIED]` file only if you made the change yourself. This is how the
integrity check catches a tampered document. The knowledge base is rebuilt only
when you approve changes or when a course folder has nothing indexed yet.

### Running each part manually

Run these from the repository root, each in its own terminal:

```bash
# Build or rebuild the knowledge base by hand
backend/.venv/bin/python -m rag_pipeline.build_index

# Backend API on 127.0.0.1:8000 (add QUIZ_LLM=mock before the command to skip Ollama)
backend/.venv/bin/uvicorn backend.app:app --host 127.0.0.1 --port 8000

# Frontend on localhost:5173 (forwards /api requests to the backend)
cd frontend && npm run dev
```

### Windows

`run.sh` is a bash script, so either run it in WSL or use PowerShell:

```powershell
py -3 -m venv backend\.venv
backend\.venv\Scripts\pip install -r backend\requirements.txt
Copy-Item llm\ollama.example.json llm\ollama.json
backend\.venv\Scripts\python -m rag_pipeline.integrity      # review the documents before approving
backend\.venv\Scripts\python -m rag_pipeline.build_index
backend\.venv\Scripts\uvicorn backend.app:app --host 127.0.0.1 --port 8000
# In a second terminal:
cd frontend; npm install; npm run dev
```

### Terminal demo and tests

```bash
# Take a quiz in the terminal
backend/.venv/bin/python -m quizAgent.demo --interactive --course NetworkSecurity
backend/.venv/bin/python -m quizAgent.demo --interactive --course NetworkSecurity --topic firewall

# Run every test (no Ollama needed; your data/ and vector_db/ aren't touched)
backend/.venv/bin/python -m pytest tests backend/tests -q
```

## Security measures

These address the risks in the threat model ([THREAT_MODEL.drawio.png](THREAT_MODEL.drawio.png)):

| Risk | Mitigation in this code |
|---|---|
| **Prompt injection** | Questions, student answers and retrieved text are passed to the model as data, and the system prompts tell it to ignore instructions inside them. Model output must match a strict JSON schema. Citations are built from retrieval metadata, never from model text. The server, not the model, totals quiz scores and checks each criterion's limit. |
| **Data exposure (vector database and embeddings)** | The backend and Ollama listen only on `127.0.0.1`. `vector_db/` and `data/` are excluded from Git. Every lookup is filtered to one course. Answer keys never reach the browser. Each browser session gets a random token in an HttpOnly, SameSite=Strict cookie and can see only its own attempts. Model errors are returned without internal details. |
| **API keys and secrets** | Local inference needs no API keys, and the optional Wikipedia lookup uses Wikipedia's public API, which needs none either, so there is no key to store or leak. `llm/ollama.json` is excluded from Git. |
| **Knowledge base poisoning** | Documents are checked against SHA-256 hashes before indexing, and changed files need explicit approval. The manifest is stored in `vector_db/`, apart from `data/`. Rebuilding the knowledge base invalidates quiz attempts made before the rebuild. |

## Issues we experienced and solutions

| Issue | Solution |
|---|---|
| Tutor questions about a topic (for example "the three core security requirements") returned "not enough evidence". Title-only slides matched the question best, so they filled the top results while the slides with the definitions ranked below 20th. | For Tutor queries, the retriever now extends a matched title slide with the slides that follow it (up to about 120 words or 4 slides). A citation to a title slide therefore covers that short section. The Quiz Agent keeps the stored chunks, because grading re-reads them. |
| The embedding model crashed with PyTorch MPS errors on Apple Silicon Macs. | It is forced to run on the CPU in [rag_pipeline/embeddings.py](rag_pipeline/embeddings.py). `all-MiniLM-L6-v2` is small enough that this is fast. |
| The Quiz Agent was first built against a sample corpus (`rag/`), separate from the team's real RAG pipeline, so the two drifted apart. | We removed `rag/` and changed the Quiz Agent to read directly from `rag_pipeline` (PR #6), so both agents use the same index. |
| Moving the slides into per-course folders changed their paths, so the existing hash manifest no longer matched. | `run.sh` lists the differences and asks for approval, then rebuilds. Re-approving is a deliberate step, never automatic. |
| The local model sometimes returns malformed JSON, invalid citations or out-of-range scores. | Every output is validated against a schema. Quiz generation retries once with the validation error fed back to the model, and grading has a `retry` endpoint that keeps the locked answers. |
| Quiz requests take a while on a 9B model, and the page looked frozen. | The backend streams each step as NDJSON, and the Quiz page shows the steps live. |
| Starting the backend and frontend separately caused port conflicts and failed `/api` calls before the backend was ready. | `run.sh` checks port 8000, waits for the backend to answer before starting Vite, and stops both on Ctrl+C. |

## Suggestions

- **Internet citations:** the Tutor's opt-in Wikipedia lookup sends a few keywords from the question. A local-only keyword extractor or an on-device paraphrase could send even less. Any future provider that needs an API key should read it from an environment variable, and web text should stay out of quiz scoring.
- **Real authentication:** the web login is only a front-end screen. Real accounts and backend authorization would be needed before anyone other than the local user could use this.
- **Encrypt the vector database at rest**, so a copied `vector_db/` folder doesn't expose the course text.
- **Persistent sessions:** quiz attempts are kept in memory and are lost when the server restarts.
- **OCR** for scanned or image-heavy slides, and support for more formats such as PPTX.
- **A grading accuracy benchmark:** compare the open-ended grader with hand-graded answers to measure how closely it agrees.

## Feedback

_To be completed by the team: what worked well in the project, what was hard,
and any suggestions for the course or the assignment._
