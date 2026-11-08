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
- Private documents remain local; optional public-web lookup is disabled.
- The current web login is not server-side authorization. Do not expose the
  backend beyond loopback or deploy it for real users without authenticated
  course permissions.
- In `QUIZ_LLM=mock` mode, the Quiz uses a mock; Tutor returns 503.


## Internet-assisted citations (optional / explicit opt-in)

The Q&A Tutor screen has an **Internet-assisted citations** checkbox, initially
off. When enabled, an HTTPS request retrieves an excerpt from one fixed Wikipedia
article matching a recognized public security topic, for example AES -> Advanced
Encryption Standard. Public evidence is supplied to the local Ollama model
alongside any approved course passages. Citations identify public sources with
clickable URLs; lecture citations continue to show document and page.

**Privacy boundary:** only a hard-coded public encyclopedia article title and
fixed MediaWiki query parameters leave the computer. The full student question,
lecture PDFs, extracted chunks, embedding vectors, model prompts, and course IDs
are NEVER sent to Wikipedia. The remote provider will still see the requested
article topic and your IP address. No external API keys are used. Redirects
are not followed, requests have an 8-second timeout and a 50 KB response cap,
and unsupported topics or provider failures report an error rather than
silently sending the prompt to a different service.

To test the network scenario, record actual traffic with the checkbox off
(loopback 5173 / 8000 / 11434) and then on (also Wikipedia HTTPS). TLS prevents
reading HTTP request contents directly from an ordinary passive PCAP. Compare
with the fixed outbound URL logic and offline tests in tests/test_web_lookup.py.
Do not claim captures have been collected unless they actually have.

Tests from the repository root:

\`\`\`powershell
python -m unittest discover -s tests -p test_tutor_agent.py -v
python -m unittest discover -s tests -p test_web_lookup.py -v
\`\`\`
