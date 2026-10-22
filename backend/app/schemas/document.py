
from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


DocumentCategory = Literal["personal", "reference", "unverified"]


class DocumentResponse(BaseModel):
    id: UUID
    filename: str
    content_type: str
    file_size: int
    chunk_count: int
    status: str
    category: DocumentCategory
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentCategoryUpdate(BaseModel):
    category: DocumentCategory


class RetrievedDocumentChunk(BaseModel):
    document_id: str
    filename: str
    text: str
    chunk_index: int = Field(ge=0)
    distance: Optional[float] = None
    category: DocumentCategory = "unverified"


class DocumentSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=5, ge=1, le=20)


class DocumentSearchResponse(BaseModel):
    results: list[RetrievedDocumentChunk]
    answer: str | None = None
    answer_status: str = "not_requested"
