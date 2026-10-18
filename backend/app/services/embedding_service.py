from functools import lru_cache

from sentence_transformers import SentenceTransformer


class EmbeddingService:
    """Create text embeddings using a locally cached sentence-transformer."""

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.model_name = model_name

    @property
    def model(self) -> SentenceTransformer:
        return _load_model(self.model_name)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self.model.encode(
            texts, normalize_embeddings=True, show_progress_bar=False
        )
        return vectors.tolist()

    def embed_query(self, text: str) -> list[float]:
        if not text.strip():
            raise ValueError("Search query cannot be empty.")
        return self.embed_texts([text])[0]


@lru_cache(maxsize=2)
def _load_model(model_name: str) -> SentenceTransformer:
    return SentenceTransformer(model_name)
