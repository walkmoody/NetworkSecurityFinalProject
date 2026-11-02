Shared RAG

Provides evidence to the Quiz and Q&A agents. The current implementation reads
sample JSON data and uses topic filtering or word overlap. Document ingestion,
embeddings, and a vector database are not implemented yet.

Structure

```text
rag/
├── __init__.py            # Retrieval client and evidence type exports
├── contracts.py           # RAG interface, access scope, evidence types, and errors
├── client.py              # InMemoryRAG implementation
└── data/
    └── sample_corpus.json # Nine sample chunks with source metadata
```

Flow

```text
Agent request → Check course access → Select sample evidence → Return text and citations
                                      ├─ Topic quiz: filter topic
                                      ├─ Random quiz: sample across topics
                                      └─ Q&A query: rank by word overlap

Quiz grading → Original chunk IDs + corpus version → Return original evidence
```

The sample corpus is used with both the real Ollama model and the offline mock.
Missing original evidence or a different corpus version causes retrieval to fail.

Commands

Run from the repository root. On Windows, replace `python3` with `py -3`.

```bash
# Test retrieval and quiz workflows without Ollama
python3 -m unittest quizAgent.tests.test_prototype -v

# Run topic retrieval through the offline demo
python3 -m quizAgent.demo --mock --topic firewall

# Run the same workflow with the configured Ollama model
python3 -m quizAgent.demo --interactive --topic firewall
```

See [LLM configuration](../llm/README.md) before using the real model.
