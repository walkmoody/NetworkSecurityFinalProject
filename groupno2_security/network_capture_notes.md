# Network capture notes

## Scenario 1 — Local Tutor inference

`scenario1_local_only.pcapng` contains 485 app-related loopback packets. The browser, Tutor API, and Ollama communicated through loopback on ports 5173, 8000, and 11434. The original also contained unrelated Wi-Fi traffic, which was excluded from the submitted file. The captured Tutor and Ollama requests stayed on loopback. This filtered file cannot establish the contents of other encrypted Wi-Fi traffic.

**Found and fixed.** The earlier warm-cache run showed the backend contacting Hugging Face during retrieval. The updated code caches the embedding model once per process and loads it from local files when the cache is present. It can still download the model on an uncached machine.

## Scenario 2 — Wikipedia lookup

`scenario2_wikipedia.pcapng` records the updated Tutor with Internet assistance enabled for “What are the weaknesses of DES?” and “What is a nonce?” Both answers returned HTTP 200 and cited Wikipedia.

| Decrypted frame | Prompt | Outbound GET parameter |
| --- | --- | --- |
| 39 | DES weaknesses | `titles=Data Encryption Standard` |
| 69 | DES weaknesses | `titles=Data Encryption Standard` |
| 172 | Nonce | `gsrsearch=nonce` |
| 205 | Nonce | `titles=Cryptographic nonce` |

The only external HTTPS destination observed for the dedicated test process was `en.wikipedia.org` at `208.80.153.224:443`. The capture also shows the DNS query to the local resolver. All four requests were GETs to `/w/api.php` with no request body. They contained fixed API options and either the public article title or the keyword `nonce`. None contained the full prompt, a course document, or retrieved course text. Ollama traffic remained on loopback. No Hugging Face traffic appeared during this run, which used cached embeddings with Hub offline mode enabled.

The process-scoped capture recorded 261 packets on November 8, 2026, from 9:33:18 to 9:35:27 p.m. CST, with zero kernel drops. To inspect the requests in Wireshark, load `wikipedia_tls_keys.log` under **Preferences → Protocols → TLS → (Pre)-Master-Secret log filename** and use the display filter `http.request`. The key log contains only the four captured Wikipedia TLS sessions. [Wireshark TLS decryption documentation](https://wiki.wireshark.org/TLS/#tls-decryption)
