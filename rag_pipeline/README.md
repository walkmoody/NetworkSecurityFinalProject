# Local RAG Pipeline

## Overview

This module implements the local Retrieval-Augmented Generation (RAG) pipeline for the Network Security Q&A Tutor and Quiz Bot.

The pipeline processes approved course materials, converts their contents into embeddings, and stores them in a local ChromaDB vector database. The Q&A Tutor and Quiz Agent can retrieve relevant course information along with source citations.

## Features

- **Document Integrity:** Uses SHA-256 hashes to verify approved course documents before ingestion.
- **Document Ingestion:** Extracts text from PDF and TXT files.
- **Text Chunking:** Splits documents into smaller chunks with configurable overlap.
- **Local Embeddings:** Uses the `all-MiniLM-L6-v2` Sentence Transformer model on the CPU.
- **Vector Database:** Stores document embeddings and metadata in ChromaDB.
- **Semantic Retrieval:** Retrieves relevant document chunks based on similarity to a user's question.
- **Source Citations:** Returns the document filename, page number, and chunk number for each result.

## Module Structure

| File | Description |
|---|---|
| `integrity.py` | Calculates SHA-256 hashes and verifies documents |
| `ingestion.py` | Extracts, cleans, and chunks document text |
| `embeddings.py` | Generates embeddings and manages ChromaDB |
| `retriever.py` | Performs semantic similarity searches |
| `build_index.py` | Runs the knowledge-base building process |

## Installation

Run the following commands from the repository root.

**1. Create a Python virtual environment (Python 3.12 recommended):**

```bash
python3.12 -m venv .venv
```

**2. Activate the environment:**

On macOS/Linux:

```bash
source .venv/bin/activate
```

On Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

**3. Install dependencies:**

```bash
python -m pip install -r requirements.txt
```

## Adding Course Documents

Place approved PDF or TXT lecture materials in the root-level `data/` folder.

Example:

```text
NetworkSecurityFinalProject/
├── data/
│   ├── Lecture 1_slides.pdf
│   ├── Lecture 2_slides.pdf
│   └── Lecture 3_slides.pdf
├── rag_pipeline/
└── requirements.txt
```

PDFs must contain extractable text. Image-only or scanned PDFs are not currently supported without OCR.

## Document Integrity Verification

Before building the knowledge base, approved documents must have a trusted SHA-256 manifest.

After reviewing and approving the documents in `data/`, create the manifest:

```bash
python -c "from rag_pipeline.integrity import create_manifest; create_manifest()"
```

This generates `hashes.json` in the repository root.

When adding new documents later, review all current documents before intentionally updating the manifest. The current implementation requires removing the old manifest before creating a replacement.

Do not regenerate the manifest merely to bypass a failed integrity check.

## Building the Knowledge Base

After approving the documents, run:

```bash
python -m rag_pipeline.build_index
```

This process:

1. Verifies document integrity.
2. Extracts text from approved documents.
3. Divides text into chunks.
4. Generates embeddings locally.
5. Rebuilds the ChromaDB collection.

The vector database is stored in the root-level `vector_db/` directory.

The embedding model may need to download its weights during the first execution. Once cached, embedding generation runs locally.

## Retrieving Documents

Other modules can retrieve course information by importing:

```python
from rag_pipeline.retriever import retrieve_documents

results = retrieve_documents(
    "What is data integrity?",
    top_k=3
)

for result in results:
    print(result["text"])
    print(result["source"])
    print(result["page"])
    print(result["similarity"])
```

Each retrieved result includes:

| Field | Description |
|---|---|
| `id` | Unique identifier for the document chunk |
| `text` | Retrieved passage |
| `source` | Original document filename |
| `page` | Original page number |
| `chunk` | Chunk number |
| `similarity` | Cosine similarity score |

The Q&A Tutor and Quiz Agent can use the retrieved passages as context when generating responses or questions.

## Running Tests

Run the automated tests from the repository root:

```bash
python -m pytest tests/test_rag.py -v
```

The test suite includes nine tests covering SHA-256 hashing, document chunking, input validation, retrieval metadata, and retrieval relevance.

The retrieval integration tests require a previously built knowledge base containing the expected lecture materials.

## Security and Privacy

- Course documents are processed locally.
- Embeddings are generated locally rather than using an external embedding API.
- SHA-256 verification prevents unapproved or modified documents from being ingested when compared against a trusted manifest.
- Course documents, `hashes.json`, and `vector_db/` are excluded from Git.
- Retrieved document text must be treated as untrusted content by downstream LLM agents.

**Security limitations:** SHA-256 verification depends on the manifest being protected. The current collection rebuild is not atomic, so an interrupted rebuild may leave the database incomplete. Prompt-injection defenses and end-to-end network privacy verification must be tested during integration.

## Known Limitations

- Supports PDF and TXT documents only.
- Does not perform OCR on scanned PDFs.
- Requires manual approval of document hashes.
- Retrieval relevance depends on the query, document content, and `top_k`.
- Larger document collections may require additional indexing time.

## Team Integration

The Q&A Tutor and Quiz Agent should import:

```python
from rag_pipeline.retriever import retrieve_documents
```

Before using retrieval, the knowledge base must be built with:

```bash
python -m rag_pipeline.build_index
```

For questions whose answers span multiple lecture slides, increasing `top_k` may improve coverage.