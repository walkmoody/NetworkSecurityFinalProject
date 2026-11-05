# Q&A Tutor Agent (Person 2)

This module integrates the existing `rag_pipeline` and shared `llm.OllamaClient`.
It does not modify the Quiz Agent, ingestion code, or Ollama runtime.

## Responsibilities
- Validate user questions and allow only course CS5342 while the shared index is single-course.
- Retrieve relevant passages from the local ChromaDB collection.
- Generate a grounded answer using local Ollama with a structured JSON schema.
- Build citations from verified retrieval metadata, rejecting fabricated IDs.
- Decline unsupported answers instead of inventing information.
- Keep private course data local; optional public-web lookup is deliberately disabled.

## Setup from repository root
1. Install Python dependencies: `python -m pip install -r requirements.txt`
2. Configure Ollama following `llm/README.md`; install and run the configured model.
3. Add approved, extractable PDF/TXT course files to `data/`.
4. Review the files, then create their trusted manifest:
   `python -c "from rag_pipeline.integrity import create_manifest; create_manifest()"`
5. Build the local index: `python -m rag_pipeline.build_index`
6. Start the Tutor service: `python -m backend.tutor_api`
7. In another terminal, run `cd frontend && npm install && npm run dev`.
8. Open the Tutor page and ask a course question.

The frontend development server proxies `/api/tutor` to the local port 8000.
The API deliberately binds to 127.0.0.1 and has **no real authentication**.
Do not expose it on an untrusted network until team authentication is integrated.

## Offline tests
`python -m unittest tests.test_tutor_agent -v`

## Known limitations
- Only one course can be trusted with the team's current unpartitioned index.
- Similarity is a retrieval heuristic, not proof the model answer is factually correct.
- Citation IDs are verified against retrieved chunks, not entailment-checked sentence by sentence.
- Tests with real Ollama, the complete course index, and the browser are still necessary.
- Optional online source lookup is deferred to a separate privacy/security review.
