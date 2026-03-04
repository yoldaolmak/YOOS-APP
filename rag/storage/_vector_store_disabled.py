class VectorStore:
    def __init__(self):
        self.items = []

    def add(self, vectors):
        self.items.extend(vectors)

    def all(self):
        return self.items
