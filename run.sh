#!/usr/bin/env bash
# Start the backend API and the frontend together from the repository root.
# Usage: ./run.sh          (uses Ollama, configured in llm/ollama.json)
#        ./run.sh --mock   (no Ollama; mock model)
set -euo pipefail
cd "$(dirname "$0")"

if [[ "${1:-}" == "--mock" ]]; then
  export QUIZ_LLM=mock
elif [[ -n "${1:-}" ]]; then
  echo "Usage: ./run.sh [--mock]" >&2
  exit 1
fi

# Find Python 3.10+ (the agents use 3.10 syntax).
PYTHON=""
for candidate in python3.13 python3.12 python3.11 python3.10 python3; do
  if command -v "$candidate" >/dev/null 2>&1 \
    && "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null; then
    PYTHON="$candidate"
    break
  fi
done
if [[ -z "$PYTHON" ]]; then
  echo "Python 3.10 or newer is required." >&2
  exit 1
fi

if [[ ! -x backend/.venv/bin/python ]]; then
  echo "Creating backend/.venv with $PYTHON..."
  "$PYTHON" -m venv backend/.venv
fi
if [[ ! -f backend/.venv/.installed || backend/requirements.txt -nt backend/.venv/.installed ]]; then
  backend/.venv/bin/pip install -q -r backend/requirements.txt
  touch backend/.venv/.installed
fi

if [[ ! -d frontend/node_modules ]]; then
  echo "Installing frontend dependencies..."
  (cd frontend && npm install)
fi

if [[ "${QUIZ_LLM:-}" != "mock" && ! -f llm/ollama.json ]]; then
  echo "Creating llm/ollama.json from the example; edit it if Ollama is not on 127.0.0.1:11434."
  cp llm/ollama.example.json llm/ollama.json
fi

# Course documents must be approved (their SHA-256 hashes recorded in the manifest) before
# they are indexed. If files are new, modified, or missing since the last approval, list them
# and ask. Declining keeps the previously approved knowledge base and starts the app anyway.
MANIFEST=vector_db/hashes.json  # matches MANIFEST_FILE in rag_pipeline/integrity.py
if true; then  # quizzes always use the knowledge base
  approved=1
  if [[ -f "$MANIFEST" ]]; then
    changes=$(backend/.venv/bin/python -m rag_pipeline.integrity | grep -E '^\[(UNAPPROVED|MODIFIED|MISSING)\]' || true)
  else
    changes=$(backend/.venv/bin/python -c "from rag_pipeline.integrity import DATA_DIR, get_documents
for p in get_documents(): print('[UNAPPROVED]', p.relative_to(DATA_DIR).as_posix())")
  fi

  if [[ -n "$changes" ]]; then
    echo
    echo "Course documents changed since they were last approved:"
    echo "$changes"
    if grep -q '^\[MODIFIED\]' <<<"$changes"; then
      echo "WARNING: [MODIFIED] files differ from the version you approved. Approve only if you changed them yourself."
    fi
    answer=n
    if [[ -t 0 ]]; then
      read -r -p "Approve these documents and rebuild the knowledge base? [y/N] " answer || answer=n
    fi
    if [[ "$answer" =~ ^[Yy]$ ]]; then
      rm -f "$MANIFEST"
      backend/.venv/bin/python -c "from rag_pipeline.integrity import create_manifest; create_manifest()" || approved=0
    else
      approved=0
      echo "Not approved; starting with the previously approved knowledge base."
    fi
  fi

  # Rebuild only when a course folder has no chunks indexed or the approvals changed since the last build.
  if (( ! approved )) || [[ ! -f "$MANIFEST" ]]; then
    :
  elif [[ ! -f vector_db/chroma.sqlite3 || "$MANIFEST" -nt vector_db/chroma.sqlite3 ]] \
    || ! backend/.venv/bin/python - <<'PY'
import sys
from rag_pipeline.embeddings import get_collection
from rag_pipeline.integrity import DATA_DIR, get_documents

collection = get_collection()
courses = {p.relative_to(DATA_DIR).parts[0] for p in get_documents() if len(p.relative_to(DATA_DIR).parts) > 1}
missing = [c for c in sorted(courses) if not collection.get(where={"course": c}, limit=1)["ids"]]
if missing:
    print("Not indexed yet:", ", ".join(missing))
sys.exit(1 if missing else 0)
PY
  then
    echo "Building the knowledge base..."
    backend/.venv/bin/python -m rag_pipeline.build_index
  fi
fi

if curl -s -o /dev/null --max-time 2 http://127.0.0.1:8000/; then
  echo "Port 8000 is already in use; stop the other backend first." >&2
  exit 1
fi

FRONTEND_PID=""
# Stop both servers when either exits or on Ctrl+C.
cleanup() {
  trap - EXIT INT TERM
  if [[ -n "$FRONTEND_PID" ]]; then pkill -P "$FRONTEND_PID" 2>/dev/null || true; fi
  kill "$BACKEND_PID" $FRONTEND_PID 2>/dev/null || true
  wait 2>/dev/null || true
}

backend/.venv/bin/uvicorn backend.app:app --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!
trap cleanup EXIT INT TERM

# Hold the frontend until the backend answers HTTP requests (any status counts as up).
echo "Waiting for the backend to start..."
for (( waited = 0; ; waited++ )); do
  if curl -s -o /dev/null --max-time 2 http://127.0.0.1:8000/api/courses; then
    break
  fi
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "The backend failed to start; see the errors above." >&2
    exit 1
  fi
  if (( waited >= 120 )); then
    echo "The backend did not start within 120 seconds." >&2
    exit 1
  fi
  sleep 1
done

(cd frontend && exec npm run dev) &
FRONTEND_PID=$!

echo "Backend: http://127.0.0.1:8000  (model: ${QUIZ_LLM:-ollama})"
echo "Frontend: open the Local URL Vite prints below  (Ctrl+C stops both)"
while kill -0 "$BACKEND_PID" 2>/dev/null && kill -0 "$FRONTEND_PID" 2>/dev/null; do
  sleep 1
done
