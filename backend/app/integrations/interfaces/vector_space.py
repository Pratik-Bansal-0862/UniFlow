
from typing import Protocol, Sequence

from app.schemas.knowledge import RetrievedChunk, KnowledgeChunk


class VectorStore(Protocol):
    def upsert(
        self,
        chunks: Sequence[KnowledgeChunk],
        embeddings: Sequence[list[float]],
    ) -> None:
        """Insert or update chunks and their embeddings."""
        ...

    def search(
        self,
        query_embedding: list[float],
        student_id: str,
        limit: int = 5,
    ) -> list[RetrievedChunk]:
        """Search only within the specified student's data."""
        ...

    def delete_document(
        self,
        document_id: str,
        student_id: str,
    ) -> None:
        """Delete indexed chunks for one student's document."""
        ...
