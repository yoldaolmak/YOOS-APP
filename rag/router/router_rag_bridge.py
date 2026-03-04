from rag.split.section_split_engine import split_sections
from rag.embedding.embedding_pipeline import embed_sections
from rag.storage._vector_store_disabled import VectorStore
from rag.retrieval.retrieval_engine import retrieve

class RAGBridge:

    def __init__(self):
        self.store = VectorStore()

    def ingest(self, text):
        sections = split_sections(text)
        vectors = embed_sections(sections)
        self.store.add(vectors)

    def query(self, text, top_k=3):
        qvec = embed_sections([text])[0]["vector"]
        return retrieve(qvec, self.store.all(), top_k=top_k)
