from sentence_transformers import SentenceTransformer
from rag.retrieval.retrieval_engine import retrieve

_MODEL_NAME = "BAAI/bge-small-en-v1.5"
_model = None


def _get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(_MODEL_NAME)
    return _model


class RAGBridge:

    def query(self, text, top_k=3):
        model = _get_model()
        qvec = model.encode(text).tolist()
        return retrieve(qvec, top_k=top_k)
