import pytest

from app.services.document_retrieval_service import DocumentRetrievalService


class FakeEmbeddingService:
    def __init__(self):
        self.queries = []

    def embed_query(self, query):
        self.queries.append(query)
        return [0.1, 0.2, 0.3]


class FakeVectorStore:
    def __init__(self):
        self.search_args = None

    def search(self, *, query_embedding, student_id, limit):
        self.search_args = {
            "query_embedding": query_embedding,
            "student_id": student_id,
            "limit": limit,
        }
        return []


def make_service():
    vector_store = FakeVectorStore()
    embedding_service = FakeEmbeddingService()
    service = DocumentRetrievalService(
        vector_store=vector_store,
        embedding_service=embedding_service,
    )
    return service, vector_store, embedding_service


def test_retrieve_embeds_query_and_passes_student_scope():
    service, vector_store, embedding_service = make_service()

    results = service.retrieve(
        "  scholarship details  ",
        student_id="student-a",
        limit=3,
    )

    assert results == []
    assert embedding_service.queries == ["scholarship details"]
    assert vector_store.search_args == {
        "query_embedding": [0.1, 0.2, 0.3],
        "student_id": "student-a",
        "limit": 3,
    }


@pytest.mark.parametrize("query", ["", "   "])
def test_retrieve_rejects_empty_query(query):
    service, vector_store, embedding_service = make_service()

    with pytest.raises(ValueError, match="Search query cannot be empty"):
        service.retrieve(query, student_id="student-a")

    assert embedding_service.queries == []
    assert vector_store.search_args is None


def test_retrieve_rejects_missing_student_id():
    service, vector_store, embedding_service = make_service()

    with pytest.raises(ValueError, match="student_id is required"):
        service.retrieve("scholarship details", student_id="   ")

    assert embedding_service.queries == []
    assert vector_store.search_args is None


@pytest.mark.parametrize("limit", [0, 21])
def test_retrieve_rejects_limit_out_of_range(limit):
    service, vector_store, embedding_service = make_service()

    with pytest.raises(ValueError, match="limit must be between 1 and 20"):
        service.retrieve("scholarship details", student_id="student-a", limit=limit)

    assert embedding_service.queries == []
    assert vector_store.search_args is None
