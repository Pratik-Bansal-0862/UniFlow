from __future__ import annotations

import re
from collections import Counter

from app.integrations.chroma_vector_store import ChromaVectorStore
from app.services.embedding_service import EmbeddingService


class DocumentRetrievalService:
    def __init__(self, embedding_service=None, vector_store=None):
        self.embedding_service = embedding_service or EmbeddingService()
        self.vector_store = vector_store or ChromaVectorStore()

    @staticmethod
    def _terms(text: str) -> list[str]:
        # Keep useful numeric/date tokens (e.g. "2026", "october", "28").
        tokens = re.findall(r"[a-z0-9]+", (text or "").lower())
        stop_words = {
            "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
            "how", "i", "in", "is", "it", "me", "my", "of", "on", "or",
            "that", "the", "this", "to", "what", "when", "where", "which",
            "who", "with", "you", "your",
        }
        return [token for token in tokens if token not in stop_words and len(token) > 1]

    @classmethod
    def _lexical_score(cls, query: str, text: str) -> float:
        query_terms = cls._terms(query)
        if not query_terms:
            return 0.0
        counts = Counter(cls._terms(text))
        unique_terms = set(query_terms)
        matched = sum(1 for term in unique_terms if counts[term])
        coverage = matched / len(unique_terms)
        # Small frequency bonus; coverage remains the dominant signal.
        frequency_bonus = sum(min(counts[t], 3) for t in unique_terms) / (3 * len(unique_terms))
        return coverage + 0.05 * frequency_bonus

    def retrieve(self, query: str, student_id: str, limit: int = 5):
        if not query or not query.strip():
            raise ValueError("Search query cannot be empty")
        if not student_id or not student_id.strip():
            raise ValueError("student_id is required")
        if not 1 <= limit <= 20:
            raise ValueError("limit must be between 1 and 20")

        normalized_query = query.strip()
        query_embedding = self.embedding_service.embed_query(normalized_query)
        hybrid = getattr(self.vector_store, "search_hybrid", None)
        if callable(hybrid):
            results = hybrid(
                query=normalized_query,
                query_embedding=query_embedding,
                student_id=student_id,
                limit=limit,
            )
        else:
            results = self.vector_store.search(
                query_embedding=query_embedding,
                student_id=student_id,
                limit=limit,
            )

        # Deduplicate first, then rerank only the already student-scoped candidates.
        # Vector distance is retained as the semantic signal; it is never fabricated.
        deduped, seen_texts, seen_ids = [], set(), set()
        for item in results or []:
            chunk = getattr(item, "chunk", None)
            if chunk is None:
                continue
            # Defence in depth: do not return a chunk whose metadata is cross-student.
            chunk_student_id = str(getattr(chunk, "student_id", "") or "")
            if chunk_student_id and chunk_student_id != student_id:
                continue

            chunk_id = str(getattr(chunk, "chunk_id", "") or "")
            document_id = str(getattr(chunk, "document_id", "") or "")
            raw_text = str(getattr(chunk, "text", "") or "")
            normalized_text = " ".join(raw_text.lower().split())
            fingerprint = (
                document_id,
                normalized_text[:180] if len(normalized_text) <= 360
                else normalized_text[:180] + normalized_text[-180:],
            )
            if (chunk_id and chunk_id in seen_ids) or (normalized_text and fingerprint in seen_texts):
                continue
            if chunk_id:
                seen_ids.add(chunk_id)
            if normalized_text:
                seen_texts.add(fingerprint)

            distance = getattr(item, "distance", None)
            lexical_score = self._lexical_score(normalized_query, raw_text)
            # Cosine distance is commonly 0..2. Convert it to a bounded similarity.
            # Missing distance contributes no semantic score rather than a fake value.
            semantic_score = (
                max(0.0, min(1.0, 1.0 - float(distance)))
                if distance is not None
                else 0.0
            )
            # Exact query-term coverage is a modest reranking signal, not a replacement
            # for embeddings. This lifts clearly relevant passages without discarding
            # semantically relevant paraphrases.
            combined_score = 0.70 * semantic_score + 0.30 * lexical_score
            deduped.append((combined_score, lexical_score, semantic_score, item))

        deduped.sort(key=lambda row: (row[0], row[1], row[2]), reverse=True)
        return [row[3] for row in deduped[:limit]]

    # Keep the newer alias for any caller already using it.
    def search(self, query: str, student_id: str, limit: int = 5):
        return self.retrieve(query=query, student_id=student_id, limit=limit)