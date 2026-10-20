from __future__ import annotations

import re
from collections.abc import Sequence

import chromadb

from app.integrations.interfaces.vector_space import VectorStore
from app.schemas.knowledge import KnowledgeChunk, RetrievedChunk


_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9+#._/-]*", re.IGNORECASE)


def _tokens(text: str) -> set[str]:
    return {
        token.casefold()
        for token in _TOKEN_RE.findall(text)
        if len(token) > 1
    }


class ChromaVectorStore:
    def __init__(
        self,
        persist_directory: str = "./data/chroma",
        collection_name: str = "uniflow_knowledge",
    ) -> None:
        self.client = chromadb.PersistentClient(path=persist_directory)
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
            raise ValueError("Each chunk must have exactly one embedding.")
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
                    "page_number": chunk.page_number if chunk.page_number is not None else -1,
                }
                for chunk in chunks
            ],
        )

    @staticmethod
    def _to_retrieved(
        ids: list[str],
        documents: list[str],
        metadatas: list[dict],
        distances: list[float],
    ) -> list[RetrievedChunk]:
        retrieved: list[RetrievedChunk] = []
        for chunk_id, text, metadata, distance in zip(ids, documents, metadatas, distances):
            chunk = KnowledgeChunk(
                chunk_id=chunk_id,
                document_id=metadata["document_id"],
                student_id=metadata["student_id"],
                text=text,
                chunk_index=metadata["chunk_index"],
                source_name=metadata["source_name"],
                page_number=metadata["page_number"] if metadata["page_number"] >= 1 else None,
            )
            retrieved.append(RetrievedChunk(chunk=chunk, distance=float(distance)))
        return retrieved

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
        return self._to_retrieved(
            result["ids"][0],
            result["documents"][0],
            result["metadatas"][0],
            result["distances"][0],
        )

    def search_hybrid(
        self,
        *,
        query: str,
        query_embedding: list[float],
        student_id: str,
        limit: int = 5,
    ) -> list[RetrievedChunk]:
        """Fuse student-scoped vector and lexical results using reciprocal rank."""
        if not student_id.strip():
            raise ValueError("student_id is required.")
        if not query_embedding:
            raise ValueError("Query embedding cannot be empty.")
        if limit < 1:
            raise ValueError("limit must be positive.")

        # Oversample vector results, then union with lexical candidates. Fetching
        # only this student's chunks ensures lexical retrieval cannot cross users.
        candidate_limit = min(max(limit * 4, 20), 100)
        vector_result = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=candidate_limit,
            where={"student_id": student_id},
            include=["documents", "metadatas", "distances"],
        )
        vector_chunks = self._to_retrieved(
            vector_result["ids"][0],
            vector_result["documents"][0],
            vector_result["metadatas"][0],
            vector_result["distances"][0],
        )

        lexical_result = self.collection.get(
            where={"student_id": student_id},
            include=["documents", "metadatas"],
        )
        lexical_chunks = self._to_retrieved(
            lexical_result["ids"],
            lexical_result["documents"],
            lexical_result["metadatas"],
            [1.0] * len(lexical_result["ids"]),
        )

        query_tokens = _tokens(query)
        if not query_tokens:
            return vector_chunks[:limit]

        vector_rank = {item.chunk.chunk_id: index + 1 for index, item in enumerate(vector_chunks)}
        lexical_scored = []
        for item in lexical_chunks:
            chunk_tokens = _tokens(item.chunk.text)
            if not chunk_tokens:
                continue
            overlap = len(query_tokens & chunk_tokens)
            if overlap == 0:
                continue
            # Overlap ratio rewards specific terms without requiring all query
            # words to occur in a chunk.
            lexical_score = overlap / len(query_tokens)
            lexical_scored.append((item, lexical_score))
        lexical_scored.sort(
            key=lambda pair: (
                pair[1],
                len(query_tokens & _tokens(pair[0].chunk.text)),
                -pair[0].chunk.chunk_index,
            ),
            reverse=True,
        )
        lexical_rank = {
            item.chunk.chunk_id: rank
            for rank, (item, _) in enumerate(lexical_scored, start=1)
        }

        # Keep the real Chroma distance when a chunk appears in both lists.
        # Lexical-only matches carry a placeholder and must not overwrite it.
        # Preserve genuine vector distances. Lexical-only candidates must not
        # masquerade as vector results with a synthetic distance of 1.0.
        by_id = {item.chunk.chunk_id: item for item in vector_chunks}
        vector_ids = set(by_id)
        for lexical_item, _lexical_score in lexical_scored:
            if lexical_item.chunk.chunk_id not in vector_ids:
                lexical_item.distance = None
                by_id[lexical_item.chunk.chunk_id] = lexical_item
        # Reciprocal-rank fusion is robust to the different scales of vector
        # distances and lexical overlap. A tiny lexical boost rewards exact terms.
        fused = []
        for chunk_id, item in by_id.items():
            score = 0.0
            if chunk_id in vector_rank:
                score += 1.0 / (60 + vector_rank[chunk_id])
            if chunk_id in lexical_rank:
                score += 1.0 / (60 + lexical_rank[chunk_id])
                score += 0.001 * next(
                    (s for candidate, s in lexical_scored if candidate.chunk.chunk_id == chunk_id),
                    0.0,
                )
            fused.append((score, item))
        fused.sort(key=lambda pair: pair[0], reverse=True)
        return [item for _, item in fused[:limit]]

    def delete_document(self, document_id: str, student_id: str) -> None:
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
