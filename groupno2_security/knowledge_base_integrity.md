# Knowledge base integrity

The current course index was rebuilt from the 26 PDFs supplied in the `NetworkSecurity` folder. Each ingested copy was checked byte-for-byte by SHA-256 against its supplied source. The runtime approval manifest, `vector_db/hashes.json`, records a SHA-256 digest for each of the 26 lecture files. After rebuilding, `python -m rag_pipeline.integrity` verified all 26 and reported “All documents passed integrity verification.”

The supplied versions establish the approval baseline for this run. A matching digest detects changes after approval. It does not prove a source was trustworthy before approval.

The rebuilt index contains 253 chunks. The new copy of Lecture 6 replaced the prior version, which was backed up separately.
