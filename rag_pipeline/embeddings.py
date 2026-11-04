
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

from rag_pipeline.ingestion import ingest_documents

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "vector_db"

COLLECTION_NAME = "network_security"

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

def load_embedding_model():
    """
    Load the embedding model using the CPU.
    This avoids PyTorch MPS compatibility issues on macOS.
    """

    model = SentenceTransformer(
        MODEL_NAME,
        device="cpu"
    )

    return model


def get_collection():
    """
    Connect to the persistent local ChromaDB database.
    """

    DB_PATH.mkdir(parents=True, exist_ok=True)

    client = chromadb.PersistentClient(
        path=str(DB_PATH)
    )

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"}
    )

    return collection


def generate_embeddings(texts, model): # convert a list of texts into embeddings using the specified model
    
    embeddings = model.encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=True
    )

    return embeddings.tolist()


def build_vector_database():
 
    print("Step 1: Loading approved documents...")

    chunks = ingest_documents()

    if not chunks:
        raise ValueError(
            "No document chunks found. Check your data folder."
        )

    print(f"Loaded {len(chunks)} chunks.")

    print("Step 2: Loading embedding model...")

    model = load_embedding_model()

    print("Step 3: Generating embeddings...")

    texts = [chunk["text"] for chunk in chunks]

    vectors = generate_embeddings(texts, model)

    
    print("Step 4: Rebuilding ChromaDB collection...")

    # only rebuild after integrity verification, ingestion, and embedding generation have succeeded
    DB_PATH.mkdir(parents=True, exist_ok=True)

    client = chromadb.PersistentClient(
        path=str(DB_PATH)
    )

    # delete the previous collection to prevent stale chunks
    try:
        client.delete_collection(name=COLLECTION_NAME)
        print("Previous collection removed.")
    except chromadb.errors.NotFoundError:
        print("No previous collection found.")

    # create a fresh collection
    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"}
    )

    ids = [chunk["id"] for chunk in chunks]

    metadata = [
        {
            "source": chunk["source"],
            "page": chunk["page"],
            "chunk": chunk["chunk"]
        }
        for chunk in chunks
    ]

    collection.upsert(
        ids=ids,
        embeddings=vectors,
        documents=texts,
        metadatas=metadata
    )

    print("Vector database created successfully!")
    print(f"Total vectors stored: {collection.count()}")

    return collection


if __name__ == "__main__":
    build_vector_database()
