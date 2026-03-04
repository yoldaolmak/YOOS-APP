import json
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

MODEL = "BAAI/bge-small-en-v1.5"
COLLECTION = "kemal_voice_travel"
BATCH = 64

model = SentenceTransformer(MODEL)
client = QdrantClient("http://localhost:6333")

points = []

with open("corpus/travel_chunks.jsonl") as f:
    for i, line in enumerate(f):
        obj = json.loads(line)

        vec = model.encode(obj["text"]).tolist()

        points.append(
            PointStruct(
                id=i,
                vector=vec,
                payload={
                    "post_id": obj["post_id"],
                    "title": obj["title"],
                    "text": obj["text"]
                }
            )
        )

        if len(points) >= BATCH:
            client.upsert(collection_name=COLLECTION, points=points)
            points = []

if points:
    client.upsert(collection_name=COLLECTION, points=points)

print("Ingest complete")
