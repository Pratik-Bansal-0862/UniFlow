
from collections.abc import Sequence

import chromadb

from app.integrations.interfaces.vector_space import VectorStore
from app.schemas.knowledge import KnowledgeChunk, RetrievedChunk


class ChromaVectorStore:
    def __init__(
        self,
        persist_directory: str = "./data/chroma",
        collection_name: str = "uniflow_knowledge",
    ) -> None:
        self.client = chromadb.PersistentClient(
            path=persist_directory
        )
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert(
        self,
        chunks: Sequence[KnowledgeChunk],
        embeddings: Sequence[list[float]],
    ) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError(
                "Each chunk must have exactly one embedding."
            )

        if not chunks:
            return

        ids = [chunk.chunk_id for chunk in chunks]

        if len(set(ids)) != len(ids):
            raise ValueError("Chunk IDs must be unique per batch.")

        for embedding in embeddings:
            if not embedding:
                raise ValueError("Embeddings cannot be empty.")

        self.collection.upsert(
            ids=ids,
            embeddings=[list(vector) for vector in embeddings],
            documents=[chunk.text for chunk in chunks],
            metadatas=[
                {
                    "document_id": chunk.document_id,
                    "student_id": chunk.student_id,
                    "chunk_index": chunk.chunk_index,
                    "source_name": chunk.source_name,
                    "page_number": (
                        chunk.page_number
                        if chunk.page_number is not None
                        else -1
                    ),
                }
                for chunk in chunks
            ],
        )

    def search(
        self,
        query_embedding: list[float],
        student_id: str,
        limit: int = 5,
    ) -> list[RetrievedChunk]:
        if not student_id.strip():
            raise ValueError("student_id is required.")

        if not query_embedding:
            raise ValueError("Query embedding cannot be empty.")

        if limit < 1:
            raise ValueError("limit must be positive.")

        result = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=limit,
            where={"student_id": student_id},
            include=["documents", "metadatas", "distances"],
        )

        retrieved = []

        ids = result["ids"][0]
        documents = result["documents"][0]
        metadatas = result["metadatas"][0]
        distances = result["distances"][0]

        for chunk_id, text, metadata, distance in zip(
            ids, documents, metadatas, distances
        ):
            chunk = KnowledgeChunk(
                chunk_id=chunk_id,
                document_id=metadata["document_id"],
                student_id=metadata["student_id"],
                text=text,
                chunk_index=metadata["chunk_index"],
                source_name=metadata["source_name"],
                page_number=(
                    metadata["page_number"]
                    if metadata["page_number"] >= 1
                    else None
                ),
            )

            retrieved.append(
                RetrievedChunk(chunk=chunk, distance=distance)
            )

        return retrieved

    def delete_document(
        self,
        document_id: str,
        student_id: str,
    ) -> None:
        if not document_id.strip():
            raise ValueError("document_id is required.")

        if not student_id.strip():
            raise ValueError("student_id is required.")

        self.collection.delete(
            where={
                "$and": [
                    {"document_id": document_id},
                    {"student_id": student_id},
                ]
            }
        )
