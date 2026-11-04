
import re
from pathlib import Path

import pymupdf

from rag_pipeline.integrity import DATA_DIR, get_documents, verify_documents


def extract_pdf(file_path):
    """
    Extract text from a PDF while preserving page numbers.
    """

    pages = []

    with pymupdf.open(file_path) as document:
        for page_number, page in enumerate(document, start=1):
            text = page.get_text("text")

            if text.strip():
                pages.append({
                    "page": page_number,
                    "text": text
                })

    return pages


def extract_txt(file_path):
    """
    Extract text from a plain text file.
    """

    text = Path(file_path).read_text(encoding="utf-8")

    if not text.strip():
        return []

    return [{
        "page": 1,
        "text": text
    }]


def clean_text(text):
    """
    Normalize whitespace while keeping readable text.
    """

    return re.sub(r"\s+", " ", text).strip()


def chunk_text(text, chunk_size=500, overlap=50):
    """
    Split text into overlapping word-based chunks.
    """

    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")

    if overlap < 0 or overlap >= chunk_size:
        raise ValueError(
            "overlap must be between 0 and chunk_size - 1"
        )

    words = text.split()
    chunks = []

    step = chunk_size - overlap

    for start in range(0, len(words), step):
        chunk = words[start:start + chunk_size]

        if not chunk:
            break

        chunks.append(" ".join(chunk))

        if start + chunk_size >= len(words):
            break

    return chunks


def ingest_documents(chunk_size=500, overlap=50):
    """
    Verify, extract, and chunk all approved documents.
    """

    if not verify_documents():
        raise RuntimeError(
            "Document integrity verification failed. "
            "Ingestion has been stopped."
        )

    documents = get_documents()
    all_chunks = []

    for file_path in documents:
        source = file_path.relative_to(DATA_DIR).as_posix()

        if file_path.suffix.lower() == ".pdf":
            pages = extract_pdf(file_path)

        elif file_path.suffix.lower() == ".txt":
            pages = extract_txt(file_path)

        else:
            continue

        for page in pages:
            cleaned_text = clean_text(page["text"])

            chunks = chunk_text(
                cleaned_text,
                chunk_size=chunk_size,
                overlap=overlap
            )

            for chunk_number, text in enumerate(chunks, start=1):
                chunk_id = (
                    f"{source}:page{page['page']}:"
                    f"chunk{chunk_number}"
                )

                all_chunks.append({
                    "id": chunk_id,
                    "text": text,
                    "source": source,
                    "page": page["page"],
                    "chunk": chunk_number
                })

    return all_chunks


if __name__ == "__main__":
    chunks = ingest_documents()

    print(f"\nTotal chunks created: {len(chunks)}")

    for chunk in chunks[:3]:
        print("\n------------------------")
        print(f"ID: {chunk['id']}")
        print(f"Source: {chunk['source']}")
        print(f"Page: {chunk['page']}")
        print(f"Text: {chunk['text'][:200]}...")
