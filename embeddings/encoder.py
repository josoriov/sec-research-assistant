"""Local embedding model. The heavy import is lazy so tests can inject a stub."""
from __future__ import annotations

import os

MODEL_NAME = os.environ.get(
    "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
)
EMBEDDING_DIM = 384


class SentenceTransformerEncoder:
    """CPU sentence encoder; vectors are L2-normalized for cosine search."""

    def __init__(self, model_name: str = MODEL_NAME):
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name, device="cpu")
        self.model_version = model_name
        dimension = self._model.get_embedding_dimension()
        if dimension is None:
            raise ValueError("embedding model does not report its dimension")
        self.dim = dimension

    def encode(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(list(texts), normalize_embeddings=True)
        return [[float(value) for value in vector] for vector in vectors]
