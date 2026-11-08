# Q&A Tutor Agent — team backend integration

This agent is available through the **existing team FastAPI backend** at
`POST /api/tutor/ask`, not through a second server. It shares the team's
Ollama runtime and course-scoped ChromaDB retrieval, with verified citation IDs,
controlled error handling, and unsupported-answer refusal.

## Local Windows setup

From the repository root, activate your virtual environment, then:

```powershell
python -m pip install -r backend/requirements.txt
```

Configure `llm/ollama.json` using `llm/ollama.example.json` and make sure
the configured Ollama model is installed. Keep local configuration untracked.

**Course layout:** the updated index groups documents by folders, so place your
approved lectures under `data/CS5342/` (or another course identifier), not
directly under `data/`. Because this changes document paths, inspect the
approved files, update the trusted `vector_db/hashes.json` manifest intentionally,
and rebuild with `python -m rag_pipeline.build_index`. Do not delete a failed
manifest without reviewing the changed source files.

Start the shared backend:

```powershell
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

In another terminal:

```powershell
cd frontend
npm install
npm run dev
```

Use the Home page to select an indexed course, then open its Tutor. The
frontend uses the team's existing `/api` proxy and course ID in the URL.

Run the offline unit tests with:

```powershell
python -m unittest discover -s tests -p test_tutor_agent.py -v
```

## Scope and security limitations

- The model is grounded in retrieved text; citation ID matching does not guarantee
  every claim is entailed by the cited page.
- Private documents remain local; the optional Wikipedia lookup sends only keywords from the question.
- The current web login is not server-side authorization. Do not expose the
  backend beyond loopback or deploy it for real users without authenticated
  course permissions.
- In `QUIZ_LLM=mock` mode, the Quiz uses a mock; Tutor returns 503.


## Internet-assisted citations (optional / explicit opt-in)

The Q&A Tutor screen has an **Internet-assisted citations** checkbox, initially
off. When enabled, the Wikipedia API returns one article's plain text. The intro
plus the passages closest to the question (ranked locally with the embedding
model, up to 2,800 characters) go to the local Ollama model alongside the
approved course passages, labeled `source_type: "web"` so the model knows to cite
them. Citations identify public sources with clickable URLs; lecture citations
continue to show document and page.

The article is chosen in one of two ways:

1. **Curated topics.** Known acronyms and a few course topics map to a fixed article,
   for example DES -> Data Encryption Standard. A plain search finds the wrong
   article for many acronyms, so these skip the search.
2. **Search.** Any other question is searched using up to 6 keywords from the
   question, with filler words ("what", "the", "difference") removed and capped at
   80 characters. The top 3 results are scored against the question with the
   local embedding model, and the closest one is used only if it scores at least
   0.55. In testing, on-topic articles scored 0.74-0.87 and off-topic ones at
   most 0.52.

**Privacy boundary:** what leaves the computer is either a curated article title
or those few keywords from the student's question, plus fixed MediaWiki query
parameters. Lecture PDFs, retrieved chunks, embedding vectors, model prompts,
and course IDs are NEVER sent; the lookup receives only the question, never the
retrieved evidence. Wikipedia sees the keywords and your IP address. No API keys
are used, because the Wikipedia API is public. Redirects are not followed, and
requests have an 8-second timeout and a 400 KB response cap. If no article
matches or Wikipedia is unreachable, the Tutor answers from course material
alone.

To test the network scenario, record actual traffic with the checkbox off
(loopback 5173 / 8000 / 11434) and then on (also Wikipedia HTTPS). TLS prevents
reading HTTP request contents directly from an ordinary passive PCAP. Compare
with the outbound request logic and offline tests in tests/test_web_lookup.py.
Do not claim captures have been collected unless they actually have.

Tests from the repository root:

\`\`\`powershell
python -m unittest discover -s tests -p test_tutor_agent.py -v
python -m unittest discover -s tests -p test_web_lookup.py -v
\`\`\`
