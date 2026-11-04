
from rag_pipeline.embeddings import (
    load_embedding_model,
    get_collection,
    generate_embeddings
)

def retrieve_documents(query, top_k=3, course=None): # retrieve the most relevant document chunks from the local ChromaDB vector database; course limits results to one data/ folder
   
    if not isinstance(query, str) or not query.strip():
        raise ValueError("Query cannot be empty.")

    if top_k < 1:
        raise ValueError("top_k must be at least 1.")

    collection = get_collection() # connect to the local vector database

    if collection.count() == 0:
        raise ValueError(
            "Vector database is empty. Run embeddings.py first."
        )

    model = load_embedding_model()

    query_vector = generate_embeddings( # convert the user's question into an embedding
        [query],
        model
    )[0]

    # search for the most similar document chunks
    results = collection.query(
        query_embeddings=[query_vector],
        n_results=min(top_k, collection.count()),
        where={"course": course} if course else None,
        include=["documents", "metadatas", "distances"]
    )

    retrieved_documents = []

    for i in range(len(results["ids"][0])):

        metadata = results["metadatas"][0][i]
        distance = results["distances"][0][i]

        retrieved_documents.append({
            "id": results["ids"][0][i],
            "text": results["documents"][0][i],
            "source": metadata["source"],
            "course": metadata.get("course", ""),
            "page": metadata["page"],
            "chunk": metadata["chunk"],
            "similarity": round(1 - distance, 4)
        })

    return retrieved_documents


if __name__ == "__main__":

    question = "What are the three main network security requirements?"

    results = retrieve_documents(question, top_k=3)

    print(f"\nQuestion: {question}")
    print(f"Retrieved {len(results)} documents.\n")

    for index, result in enumerate(results, start=1):

        print(f"--- Result {index} ---")
        print(f"Source: {result['source']}")
        print(f"Page: {result['page']}")
        print(f"Similarity: {result['similarity']}")
        print(f"Text: {result['text']}\n")
