import json
import numpy as np
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("BAAI/bge-small-en-v1.5")

query = "Napoli'de gezilecek yerler hakkında kişisel deneyim"

qvec = model.encode(query)

data = []
with open("data/corpus_embeddings.jsonl") as f:
    for line in f:
        item = json.loads(line)
        data.append(item)

def cosine(a,b):
    return np.dot(a,b)/(np.linalg.norm(a)*np.linalg.norm(b))

scores = []

for item in data:
    score = cosine(qvec, item["embedding"])
    scores.append((score, item))

scores.sort(reverse=True)

for s,i in scores[:3]:
    print("\nSCORE:", round(s,3))
    print("TITLE:", i.get("title"))
    print(i["text"][:200])
