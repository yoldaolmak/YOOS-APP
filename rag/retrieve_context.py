import json
import numpy as np
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("BAAI/bge-small-en-v1.5")

def cosine(a,b):
    return np.dot(a,b)/(np.linalg.norm(a)*np.linalg.norm(b))

def retrieve(query, top_k=3):

    qvec = model.encode(query)

    data=[]
    with open("rag/data/corpus_embeddings.jsonl") as f:
        for line in f:
            data.append(json.loads(line))

    scores=[]

    for item in data:
        s=cosine(qvec,item["embedding"])
        scores.append((s,item))

    scores.sort(reverse=True)

    return [x[1]["text"] for x in scores[:top_k]]
