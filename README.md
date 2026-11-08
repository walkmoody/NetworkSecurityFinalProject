# NetworkSecurityFinalProject

Q&Q Tutor Agent \
Quiz Agent section \
Threat

## Running the app

Requirements:
- Python 3.10 or newer
- Node.js with npm
- [Ollama](https://ollama.com) with the configured model, such as `qwen3.5:9b`. You can skip Ollama if you run in mock mode.

Quizzes are built from the course knowledge base:

1. Put each course's PDF or TXT files in their own folder in `data/`, for example `data/NetworkSecurity/`. Each folder becomes a course in the app, and its name is the course name.
2. Run `./run.sh`. Before starting the app, it checks every file in `data/` against `vector_db/hashes.json`, the SHA-256 hashes of the approved documents. The hashes are kept apart from `data/`, so whoever can change the documents can't also rewrite their approval in the same place. If any files are new (`[UNAPPROVED]`), changed (`[MODIFIED]`) or deleted (`[MISSING]`), it lists them and asks whether to approve them:
   - **`y`:** updates `vector_db/hashes.json` to match the current files, then rebuilds the knowledge base.
   - **`n` or Enter:** changes nothing and starts the app with the previously approved knowledge base.
   - **Without a terminal** (for example, when run from another script): treated as `n`.

   A `[MODIFIED]` file differs from the version you approved. Approve it only if you made the change yourself, because this is how the integrity check catches a tampered document. See [rag_pipeline/README.md](rag_pipeline/README.md) for details.

`./run.sh` rebuilds the knowledge base (`python -m rag_pipeline.build_index`) only when needed: when you approve changes, or when a course folder has nothing indexed yet. `backend/.venv` is created the first time you run `./run.sh`.

From the repository root:

```bash
./run.sh                          # Use the local Ollama model
./run.sh --mock                   # Use the mock model; no Ollama needed
```

Then open http://localhost:5173. Press Ctrl+C to stop both the backend and the frontend.

The first time it runs, the script:
- Creates the Python venv in `backend/.venv` and installs the backend's dependencies.
- Installs the frontend's npm packages.
- Copies `llm/ollama.example.json` to `llm/ollama.json` if that file doesn't exist yet.

To check your Ollama setup, see [llm/README.md](llm/README.md).

### Running each part manually

Run these from the repository root, each in its own terminal:

```bash
# Backend API on 127.0.0.1:8000 (add QUIZ_LLM=mock before the command to skip Ollama)
backend/.venv/bin/uvicorn backend.app:app --host 127.0.0.1 --port 8000

# Frontend on localhost:5173 (forwards /api requests to the backend)
cd frontend && npm run dev
```

For more detail, see [backend/README.md](backend/README.md) and [quizAgent/README.md](quizAgent/README.md).
