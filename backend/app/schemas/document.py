from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DocumentResponse(BaseModel):
    id: UUID
    filename: str
    content_type: str
    file_size: int
    chunk_count: int
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RetrievedDocumentChunk(BaseModel):
    document_id: str
    filename: str
    text: str
    chunk_index: int = Field(ge=0)
    distance: float


class DocumentSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=5, ge=1, le=20)


class DocumentSearchResponse(BaseModel):
    results: list[RetrievedDocumentChunk]
    answer: str | None = None
    answer_status: str = "not_requested"
