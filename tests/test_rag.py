
import sys
from pathlib import Path

import pytest

# allow tests to import files from the project root
sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1])
)

from rag_pipeline.integrity import calculate_hash
from rag_pipeline.ingestion import clean_text, chunk_text
from rag_pipeline.retriever import retrieve_documents



def test_sha256_hash(): # verify that identical file contents produce identical SHA-256 hashes.
    
    import tempfile

    with tempfile.TemporaryDirectory() as temp_dir:
        file_path = Path(temp_dir) / "test.txt"

        file_path.write_text("Network Security")

        first_hash = calculate_hash(file_path)
        second_hash = calculate_hash(file_path)

        assert first_hash == second_hash
        assert len(first_hash) == 64


def test_sha256_detects_modification():

    import tempfile

    with tempfile.TemporaryDirectory() as temp_dir:
        file_path = Path(temp_dir) / "test.txt"

        file_path.write_text("Original content")
        original_hash = calculate_hash(file_path)

        file_path.write_text("Modified content")
        modified_hash = calculate_hash(file_path)

        assert original_hash != modified_hash


def test_clean_text(): 
    text = "Network   Security\n  Requirements"

    result = clean_text(text)

    assert result == "Network Security Requirements"


def test_chunk_text():

    text = "one two three four five six"

    chunks = chunk_text(
        text,
        chunk_size=3,
        overlap=1
    )

    assert chunks == [
        "one two three",
        "three four five",
        "five six"
    ]


def test_invalid_chunk_size(): # verify that invalid chunk settings are rejected
       
    with pytest.raises(ValueError):
        chunk_text(
            "Network Security",
            chunk_size=0
        )


def test_invalid_overlap(): # verify that overlap cannot equal chunk size.

    
    with pytest.raises(ValueError):
        chunk_text(
            "Network Security",
            chunk_size=3,
            overlap=3
        )


def test_empty_query(): # empty retrieval queries are rejected
  

    with pytest.raises(ValueError):
        retrieve_documents("")


def test_retrieval_metadata():

    results = retrieve_documents(
        "What is data integrity?",
        top_k=2
    )

    assert len(results) == 2

    for result in results:
        assert "text" in result
        assert "source" in result
        assert "page" in result
        assert "similarity" in result

        assert isinstance(result["text"], str)
        assert isinstance(result["source"], str)
        assert isinstance(result["page"], int)


def test_retrieval_relevance(): # check that the retrieval system returns relevant results for a known query.
    
    results = retrieve_documents(
        "What is data integrity?",
        top_k=3
    )

    assert any(
        "Data integrity" in result["text"]
        for result in results
    )
