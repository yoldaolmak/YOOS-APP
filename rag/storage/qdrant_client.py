class QdrantClient:
    def __init__(self, host="localhost", port=6333):
        self.host = host
        self.port = port

    def status(self):
        return f"Qdrant client ready: {self.host}:{self.port}"
