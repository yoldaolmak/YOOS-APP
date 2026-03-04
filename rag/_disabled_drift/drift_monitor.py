class DriftMonitor:
    def __init__(self):
        self.history = []

    def record(self, query):
        self.history.append(query)

    def size(self):
        return len(self.history)
