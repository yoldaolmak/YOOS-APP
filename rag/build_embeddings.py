import json
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("BAAI/bge-small-en-v1.5")

input_file = "data/corpus_stage1.jsonl"
output_file = "data/corpus_embeddings.jsonl"

with open(input_file, "r") as fin, open(output_file, "w") as fout:
    for line in fin:
        item = json.loads(line)
        text = item["text"]

        emb = model.encode(text).tolist()

        item["embedding"] = emb
        fout.write(json.dumps(item) + "\n")

print("Embedding tamamlandı.")
