import json
import re
from pathlib import Path

SOURCE_FILE = "/home/ai/clawdbot/raw_posts.json"
OUTPUT_FILE = "/home/ai/clawdbot/corpus/travel_chunks.jsonl"

def clean_html(text):
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def chunk_text(text, size=500):
    words = text.split()
    for i in range(0, len(words), size):
        yield " ".join(words[i:i+size])

def main():
    Path("/home/ai/clawdbot/corpus").mkdir(exist_ok=True)

    with open(SOURCE_FILE, "r", encoding="utf-8") as f:
        posts = json.load(f)

    chunk_id = 0

    with open(OUTPUT_FILE, "w", encoding="utf-8") as out:
        for p in posts:
            content = clean_html(p["content"])
            for chunk in chunk_text(content):
                record = {
                    "chunk_id": chunk_id,
                    "post_id": p["id"],
                    "title": p["title"],
                    "text": chunk
                }
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
                chunk_id += 1

    print("Chunks created:", chunk_id)

if __name__ == "__main__":
    main()
