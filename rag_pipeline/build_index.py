from rag_pipeline.integrity import verify_documents
from rag_pipeline.embeddings import build_vector_database


def main(): # verify documents and build the local knowledge base
    
    print("=" * 50)
    print("NETWORK SECURITY KNOWLEDGE BASE BUILDER")
    print("=" * 50)

    print("\nStep 1: Verifying document integrity...")

    if not verify_documents():
        print("\nERROR: Document verification failed.")
        print("Database build cancelled.")
        return

    print("\nStep 2: Building vector database...")

    collection = build_vector_database()

    print("\n" + "=" * 50)
    print("KNOWLEDGE BASE BUILD COMPLETE")
    print("=" * 50)

    print(f"Total document chunks: {collection.count()}")
    print("Database location: vector_db/")
    print("Your RAG pipeline is ready!")


if __name__ == "__main__":
    main()
