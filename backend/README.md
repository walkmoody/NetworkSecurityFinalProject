# Backend

FastAPI server that connects the React frontend to the [Quiz Agent](../quizAgent/README.md).
It listens on 127.0.0.1 only and calls the local Ollama model, so course material
never leaves the machine.

Structure

```text
backend/
├── app.py            # HTTP endpoints, sessions, and error mapping
├── tracing.py        # Reports each rag_pipeline, model, and agent call live while a quiz request runs
└── requirements.txt  # fastapi, uvicorn, plus the root requirements.txt
```

Flow

```text
React (Vite :5173) → /api proxy → FastAPI (:8000) → MockBackend → QuizAgent → rag_pipeline (ChromaDB) + Ollama
```

quizAgent reads the knowledge base that `python -m rag_pipeline.build_index` builds, through `rag_pipeline.retriever` (generation) and `quizAgent/evidence.py` (original evidence for grading and citations). Each top-level folder in `data/` is a course, and nothing is hard-coded. A session can use the courses that were indexed when it started, so restart the server after adding a course.
- **Course isolation:** every lookup is limited to the requested course's chunks.
- **Random mode:** a semantic search for the course's key concepts.
- **Topic mode:** runs a semantic search on the topic name.
- **Citations:** show the document's filename and page.
- **Corpus version:** comes from `vector_db/hashes.json`, so rebuilding the knowledge base invalidates quiz attempts made before the rebuild.

Each browser gets a random session token in an HttpOnly, SameSite=Strict cookie.
Each session has its own attempt store, so one user can't read or submit another
user's attempts. Answer keys stay on the server. Sessions are kept in memory and
are cleared when the server restarts.

Endpoints

| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/api/health` | — | Ollama connection status, or `{"mode": "mock"}` |
| GET | `/api/courses` | — | `{courses: [...]}`: the indexed folders in `data/` |
| POST | `/api/quiz` | `{course_id, mode, topic_id, question_counts}` | Stream ending in the public quiz (no answer keys) |
| POST | `/api/quiz/{attempt_id}/submit` | `{answers: {question_id: answer}}` | Stream ending in points, feedback, and citations |
| POST | `/api/quiz/{attempt_id}/retry` | — | Stream ending in the result of grading again after a model failure |

The three quiz endpoints stream newline-delimited JSON (`application/x-ndjson`) so the page can show each call as it happens:

```text
{"type": "step", "id": 3, "text": "rag_pipeline.retrieve_documents — …"}
{"type": "step", "id": 3, "text": "rag_pipeline.retrieve_documents — … — 12 chunks from 3 documents (0.4s)", "done": true}
{"type": "result", "data": {...}}        or        {"type": "error", "status": 409, "detail": "..."}
```

Errors return `{"detail": ...}` with one of these statuses. In a stream, the same status and detail arrive as the final `error` event:

| Status | Meaning |
|---|---|
| 400 | Invalid request |
| 403 | Course or attempt not available to your session |
| 409 | Already submitted |
| 422 | Retrieval error, such as a knowledge base that hasn't been built |
| 502 | Model unavailable |

Commands

Use Python 3.10+ and run from the repository root. First follow the
[Ollama configuration instructions](../llm/README.md).

```bash
# One-time setup
python3.11 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt

# Start the API with Ollama
backend/.venv/bin/uvicorn backend.app:app --host 127.0.0.1 --port 8000

# Start the API without Ollama (mock model)
QUIZ_LLM=mock backend/.venv/bin/uvicorn backend.app:app --host 127.0.0.1 --port 8000

# In another terminal, start the frontend
cd frontend && npm run dev

# Run the backend tests (no Ollama needed; your data/ and vector_db/ are not touched)
backend/.venv/bin/python -m unittest discover -s backend/tests -t . -v
```

The tests cover:
- `test_app.py`: the HTTP API through rag_pipeline, using a throwaway in-memory Chroma collection (`helpers.knowledge_base`) and the mock model. It checks the streamed steps and result, sessions and cookies, error statuses, and that model errors don't leak details.
- `test_tracing.py`: the progress steps, including a rejected first draft and failed calls.

## Q&A Tutor integration

The same FastAPI process serves `POST /api/tutor/ask` with:
`{"course_id": "CS5342", "question": "What is AES?"}`.
It returns `{"answer": "...", "supported": true, "citations": [...]}`.
The Tutor reuses the same `OllamaClient` as Quiz and restricts semantic
retrieval to the requested indexed course. Quiz endpoints remain unchanged.
Mock mode intentionally returns HTTP 503 for Tutor instead of fabricating answers.
The app is intended for local demos; browser login is not backend authentication.
