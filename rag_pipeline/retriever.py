
from rag_pipeline.embeddings import (
    load_embedding_model,
    get_collection,
    generate_embeddings
)

TITLE_SLIDE_WORDS = 8     # a slide with fewer words is a section title, e.g. "Network Security Requirements"
EXPANDED_MIN_WORDS = 120  # a matched title slide borrows following slides until it has this many words
EXPANDED_MAX_PAGES = 4


def _expand_title_slide(collection, row):
    """
    Title slides match questions closely but hold no content; the slides after them do.
    Append the following pages of the same document so the match carries real evidence.
    """

    if len(row["text"].split()) >= TITLE_SLIDE_WORDS or row["chunk"] != 1:
        return row

    following = collection.get(
        where={"$and": [
            {"source": row["source"]},
            {"page": {"$gt": row["page"]}},
            {"page": {"$lte": row["page"] + EXPANDED_MAX_PAGES}},
        ]},
        include=["documents", "metadatas"],
    )
    pages = sorted(
        zip(following["metadatas"], following["documents"]),
        key=lambda item: (item[0]["page"], item[0]["chunk"]),
    )

    text = row["text"]
    for _, document in pages:
        if len(text.split()) >= EXPANDED_MIN_WORDS:
            break
        text += " " + document

    return {**row, "text": text}


def retrieve_documents(query, top_k=3, course=None, expand_titles=False): # retrieve the most relevant document chunks from the local ChromaDB vector database; course limits results to one data/ folder
    # expand_titles: replace title-only slides with the slides they introduce (Tutor only; the Quiz
    # Agent re-reads stored chunk text when grading, so its evidence must stay as stored)

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

    if expand_titles:
        retrieved_documents = [
            _expand_title_slide(collection, row) for row in retrieved_documents
        ]

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
