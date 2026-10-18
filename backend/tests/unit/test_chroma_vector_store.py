
import pytest

from app.integrations.chroma_vector_store import ChromaVectorStore
from app.schemas.knowledge import KnowledgeChunk


@pytest.fixture
def store(tmp_path):
    return ChromaVectorStore(
        persist_directory=str(tmp_path / "chroma"),
        collection_name="test_knowledge",
    )


def make_chunk(
    chunk_id: str,
    student_id: str,
    text: str,
) -> KnowledgeChunk:
    return KnowledgeChunk(
        chunk_id=chunk_id,
        document_id="doc-1",
        student_id=student_id,
        text=text,
        chunk_index=0,
        source_name="notes.pdf",
        page_number=1,
    )


def test_upsert_and_search_return_matching_student(store):
    store.upsert(
        [
            make_chunk("chunk-a", "student-a", "Scholarship details"),
            make_chunk("chunk-b", "student-b", "Exam timetable"),
        ],
        [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
        ],
    )

    results = store.search(
        query_embedding=[1.0, 0.0, 0.0],
        student_id="student-a",
        limit=5,
    )

    assert len(results) == 1
    assert results[0].chunk.chunk_id == "chunk-a"
    assert results[0].chunk.student_id == "student-a"
    assert results[0].chunk.text == "Scholarship details"


def test_upsert_rejects_mismatched_embedding_count(store):
    chunk = make_chunk("chunk-a", "student-a", "Example")

    with pytest.raises(ValueError):
        store.upsert([chunk], [])


def test_search_rejects_missing_student_id(store):
    with pytest.raises(ValueError):
        store.search([1.0, 0.0], "", limit=5)


def test_delete_document_is_student_scoped(store):
    store.upsert(
        [
            make_chunk("chunk-a", "student-a", "Student A notes"),
            make_chunk("chunk-b", "student-b", "Student B notes"),
        ],
        [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
        ],
    )

    store.delete_document("doc-1", "student-a")

    remaining = store.search(
        query_embedding=[0.0, 1.0, 0.0],
        student_id="student-b",
        limit=5,
    )

    assert len(remaining) == 1
    assert remaining[0].chunk.student_id == "student-b"
