import math

def cosine(a, b):
    dot = sum(x*y for x,y in zip(a,b))
    na = math.sqrt(sum(x*x for x in a))
    nb = math.sqrt(sum(x*x for x in b))
    if na == 0 or nb == 0:
        return 0
    return dot/(na*nb)

def retrieve(query_vec, items, top_k=3):
    scored = []
    for it in items:
        s = cosine(query_vec, it["vector"])
        scored.append((s, it))
    scored.sort(reverse=True, key=lambda x: x[0])
    return [x[1] for x in scored[:top_k]]
