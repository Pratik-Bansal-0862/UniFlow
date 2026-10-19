
from app.integrations.chroma_vector_store import ChromaVectorStore
from app.integrations.interfaces.vector_space import VectorStore
from app.schemas.knowledge import RetrievedChunk
from app.services.embedding_service import EmbeddingService


class DocumentRetrievalService:
    """Retrieve relevant document chunks for an authenticated student."""

    def __init__(
        self,
        vector_store: VectorStore | None = None,
        embedding_service: EmbeddingService | None = None,
    ) -> None:
        self.vector_store = (
            vector_store if vector_store is not None else ChromaVectorStore()
        )
        self.embedding_service = (
            embedding_service
            if embedding_service is not None
            else EmbeddingService()
        )

    def retrieve(
        self,
        query: str,
        *,
        student_id: str,
        limit: int = 5,
    ) -> list[RetrievedChunk]:
        """Return the most relevant chunks belonging to one student."""

        if not query.strip():
            raise ValueError("Search query cannot be empty.")

        if not student_id.strip():
            raise ValueError("student_id is required.")

        if not 1 <= limit <= 20:
            raise ValueError("limit must be between 1 and 20.")

        query_embedding = self.embedding_service.embed_query(query.strip())

        return self.vector_store.search(
            query_embedding=query_embedding,
            student_id=student_id,
            limit=limit,
        )
