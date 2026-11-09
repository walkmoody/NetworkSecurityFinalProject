# Threat model check

`THREAT_MODEL.drawio.png` is the Round 1 diagram. It marks three risks: prompt injection, database exposure, and API key exposure. This check compares each risk with the system as built and points to the evidence in this package.

| Risk (Round 1) | Mitigation as built | Evidence in this package | Holds? |
| --- | --- | --- | --- |
| **Prompt injection.** Malicious input makes the agent leak content or follow injected instructions. | The question and retrieved text go to the model as untrusted data under a separate system instruction. Output must match a strict JSON schema. Citations are built from retrieval IDs, never from model text. A question with no relevant course evidence is declined before the model is called. The Quiz server, not the model, totals scores. | `adversarial_testing_log.md`: 4 attempts (fake system role, poisoned document, Base64 instruction, system-prompt request on the real course). None changed the answer or disclosed the system prompt. In `scenario1_local_only.pcapng`, the system-prompt request (frame 468) was declined at frame 471 with no Ollama traffic. | Yes |
| **Database exposure.** Unauthorized access to the vector database or cached embeddings. | The backend listens on 127.0.0.1:8000 and Ollama on 127.0.0.1:11434. `vector_db/` and `data/` are excluded from Git. Retrieval is filtered to one course. Quiz answer keys stay on the server. | `scenario1_local_only.pcapng`: all Tutor and model traffic is loopback (127.0.0.1 or ::1). `network_capture_notes.md` covers the Hugging Face connection found in an earlier capture and its fix. | Yes, on one machine. Not designed for exposure beyond localhost: there is no server-side login, and the vector database is not encrypted at rest. |
| **API key exposure.** Keys for internet lookups are stored, sent, or leaked. | The only internet service is Wikipedia's public API, which needs no key, so there is no key to store or leak. The local Ollama settings file is excluded from Git. | `scenario2_wikipedia.pcapng` decrypted with `wikipedia_tls_keys.log`: the four requests to `en.wikipedia.org` (frames 39, 69, 172, 205) carry only `Host`, `Accept`, `User-Agent`, `Accept-Encoding` and `Connection` headers. There is no `Authorization`, `Cookie` or key parameter. | Yes. The risk is removed rather than mitigated. |

## Where the diagram differs from the built system

- **API key storage.** The diagram has an API key store, but the built system has none, because Wikipedia needs no key. A future provider that requires a key should read it from an environment variable, never from a file in the repository.
- **Local model.** The diagram doesn't show Ollama. It runs on 127.0.0.1:11434, and the captures show model traffic only on loopback.
- **Knowledge base poisoning.** This risk was added after Round 1. Course documents are checked against SHA-256 hashes before indexing; see `knowledge_base_integrity.md`.
- **Internet lookup.** The arrow to the external web is now an opt-in Wikipedia lookup. It sends a curated article title or up to 6 keywords from the question, never course text; see `network_capture_notes.md`.
