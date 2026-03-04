from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient

model = SentenceTransformer("BAAI/bge-small-en-v1.5")
client = QdrantClient("http://localhost:6333")

query = "Kapadokya gezilecek yerler"
vector = model.encode(query).tolist()

results = client.query_points(
    collection_name="kemal_voice_travel",
    query=vector,
    limit=3
)

for r in results.points:
    print(r.payload["title"])
