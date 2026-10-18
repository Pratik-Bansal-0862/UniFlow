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
