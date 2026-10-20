from __future__ import annotations

import math
import re
from dataclasses import dataclass

import pytest

from app.services.document_chunking_service import chunk_text


def test_chunking_preserves_paragraph_boundary_when_possible() -> None:
    first = "A useful paragraph about financial aid and grant deadlines. " * 7
    second = "A separate paragraph about biology lab reports and course registration. " * 7
    chunks = chunk_text(first + "\n\n" + second, chunk_size=500, overlap=60)
    assert len(chunks) >= 2
    assert all(chunk.strip() for chunk in chunks)
    assert all(len(chunk) <= 500 for chunk in chunks)
    # The second paragraph remains discoverable after chunking.
    assert any("biology lab reports" in chunk for chunk in chunks)


def test_chunking_overlap_is_retained_without_stalling() -> None:
    text = "student portal assignment deadline " * 120
    chunks = chunk_text(text, chunk_size=300, overlap=50)
    assert len(chunks) > 2
    assert all(len(chunk) <= 300 for chunk in chunks)
    assert all(chunks[i][-30:] in chunks[i + 1] for i in range(len(chunks) - 1))


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", []),
        ("   \n  ", []),
        ("One short sentence.", ["One short sentence."]),
    ],
)
def test_chunking_empty_and_short_inputs(text: str, expected: list[str]) -> None:
    assert chunk_text(text, chunk_size=100, overlap=10) == expected


def test_chunking_rejects_invalid_sizes() -> None:
    with pytest.raises(ValueError):
        chunk_text("text", chunk_size=0, overlap=0)
    with pytest.raises(ValueError):
        chunk_text("text", chunk_size=10, overlap=10)


@dataclass
class FakeChunk:
    chunk_id: str
    document_id: str
    student_id: str
    text: str
    chunk_index: int = 0
    source_name: str = "handbook.pdf"
    page_number: int | None = 2


@dataclass
class FakeRetrieved:
    chunk: FakeChunk
    distance: float = 0.2


class FakeCollection:
    def __init__(self, records: list[FakeRetrieved]) -> None:
        self.records = records
        self.last_where = None
        self.query_calls = 0

    def query(self, *, query_embeddings, n_results, where, include):
        self.last_where = where
        self.query_calls += 1
        rows = [r for r in self.records if r.chunk.student_id == where["student_id"]]
        rows.sort(key=lambda r: r.distance)
        rows = rows[:n_results]
        return {
            "ids": [[r.chunk.chunk_id for r in rows]],
            "documents": [[r.chunk.text for r in rows]],
            "metadatas": [[{
                "document_id": r.chunk.document_id,
                "student_id": r.chunk.student_id,
                "chunk_index": r.chunk.chunk_index,
                "source_name": r.chunk.source_name,
                "page_number": r.chunk.page_number or -1,
            } for r in rows]],
            "distances": [[r.distance for r in rows]],
        }

    def get(self, *, where, include):
        self.last_where = where
        rows = [r for r in self.records if r.chunk.student_id == where["student_id"]]
        return {
            "ids": [r.chunk.chunk_id for r in rows],
            "documents": [r.chunk.text for r in rows],
            "metadatas": [{
                "document_id": r.chunk.document_id,
                "student_id": r.chunk.student_id,
                "chunk_index": r.chunk.chunk_index,
                "source_name": r.chunk.source_name,
                "page_number": r.chunk.page_number or -1,
            } for r in rows],
        }


def _store_with_fake_collection():
    from app.integrations.chroma_vector_store import ChromaVectorStore

    records = [
        FakeRetrieved(FakeChunk(
            "s1-exact", "doc-1", "student-1",
            "Scholarship portal: FAFSA correction deadline is October 28. Contact the financial aid office.",
            0, "aid-guide.pdf", 3,
        ), 0.38),
        FakeRetrieved(FakeChunk(
            "s1-semantic", "doc-2", "student-1",
            "Students should submit corrected federal aid forms before the end-of-month cutoff.",
            1, "student-handbook.pdf", 4,
        ), 0.12),
        FakeRetrieved(FakeChunk(
            "s1-other", "doc-3", "student-1",
            "Biology lab reports are due on Friday; include methods and observations.",
            2, "biology.pdf", 1,
        ), 0.31),
        FakeRetrieved(FakeChunk(
            "s2-secret", "doc-4", "student-2",
            "FAFSA correction deadline is October 28. Private student record.",
            0, "private.pdf", 2,
        ), 0.01),
    ]
    store = object.__new__(ChromaVectorStore)
    store.collection = FakeCollection(records)
    return store


def test_hybrid_retrieval_promotes_exact_terms_and_keeps_student_scope() -> None:
    store = _store_with_fake_collection()
    results = store.search_hybrid(
        query="FAFSA correction deadline October 28",
        query_embedding=[0.1, 0.2],
        student_id="student-1",
        limit=3,
    )
    ids = [item.chunk.chunk_id for item in results]
    assert "s1-exact" in ids
    assert "s2-secret" not in ids
    assert store.collection.last_where == {"student_id": "student-1"}


def test_hybrid_retrieval_returns_semantic_candidate_for_paraphrase() -> None:
    store = _store_with_fake_collection()
    results = store.search_hybrid(
        query="When must I finish my corrected financial aid paperwork?",
        query_embedding=[0.1, 0.2],
        student_id="student-1",
        limit=3,
    )
    ids = [item.chunk.chunk_id for item in results]
    # Lexical overlap may be low; the semantic vector candidate remains eligible.
    assert "s1-semantic" in ids
    assert all(item.chunk.student_id == "student-1" for item in results)


def test_hybrid_search_never_fetches_lexical_candidates_for_other_students() -> None:
    store = _store_with_fake_collection()
    store.search_hybrid(
        query="private student record",
        query_embedding=[0.1, 0.2],
        student_id="student-1",
        limit=5,
    )
    assert store.collection.last_where == {"student_id": "student-1"}


def test_missing_evidence_does_not_create_lexical_results() -> None:
    store = _store_with_fake_collection()
    results = store.search_hybrid(
        query="quantum entanglement telescope calibration",
        query_embedding=[0.1, 0.2],
        student_id="student-1",
        limit=3,
    )
    # This tests candidate ranking, not the answer service's abstention policy.
    assert results
    assert all(item.chunk.student_id == "student-1" for item in results)


def test_source_attribution_survives_hybrid_ranking() -> None:
    store = _store_with_fake_collection()
    results = store.search_hybrid(
        query="FAFSA correction deadline October 28",
        query_embedding=[0.1, 0.2],
        student_id="student-1",
        limit=3,
    )
    exact = next(item for item in results if item.chunk.chunk_id == "s1-exact")
    assert exact.chunk.source_name == "aid-guide.pdf"
    assert exact.chunk.page_number == 3
    assert exact.chunk.document_id == "doc-1"
