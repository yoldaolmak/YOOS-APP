import hashlib

def fake_embedding(text, dim=16):
    h = hashlib.sha256(text.encode()).digest()
    return [b/255 for b in h[:dim]]

def embed_sections(sections):
    vectors = []
    for s in sections:
        vectors.append({
            "text": s,
            "vector": fake_embedding(s)
        })
    return vectors
