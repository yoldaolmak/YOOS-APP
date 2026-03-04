from qdrant_client import QdrantClient

client = QdrantClient("http://localhost:6333")
COLLECTION = "kemal_voice_travel"

def retrieve(query_vec, top_k=3):
    results = client.query_points(
        collection_name=COLLECTION,
        query=query_vec,
        limit=top_k
    )

    out = []
    for r in results.points:
        out.append({
            "title": r.payload.get("title"),
            "text": r.payload.get("text"),
            "post_id": r.payload.get("post_id")
        })

    return out
