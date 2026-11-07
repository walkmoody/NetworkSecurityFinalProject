"""Create citations solely from trusted retrieval metadata."""

def clean_citations(ids, evidence):
    if not isinstance(ids, list) or not 1 <= len(ids) <= 8:
        return []
    indexed = {row["id"]: row for row in evidence}
    citations, seen = [], set()
    for key in ids:
        if not isinstance(key, str) or key not in indexed:
            return []
        if key in seen:
            continue
        seen.add(key)
        row = indexed[key]
        citations.append({
            "id": row["id"], "source": row["source"],
            "page": int(row["page"]), "chunk": int(row["chunk"]),
            "section": f"Page {row['page']}, chunk {row['chunk']}",
        })
    return citations
