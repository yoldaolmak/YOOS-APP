def centroid(vectors):
    if not vectors:
        return []

    dim = len(vectors[0])
    c = [0]*dim

    for v in vectors:
        for i,x in enumerate(v):
            c[i] += x

    n = len(vectors)
    return [x/n for x in c]
