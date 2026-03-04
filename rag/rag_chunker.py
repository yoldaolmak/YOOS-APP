import os
import json

INPUT_DIR = "corpus_text"
OUTPUT_FILE = "corpus_chunks.jsonl"

CHUNK_SIZE = 600
OVERLAP = 100

def chunk_text(text):
    words = text.split()
    chunks = []
    i = 0

    while i < len(words):
        chunk = words[i:i + CHUNK_SIZE]
        chunks.append(" ".join(chunk))
        i += CHUNK_SIZE - OVERLAP

    return chunks


with open(OUTPUT_FILE, "w", encoding="utf-8") as out:
    for f in os.listdir(INPUT_DIR):

        if not f.endswith(".txt"):
            continue

        post_id = f.replace(".txt", "")
        path = os.path.join(INPUT_DIR, f)

        with open(path, encoding="utf-8") as file:
            text = file.read()

        for chunk in chunk_text(text):

            row = {
                "post_id": post_id,
                "voice_group": "A",
                "year": 2012,
                "source": "yoldaolmak",
                "text": chunk
            }

            out.write(json.dumps(row, ensure_ascii=False) + "\n")
